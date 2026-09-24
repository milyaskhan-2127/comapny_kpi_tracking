import frappe
import json
import re


import frappe
import json
import re

CANONICAL_DEPT_MAP = {
    "PROD": "PRODUCTION",
    "PRODUCTION": "PRODUCTION",
    "DEP_PRODUCTION": "PRODUCTION",
    "FIN": "FINANCE",
    "FINANCE": "FINANCE",
    "ACCOUNTING": "FINANCE",
    "ACCOUNTS": "FINANCE",
    "DEP_FINANCE": "FINANCE",
    "QC": "QC",
    "QUALITY": "QC",
    "QUALITY_CONTROL": "QC",
    "QA": "QC",
    "DEP_QC": "QC",
    "SC": "SUPPLY_CHAIN",
    "SUPPLY_CHAIN": "SUPPLY_CHAIN",
    "LOGISTICS": "SUPPLY_CHAIN",
    "DEP_SUPPLY_CHAIN": "SUPPLY_CHAIN",
    "MAINT": "MAINTENANCE",
    "MAINTENANCE": "MAINTENANCE",
    "DEP_MAINTENANCE": "MAINTENANCE",
    "CS": "CUSTOMER_SUCCESS",
    "CUSTOMER_SUPPORT": "CUSTOMER_SUCCESS",
    "CUSTOMER_SUCCESS": "CUSTOMER_SUCCESS",
    "SUPPORT": "CUSTOMER_SUCCESS",
    "CUSTOMER_SERVICE": "CUSTOMER_SUCCESS",
    "DEP_CUSTOMER_SUCCESS": "CUSTOMER_SUCCESS",
    "HR": "HR",
    "HUMAN_RESOURCES": "HR",
    "DEP_HR": "HR",
    "SALES": "SALES",
    "DEP_SALES": "SALES",
    "SAFETY": "SAFETY",
    "EHS": "SAFETY",
    "DEP_SAFETY": "SAFETY",
    "RND": "RND",
    "RD": "RND",
    "RESEARCH": "RND",
    "DEP_RND": "RND",
    "PROCUREMENT": "PROCUREMENT",
    "PURCHASING": "PROCUREMENT",
    "DEP_PROCUREMENT": "PROCUREMENT",
}


def _clean_department_code(code_or_name):
    """Sanitize department code to adhere to ^[A-Z][A-Z0-9_]*$ without collapsing distinct departments."""
    raw = (code_or_name or "").upper().strip()
    raw = raw.replace("&", "AND").replace("-", "_").replace(" ", "_")
    cleaned = re.sub(r'[^A-Z0-9_]', '', raw)
    cleaned = re.sub(r'_+', '_', cleaned).strip('_')
    if not cleaned or not cleaned[0].isalpha():
        cleaned = f"DEP_{cleaned}" if cleaned else "DEP_NEW"

    # Only map exact standard alias keywords when they are single-token or DEP_ prefixed
    # Never collapse user-disambiguated sub-departments like SALES_B1, SALES_BLOCK_2, etc.
    if cleaned in CANONICAL_DEPT_MAP and ("_" not in cleaned or cleaned.startswith("DEP_")):
        return CANONICAL_DEPT_MAP[cleaned]
    return cleaned


def consolidate_duplicate_departments():
    """
    Consolidates exact duplicate KPI Department records (e.g. duplicate primary keys
    or legacy naming conflicts) without merging distinct user-created departments.
    """
    all_depts = frappe.db.get_all(
        "KPI Department",
        fields=["name", "department_name", "department_code", "is_active", "weight", "description", "location", "creation"],
        order_by="creation asc"
    )
    if not all_depts:
        return

    # Group strictly by exact normalized department_code or primary key name
    dept_groups = {}
    for d in all_depts:
        code = (d.department_code or d.name or "").strip().upper()
        if code not in dept_groups:
            dept_groups[code] = []
        dept_groups[code].append(d)

    for code, depts in dept_groups.items():
        if len(depts) <= 1:
            d = depts[0]
            if not d.department_code:
                clean_code = _clean_department_code(d.name)
                frappe.db.set_value("KPI Department", d.name, "department_code", clean_code, update_modified=False)
            continue

        # Truly duplicate departments sharing the exact same code
        primary = None
        for d in depts:
            if d.name == code:
                primary = d
                break
        if not primary:
            active_ones = [d for d in depts if d.is_active]
            primary = active_ones[0] if active_ones else depts[0]

        primary_name = primary.name
        is_active_flag = 1 if any(d.is_active for d in depts) else 0
        max_weight = max((float(d.weight or 1.0) for d in depts), default=1.0)
        best_dept_name = primary.department_name or primary.name
        best_location = primary.get("location") or next((d.get("location") for d in depts if d.get("location")), "")

        if primary_name != code and not frappe.db.exists("KPI Department", code):
            try:
                frappe.rename_doc("KPI Department", primary_name, code, force=True, ignore_permissions=True)
                primary_name = code
            except Exception:
                pass

        frappe.db.set_value("KPI Department", primary_name, {
            "department_code": code,
            "department_name": best_dept_name,
            "is_active": is_active_flag,
            "weight": max_weight,
            "location": best_location,
        }, update_modified=False)

        duplicate_names = [d.name for d in depts if d.name != primary_name]
        for dup_name in duplicate_names:
            child_doctypes = [
                ("KPI Definition", "department"),
                ("KPI Data Entry", "department"),
                ("KPI Alert", "department"),
                ("KPI Prediction", "department"),
                ("KPI User Assignment", "department"),
                ("KPI Operational Table", "department"),
                ("Machine", "department"),
            ]
            for dt, field in child_doctypes:
                try:
                    if frappe.db.table_exists(f"tab{dt}"):
                        frappe.db.sql(f"""
                            UPDATE `tab{dt}`
                            SET `{field}` = %s
                            WHERE `{field}` = %s
                        """, (primary_name, dup_name))
                except Exception:
                    pass

            try:
                frappe.db.sql("DELETE FROM `tabKPI Department` WHERE name = %s", (dup_name,))
            except Exception:
                pass

    frappe.db.commit()


@frappe.whitelist()
def get_setup_status():
    from productix_kpi.kpi_tracking.api.dashboard import _check_kpi_access
    role = _check_kpi_access()
    if role not in ("KPI Admin",) and "System Manager" not in frappe.get_roles():
        frappe.throw("Only admins can view setup status", frappe.PermissionError)

    # Clean up duplicate departments first
    try:
        consolidate_duplicate_departments()
    except Exception:
        pass

    settings = frappe.get_cached_doc("KPI Settings")
    dept_count = frappe.db.count("KPI Department", {"is_active": 1})
    user_count = frappe.db.count("KPI User Assignment", {"is_active": 1})
    template_count = frappe.db.count("KPI Template", {"is_active": 1})
    kpi_count = frappe.db.count("KPI Definition", {"is_active": 1})
    kpis_without_target = frappe.db.count("KPI Definition", {"is_active": 1, "target_value": 0})
    variable_count = frappe.db.count("KPI Variable")
    formula_count = frappe.db.count("KPI Formula", {"is_active": 1})
    op_table_count = frappe.db.count("KPI Operational Table", {"is_active": 1})

    # Fetch all existing departments with live KPI counts
    raw_departments = frappe.get_all(
        "KPI Department",
        fields=["name", "department_name", "department_code", "is_active", "weight", "description", "location"],
        order_by="department_name asc",
    )
    dept_kpis = frappe.db.sql("""
        SELECT department, COUNT(name) as count
        FROM `tabKPI Definition`
        WHERE is_active = 1
        GROUP BY department
    """, as_dict=True)
    kpi_count_map = {d.department: d.count for d in dept_kpis}

    seen = set()
    departments = []
    for d in raw_departments:
        code_key = (d.department_code or d.name or "").upper().strip()
        if code_key in seen:
            continue
        seen.add(code_key)
        d["kpi_count"] = kpi_count_map.get(d.name, 0)
        departments.append(d)

    companies = frappe.get_all("Company", fields=["name", "company_name", "default_currency", "country"], order_by="creation desc")
    fiscal_years = frappe.get_all("Fiscal Year", fields=["name"], order_by="year_start_date desc")

    # Priority popular currencies with PKR prominent
    popular_currencies = ["PKR", "USD", "EUR", "GBP", "AED", "SAR", "INR", "CAD"]
    db_currencies = frappe.get_all("Currency", fields=["name"], order_by="name asc", limit=150)
    db_curr_names = [c.name for c in db_currencies]
    all_currencies = [c for c in popular_currencies if c in db_curr_names] + [c for c in db_curr_names if c not in popular_currencies]
    if "PKR" not in all_currencies:
        all_currencies.insert(0, "PKR")
    elif all_currencies[0] != "PKR":
        all_currencies.remove("PKR")
        all_currencies.insert(0, "PKR")

    default_company = settings.company or (companies[0].name if companies else "")
    default_fiscal_year = settings.fiscal_year or (fiscal_years[0].name if fiscal_years else "2026")
    default_currency = settings.currency or (companies[0].default_currency if (companies and companies[0].default_currency) else "PKR") or "PKR"
    default_frequency = settings.default_frequency or "Daily"

    steps = [
        {"step": "Company", "status": "complete" if settings.company else "pending", "value": settings.company},
        {"step": "Departments", "status": "complete" if dept_count > 0 else "pending", "count": dept_count},
        {"step": "Users", "status": "complete" if user_count > 0 else "pending", "count": user_count},
        {"step": "Variables", "status": "complete" if variable_count > 0 else "pending", "count": variable_count},
        {"step": "Operational Tables", "status": "complete" if op_table_count > 0 else "pending", "count": op_table_count},
        {"step": "Formulas", "status": "complete" if formula_count > 0 else "pending", "count": formula_count},
        {"step": "KPI Templates", "status": "complete" if template_count > 0 else "pending", "count": template_count},
        {
            "step": "KPIs",
            "status": "warning" if kpis_without_target > 0 else ("complete" if kpi_count > 0 else "pending"),
            "count": kpi_count,
            "warning": f"{kpis_without_target} need targets" if kpis_without_target else None,
        },
        {"step": "Dashboard", "status": "complete" if kpi_count > 0 and dept_count > 0 else "pending"},
    ]

    completed = sum(1 for s in steps if s["status"] == "complete")
    total = len(steps)

    return {
        "steps": steps,
        "completed": completed,
        "total": total,
        "percentage": round(completed / total * 100) if total else 0,
        "setup_completed": settings.setup_completed or 0,
        "settings": {
            "company": settings.company or default_company,
            "fiscal_year": settings.fiscal_year or default_fiscal_year,
            "currency": settings.currency or default_currency or "PKR",
            "default_frequency": settings.default_frequency or "Daily",
        },
        "companies": [c.name for c in companies],
        "fiscal_years": [f.name for f in fiscal_years],
        "currencies": all_currencies,
        "departments": departments,
    }


@frappe.whitelist()
def setup_company(company, fiscal_year=None, currency=None, default_frequency="Daily"):
    from productix_kpi.kpi_tracking.api.dashboard import _check_kpi_access
    role = _check_kpi_access()
    if role != "KPI Admin" and "System Manager" not in frappe.get_roles():
        frappe.throw("Only admins can configure settings", frappe.PermissionError)

    if not company:
        frappe.throw("Company name is required")

    default_frequency = default_frequency or "Daily"
    company_name = company.strip()
    if not frappe.db.exists("Company", company_name):
        words = [w for w in company_name.split() if w]
        abbr = "".join(w[0].upper() for w in words)
        if len(abbr) < 2:
            abbr = (company_name[:3]).upper().replace(" ", "")

        existing_abbr = frappe.db.get_value("Company", {"abbr": abbr}, "name")
        if existing_abbr:
            abbr = f"{abbr[:3]}{frappe.db.count('Company') + 1}"

        default_currency = currency or frappe.db.get_single_value("Global Defaults", "default_currency") or "PKR"
        default_country = frappe.db.get_single_value("Global Defaults", "country") or "Pakistan"

        comp_doc = frappe.get_doc({
            "doctype": "Company",
            "company_name": company_name,
            "abbr": abbr,
            "default_currency": default_currency,
            "country": default_country,
        })
        comp_doc.insert(ignore_permissions=True)
        company_name = comp_doc.name

    if not frappe.db.get_single_value("Global Defaults", "default_company"):
        frappe.db.set_single_value("Global Defaults", "default_company", company_name)

    if not fiscal_year:
        fiscal_year = frappe.db.get_value("Fiscal Year", {}, "name", order_by="year_start_date desc") or "2026"

    if not currency:
        currency = frappe.db.get_value("Company", company_name, "default_currency") or "PKR"

    # Also update company currency if specified
    if currency and frappe.db.exists("Company", company_name):
        try:
            frappe.db.set_value("Company", company_name, "default_currency", currency)
        except Exception:
            pass

    settings = frappe.get_doc("KPI Settings")
    settings.company = company_name
    settings.fiscal_year = fiscal_year
    settings.currency = currency or "PKR"
    settings.default_frequency = default_frequency
    settings.save(ignore_permissions=True)

    return {
        "status": "ok",
        "company": company_name,
        "fiscal_year": fiscal_year,
        "currency": currency,
        "default_frequency": default_frequency,
    }


TEMPLATE_CODE_MAP = {
    "SALES": ["SALES", "Sales", "DEP_SALES"],
    "PRODUCTION": ["PRODUCTION", "Production", "DEP_PRODUCTION", "PROD"],
    "QC": ["QC", "Quality Control", "Quality Assurance & Control", "QUALITY_CONTROL", "QUALITY", "DEP_QC"],
    "SAFETY": ["SAFETY", "Safety", "EHS", "DEP_SAFETY"],
    "PROCUREMENT": ["PROCUREMENT", "Procurement", "Purchasing", "DEP_PROCUREMENT"],
    "SUPPLY_CHAIN": ["SUPPLY_CHAIN", "Supply Chain", "Logistics", "DEP_SUPPLY_CHAIN", "SC"],
    "RND": ["RND", "R&D", "Research & Development", "RD", "DEP_RND"],
    "FINANCE": ["FINANCE", "Finance", "Accounting", "ACCOUNTS", "DEP_FINANCE", "FIN"],
    "HR": ["HR", "Human Resources", "HUMAN_RESOURCES", "DEP_HR"],
    "CUSTOMER_SUCCESS": ["CUSTOMER_SUCCESS", "Customer Support & Success", "Customer Success", "Customer Support", "Support", "CS", "DEP_CUSTOMER_SUCCESS", "CUSTOMER_SUPPORT"],
}


@frappe.whitelist()
def setup_departments(departments):
    """
    Create or activate/update multiple operational departments safely.
    Handles code sanitization, duplicate lookup, and status/weight synchronization.
    Supports location/block disambiguation.
    """
    from productix_kpi.kpi_tracking.api.dashboard import _check_kpi_access
    role = _check_kpi_access()
    if role != "KPI Admin" and "System Manager" not in frappe.get_roles():
        frappe.throw("Only admins can create or update departments", frappe.PermissionError)

    # First clean up any existing duplicate records in database
    consolidate_duplicate_departments()

    if isinstance(departments, str):
        departments = json.loads(departments)

    created = []
    for dept in departments:
        name = (dept.get("name") or dept.get("department_name") or "").strip()
        raw_code = (dept.get("code") or dept.get("department_code") or "").strip()
        code = _clean_department_code(raw_code or name)
        name = name or code

        weight = float(dept.get("weight") or 1.0)
        is_active = 1 if int(dept.get("is_active", 1)) else 0
        desc = dept.get("description", "")
        loc = (dept.get("location") or "").strip()

        # Look for existing department strictly by primary key name or department_code
        existing_names = frappe.db.sql("""
            SELECT name FROM `tabKPI Department`
            WHERE name = %s OR department_code = %s
        """, (code, code), as_dict=True)

        if existing_names:
            for en in existing_names:
                doc = frappe.get_doc("KPI Department", en.name)
                doc.department_name = name
                doc.department_code = code
                doc.weight = weight
                doc.is_active = is_active
                if loc:
                    doc.location = loc
                if desc:
                    doc.description = desc
                doc.save(ignore_permissions=True)
                if doc.name not in created:
                    created.append(doc.name)
        else:
            doc = frappe.get_doc({
                "doctype": "KPI Department",
                "department_name": name,
                "department_code": code,
                "location": loc,
                "description": desc,
                "is_active": is_active,
                "weight": weight,
            })
            doc.insert(ignore_permissions=True)
            created.append(doc.name)

    frappe.db.commit()
    return {"created": created, "count": len(created)}


@frappe.whitelist()
def create_or_update_department(department_name, department_code=None, weight=1.0, is_active=1, description=None, location=None):
    """Create or update a single KPI Department with automatic code validation, location disambiguation, and duplicate protection."""
    from productix_kpi.kpi_tracking.api.dashboard import _check_kpi_access
    role = _check_kpi_access()
    if role != "KPI Admin" and "System Manager" not in frappe.get_roles():
        frappe.throw("Only admins can manage departments", frappe.PermissionError)

    department_name = (department_name or "").strip()
    if not department_name:
        frappe.throw("Department Name is required")

    code = _clean_department_code(department_code or department_name)
    weight = float(weight or 1.0)
    is_active_int = 1 if int(is_active) else 0
    loc = (location or "").strip()

    # Look for existing department strictly by primary key name or department_code
    existing_names = frappe.db.sql("""
        SELECT name FROM `tabKPI Department`
        WHERE name = %s OR department_code = %s
    """, (code, code), as_dict=True)

    if existing_names:
        for en in existing_names:
            doc = frappe.get_doc("KPI Department", en.name)
            doc.department_name = department_name
            doc.department_code = code
            doc.weight = weight
            doc.is_active = is_active_int
            if loc:
                doc.location = loc
            if description is not None:
                doc.description = description
            doc.save(ignore_permissions=True)
    else:
        doc = frappe.get_doc({
            "doctype": "KPI Department",
            "department_name": department_name,
            "department_code": code,
            "location": loc,
            "weight": weight,
            "is_active": is_active_int,
            "description": description or "",
        })
        doc.insert(ignore_permissions=True)

    frappe.db.commit()
    return {
        "status": "ok",
        "name": doc.name,
        "department_name": doc.department_name,
        "department_code": doc.department_code,
        "location": doc.location,
        "is_active": doc.is_active,
        "weight": doc.weight,
    }


@frappe.whitelist()
def toggle_department_active(department, is_active=None):
    """Toggle or set the active status of a KPI Department."""
    from productix_kpi.kpi_tracking.api.dashboard import _check_kpi_access
    role = _check_kpi_access()
    if role != "KPI Admin" and "System Manager" not in frappe.get_roles():
        frappe.throw("Only admins can toggle department status", frappe.PermissionError)

    consolidate_duplicate_departments()

    code = _clean_department_code(department)
    matching_names = frappe.db.sql("""
        SELECT name FROM `tabKPI Department`
        WHERE name = %s OR department_code = %s
    """, (department, code), as_dict=True)

    if not matching_names:
        frappe.throw(f"Department '{department}' does not exist.", frappe.DoesNotExistError)

    first_doc = None
    for item in matching_names:
        doc = frappe.get_doc("KPI Department", item.name)
        if is_active is None:
            doc.is_active = 0 if doc.is_active else 1
        else:
            doc.is_active = 1 if int(is_active) else 0
        doc.save(ignore_permissions=True)
        if not first_doc:
            first_doc = doc

    frappe.db.commit()

    return {
        "status": "ok",
        "name": first_doc.name,
        "department_name": first_doc.department_name,
        "location": first_doc.location,
        "is_active": first_doc.is_active,
    }


@frappe.whitelist()
def apply_kpi_template(template_code, department, selected_items=None):
    from productix_kpi.kpi_tracking.api.dashboard import _check_kpi_access
    _check_kpi_access()

    if selected_items and isinstance(selected_items, str):
        selected_items = json.loads(selected_items)

    template = frappe.get_doc("KPI Template", template_code)
    created = template.apply_template(department, selected_items)
    return {"created": created, "count": len(created)}


@frappe.whitelist()
def create_default_templates():
    from productix_kpi.kpi_tracking.api.dashboard import _check_kpi_access
    role = _check_kpi_access()
    if role != "KPI Admin" and "System Manager" not in frappe.get_roles():
        frappe.throw("Only admins can create templates", frappe.PermissionError)

    default_freq = frappe.db.get_single_value("KPI Settings", "default_frequency") or "Daily"

    templates = {
        "SALES": {
            "name": "Sales KPI Template",
            "items": [
                {"kpi_name": "Revenue", "measurement_type": "Currency", "default_frequency": default_freq, "direction": "Higher is Better", "default_target": 150000},
                {"kpi_name": "Sales Growth", "measurement_type": "Percentage", "default_frequency": default_freq, "direction": "Higher is Better", "default_target": 10},
                {"kpi_name": "New Customers", "measurement_type": "Integer", "default_frequency": default_freq, "direction": "Higher is Better", "default_target": 15},
                {"kpi_name": "Conversion Rate", "measurement_type": "Percentage", "default_frequency": default_freq, "direction": "Higher is Better", "default_target": 25},
                {"kpi_name": "Average Deal Size", "measurement_type": "Currency", "default_frequency": default_freq, "direction": "Higher is Better", "default_target": 5000},
                {"kpi_name": "Customer Retention", "measurement_type": "Percentage", "default_frequency": default_freq, "direction": "Higher is Better", "default_target": 90},
            ],
        },
        "PRODUCTION": {
            "name": "Production KPI Template",
            "items": [
                {"kpi_name": "Production Quantity", "measurement_type": "Number", "default_frequency": default_freq, "direction": "Higher is Better", "default_target": 5000},
                {"kpi_name": "Production Efficiency", "measurement_type": "Percentage", "default_frequency": default_freq, "direction": "Higher is Better", "default_target": 95},
                {"kpi_name": "Downtime", "measurement_type": "Duration", "default_frequency": default_freq, "direction": "Lower is Better", "default_target": 8},
                {"kpi_name": "Rejection Rate", "measurement_type": "Percentage", "default_frequency": default_freq, "direction": "Lower is Better", "default_target": 2},
                {"kpi_name": "Capacity Utilization", "measurement_type": "Percentage", "default_frequency": default_freq, "direction": "Higher is Better", "default_target": 85},
            ],
        },
        "QC": {
            "name": "QC KPI Template",
            "items": [
                {"kpi_name": "Defect Rate", "measurement_type": "Percentage", "default_frequency": default_freq, "direction": "Lower is Better", "default_target": 1.5},
                {"kpi_name": "First Pass Yield", "measurement_type": "Percentage", "default_frequency": default_freq, "direction": "Higher is Better", "default_target": 98},
                {"kpi_name": "Inspection Completion", "measurement_type": "Percentage", "default_frequency": default_freq, "direction": "Higher is Better", "default_target": 100},
            ],
        },
        "SAFETY": {
            "name": "Safety KPI Template",
            "items": [
                {"kpi_name": "Incidents", "measurement_type": "Integer", "default_frequency": default_freq, "direction": "Lower is Better", "default_target": 0},
                {"kpi_name": "Near Misses", "measurement_type": "Integer", "default_frequency": default_freq, "direction": "Lower is Better", "default_target": 2},
                {"kpi_name": "Safety Compliance", "measurement_type": "Percentage", "default_frequency": default_freq, "direction": "Higher is Better", "default_target": 100},
            ],
        },
        "PROCUREMENT": {
            "name": "Procurement KPI Template",
            "items": [
                {"kpi_name": "Purchase Cost", "measurement_type": "Currency", "default_frequency": default_freq, "direction": "Lower is Better", "default_target": 85000},
                {"kpi_name": "Supplier Performance", "measurement_type": "Percentage", "default_frequency": default_freq, "direction": "Higher is Better", "default_target": 95},
                {"kpi_name": "On-Time Delivery", "measurement_type": "Percentage", "default_frequency": default_freq, "direction": "Higher is Better", "default_target": 98},
            ],
        },
        "SUPPLY_CHAIN": {
            "name": "Supply Chain KPI Template",
            "items": [
                {"kpi_name": "On-Time Delivery", "measurement_type": "Percentage", "default_frequency": default_freq, "direction": "Higher is Better", "default_target": 96},
                {"kpi_name": "Inventory Turnover", "measurement_type": "Number", "default_frequency": default_freq, "direction": "Higher is Better", "default_target": 6},
                {"kpi_name": "Stock Accuracy", "measurement_type": "Percentage", "default_frequency": default_freq, "direction": "Higher is Better", "default_target": 99},
            ],
        },
        "RND": {
            "name": "R&D KPI Template",
            "items": [
                {"kpi_name": "New Formulations Developed", "measurement_type": "Integer", "default_frequency": default_freq, "direction": "Higher is Better", "default_target": 4},
                {"kpi_name": "R&D Milestones Met", "measurement_type": "Percentage", "default_frequency": default_freq, "direction": "Higher is Better", "default_target": 95},
                {"kpi_name": "Batch Trial Success Rate", "measurement_type": "Percentage", "default_frequency": default_freq, "direction": "Higher is Better", "default_target": 92},
                {"kpi_name": "Formulation Cost Optimization", "measurement_type": "Percentage", "default_frequency": default_freq, "direction": "Higher is Better", "default_target": 5},
            ],
        },
        "FINANCE": {
            "name": "Finance KPI Template",
            "items": [
                {"kpi_name": "Operating Margin", "measurement_type": "Percentage", "default_frequency": default_freq, "direction": "Higher is Better", "default_target": 24},
                {"kpi_name": "Gross Profit Margin", "measurement_type": "Percentage", "default_frequency": default_freq, "direction": "Higher is Better", "default_target": 42},
                {"kpi_name": "Operating Cash Flow", "measurement_type": "Currency", "default_frequency": default_freq, "direction": "Higher is Better", "default_target": 500000},
                {"kpi_name": "Days Sales Outstanding", "measurement_type": "Duration", "default_frequency": default_freq, "direction": "Lower is Better", "default_target": 35},
                {"kpi_name": "Budget Variance", "measurement_type": "Percentage", "default_frequency": default_freq, "direction": "Lower is Better", "default_target": 3.0},
                {"kpi_name": "Operating Expense Ratio", "measurement_type": "Percentage", "default_frequency": default_freq, "direction": "Lower is Better", "default_target": 28},
                {"kpi_name": "EBITDA Margin", "measurement_type": "Percentage", "default_frequency": default_freq, "direction": "Higher is Better", "default_target": 26},
            ],
        },
        "HR": {
            "name": "Human Resources KPI Template",
            "items": [
                {"kpi_name": "Employee Retention Rate", "measurement_type": "Percentage", "default_frequency": default_freq, "direction": "Higher is Better", "default_target": 95},
                {"kpi_name": "Training Hours Completed", "measurement_type": "Number", "default_frequency": default_freq, "direction": "Higher is Better", "default_target": 250},
                {"kpi_name": "Absenteeism Rate", "measurement_type": "Percentage", "default_frequency": default_freq, "direction": "Lower is Better", "default_target": 2.0},
                {"kpi_name": "Time-to-Fill Key Roles", "measurement_type": "Duration", "default_frequency": default_freq, "direction": "Lower is Better", "default_target": 20},
            ],
        },
        "CUSTOMER_SUCCESS": {
            "name": "Customer Support & Success KPI Template",
            "items": [
                {"kpi_name": "Customer Satisfaction Score", "measurement_type": "Percentage", "default_frequency": default_freq, "direction": "Higher is Better", "default_target": 92},
                {"kpi_name": "First Contact Resolution", "measurement_type": "Percentage", "default_frequency": default_freq, "direction": "Higher is Better", "default_target": 80},
                {"kpi_name": "Ticket Resolution Time", "measurement_type": "Duration", "default_frequency": default_freq, "direction": "Lower is Better", "default_target": 4},
                {"kpi_name": "Net Promoter Score", "measurement_type": "Number", "default_frequency": default_freq, "direction": "Higher is Better", "default_target": 65},
                {"kpi_name": "Customer Churn Rate", "measurement_type": "Percentage", "default_frequency": default_freq, "direction": "Lower is Better", "default_target": 2.0},
                {"kpi_name": "Ticket Escalation Rate", "measurement_type": "Percentage", "default_frequency": default_freq, "direction": "Lower is Better", "default_target": 5.0},
                {"kpi_name": "Customer Retention Rate", "measurement_type": "Percentage", "default_frequency": default_freq, "direction": "Higher is Better", "default_target": 95},
            ],
        },
    }

    created = []
    for code, tmpl in templates.items():
        if frappe.db.exists("KPI Template", code):
            doc = frappe.get_doc("KPI Template", code)
            existing_names = {i.kpi_name for i in doc.items}
            has_changes = False
            for item in tmpl["items"]:
                if item["kpi_name"] not in existing_names:
                    doc.append("items", item)
                    has_changes = True
            if has_changes:
                doc.save(ignore_permissions=True)
            created.append(code)
            continue

        doc = frappe.get_doc({
            "doctype": "KPI Template",
            "template_name": tmpl["name"],
            "template_code": code,
            "is_active": 1,
        })
        for item in tmpl["items"]:
            doc.append("items", item)
        doc.insert(ignore_permissions=True)
        created.append(code)

    return {"created": created}


@frappe.whitelist()
def apply_all_default_templates():
    from productix_kpi.kpi_tracking.api.dashboard import _check_kpi_access
    role = _check_kpi_access()
    if role != "KPI Admin" and "System Manager" not in frappe.get_roles():
        frappe.throw("Only admins can apply templates", frappe.PermissionError)

    create_default_templates()
    consolidate_duplicate_departments()

    active_depts = frappe.get_all(
        "KPI Department",
        filters={"is_active": 1},
        fields=["name", "department_name", "department_code"]
    )

    templates = frappe.get_all("KPI Template", filters={"is_active": 1}, fields=["name", "template_code", "template_name"])
    applied_templates = []
    total_kpis = []

    for dept in active_depts:
        matched_tmpl = None
        dept_name_norm = (dept.department_name or "").strip().lower()
        dept_code_norm = (dept.department_code or dept.name or "").strip().upper()

        for tmpl in templates:
            t_code = (tmpl.template_code or tmpl.name).upper()
            aliases = [a.lower() for a in TEMPLATE_CODE_MAP.get(t_code, [t_code])]
            if (dept_code_norm == t_code or
                dept_code_norm in [a.upper() for a in TEMPLATE_CODE_MAP.get(t_code, [])] or
                dept_name_norm in aliases or
                t_code in dept_code_norm or
                dept_code_norm in t_code):
                matched_tmpl = tmpl
                break

        if matched_tmpl:
            template_doc = frappe.get_doc("KPI Template", matched_tmpl.name)
            created = template_doc.apply_template(dept.name)
            total_kpis.extend(created)
            if matched_tmpl.name not in applied_templates:
                applied_templates.append(matched_tmpl.name)

    frappe.db.commit()
    return {"applied_templates": applied_templates, "created_kpis": total_kpis, "count": len(total_kpis)}


@frappe.whitelist()
def one_click_quick_setup(company_name=None, currency="PKR"):
    """One-click setup for admin: auto-configures Company, 10 Departments, Templates, and initial KPIs."""
    from productix_kpi.kpi_tracking.api.dashboard import _check_kpi_access
    role = _check_kpi_access()
    if role != "KPI Admin" and "System Manager" not in frappe.get_roles():
        frappe.throw("Only admins can run quick setup", frappe.PermissionError)

    # 1. Company with PKR / chosen currency
    companies = frappe.get_all("Company", pluck="name")
    chosen_company = company_name or (companies[0] if companies else None)
    if not chosen_company:
        chosen_company = frappe.db.get_single_value("Global Defaults", "default_company") or "Company"
    setup_company(chosen_company, currency=currency)

    # 2. All 10 Standard Departments
    all_10_depts = [
        {"name": "Production", "code": "PRODUCTION", "weight": 1.5, "is_active": 1},
        {"name": "Quality Control", "code": "QC", "weight": 1.3, "is_active": 1},
        {"name": "Safety", "code": "SAFETY", "weight": 1.0, "is_active": 1},
        {"name": "Procurement", "code": "PROCUREMENT", "weight": 1.0, "is_active": 1},
        {"name": "Supply Chain", "code": "SUPPLY_CHAIN", "weight": 1.1, "is_active": 1},
        {"name": "Sales", "code": "SALES", "weight": 1.2, "is_active": 1},
        {"name": "R&D", "code": "RND", "weight": 1.0, "is_active": 1},
        {"name": "Finance", "code": "FINANCE", "weight": 1.1, "is_active": 1},
        {"name": "Human Resources", "code": "HR", "weight": 1.0, "is_active": 1},
        {"name": "Customer Support & Success", "code": "CUSTOMER_SUCCESS", "weight": 1.1, "is_active": 1},
    ]
    setup_departments(all_10_depts)

    # 3. Templates & KPIs for all 10 departments
    create_default_templates()
    apply_res = apply_all_default_templates()

    # 4. Complete Setup
    settings = frappe.get_doc("KPI Settings")
    settings.setup_completed = 1
    settings.currency = currency
    settings.save(ignore_permissions=True)

    return {
        "status": "ok",
        "company": chosen_company,
        "currency": currency,
        "departments_count": len(all_10_depts),
        "kpis_created": apply_res.get("count", 0),
        "setup_completed": 1,
    }


def seed_default_kpis():
    """Seed all standard departments, templates, and baseline KPIs into the database."""
    frappe.set_user("Administrator")
    consolidate_duplicate_departments()
    all_10_depts = [
        {"name": "Production", "code": "PRODUCTION", "weight": 1.5, "is_active": 1},
        {"name": "Quality Control", "code": "QC", "weight": 1.3, "is_active": 1},
        {"name": "Safety", "code": "SAFETY", "weight": 1.0, "is_active": 1},
        {"name": "Procurement", "code": "PROCUREMENT", "weight": 1.0, "is_active": 1},
        {"name": "Supply Chain", "code": "SUPPLY_CHAIN", "weight": 1.1, "is_active": 1},
        {"name": "Sales", "code": "SALES", "weight": 1.2, "is_active": 1},
        {"name": "R&D", "code": "RND", "weight": 1.0, "is_active": 1},
        {"name": "Finance", "code": "FINANCE", "weight": 1.1, "is_active": 1},
        {"name": "Human Resources", "code": "HR", "weight": 1.0, "is_active": 1},
        {"name": "Customer Support & Success", "code": "CUSTOMER_SUCCESS", "weight": 1.1, "is_active": 1},
    ]
    setup_departments(all_10_depts)
    create_default_templates()
    return apply_all_default_templates()

    # 4. Complete Setup
    settings = frappe.get_doc("KPI Settings")
    settings.setup_completed = 1
    settings.currency = currency
    settings.save(ignore_permissions=True)

    return {
        "status": "ok",
        "company": chosen_company,
        "currency": currency,
        "departments_count": len(all_9_depts),
        "kpis_created": apply_res.get("count", 0),
        "setup_completed": 1,
    }


@frappe.whitelist()
def complete_setup():
    from productix_kpi.kpi_tracking.api.dashboard import _check_kpi_access
    role = _check_kpi_access()
    if role != "KPI Admin" and "System Manager" not in frappe.get_roles():
        frappe.throw("Only admins can complete setup", frappe.PermissionError)

    settings = frappe.get_doc("KPI Settings")
    settings.setup_completed = 1
    settings.save(ignore_permissions=True)
    return {"status": "ok"}
