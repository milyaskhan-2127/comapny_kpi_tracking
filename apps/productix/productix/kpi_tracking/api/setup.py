import frappe
import json


@frappe.whitelist()
def get_setup_status():
    from productix.kpi_tracking.api.dashboard import _check_kpi_access
    role = _check_kpi_access()
    if role not in ("KPI Admin",) and "System Manager" not in frappe.get_roles():
        frappe.throw("Only admins can view setup status", frappe.PermissionError)

    settings = frappe.get_cached_doc("KPI Settings")
    dept_count = frappe.db.count("KPI Department", {"is_active": 1})
    user_count = frappe.db.count("KPI User Assignment", {"is_active": 1})
    template_count = frappe.db.count("KPI Template", {"is_active": 1})
    kpi_count = frappe.db.count("KPI Definition", {"is_active": 1})
    kpis_without_target = frappe.db.count("KPI Definition", {"is_active": 1, "target_value": 0})
    variable_count = frappe.db.count("KPI Variable")
    formula_count = frappe.db.count("KPI Formula", {"is_active": 1})
    op_table_count = frappe.db.count("KPI Operational Table", {"is_active": 1})

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
    }


@frappe.whitelist()
def setup_company(company, fiscal_year=None, currency=None, default_frequency="Daily"):
    from productix.kpi_tracking.api.dashboard import _check_kpi_access
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

    # Dynamically sync all active KPI Definitions and Template Items to the chosen Company Frequency
    try:
        frappe.db.sql(
            "UPDATE `tabKPI Definition` SET frequency = %s WHERE is_active = 1",
            (default_frequency,)
        )
        frappe.db.sql(
            "UPDATE `tabKPI Template Item` SET default_frequency = %s",
            (default_frequency,)
        )
        frappe.db.commit()
        frappe.clear_cache()
    except Exception:
        pass

    return {
        "status": "ok",
        "company": company_name,
        "fiscal_year": fiscal_year,
        "currency": currency,
        "default_frequency": default_frequency,
    }


@frappe.whitelist()
def setup_departments(departments):
    from productix.kpi_tracking.api.dashboard import _check_kpi_access
    role = _check_kpi_access()
    if role != "KPI Admin" and "System Manager" not in frappe.get_roles():
        frappe.throw("Only admins can create departments", frappe.PermissionError)

    if isinstance(departments, str):
        departments = json.loads(departments)

    created = []
    for dept in departments:
        code = dept.get("code") or dept.get("name", "").upper().replace(" ", "_")
        weight = float(dept.get("weight") or 1.0)
        name = dept.get("name") or code

        if frappe.db.exists("KPI Department", code):
            # Ensure it is active with proper weight
            frappe.db.set_value("KPI Department", code, {"is_active": 1, "weight": weight, "department_name": name})
            created.append(code)
            continue

        doc = frappe.get_doc({
            "doctype": "KPI Department",
            "department_name": name,
            "department_code": code,
            "description": dept.get("description", ""),
            "is_active": 1,
            "weight": weight,
        })
        doc.insert(ignore_permissions=True)
        created.append(doc.name)

    frappe.db.commit()
    return {"created": created}


@frappe.whitelist()
def apply_kpi_template(template_code, department, selected_items=None):
    from productix.kpi_tracking.api.dashboard import _check_kpi_access
    _check_kpi_access()

    if selected_items and isinstance(selected_items, str):
        selected_items = json.loads(selected_items)

    template = frappe.get_doc("KPI Template", template_code)
    created = template.apply_template(department, selected_items)
    return {"created": created, "count": len(created)}


@frappe.whitelist()
def create_default_templates():
    from productix.kpi_tracking.api.dashboard import _check_kpi_access
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
                {"kpi_name": "Operating Margin", "measurement_type": "Percentage", "default_frequency": default_freq, "direction": "Higher is Better", "default_target": 22},
                {"kpi_name": "Budget Variance", "measurement_type": "Percentage", "default_frequency": default_freq, "direction": "Lower is Better", "default_target": 3},
                {"kpi_name": "Operating Cash Flow", "measurement_type": "Currency", "default_frequency": default_freq, "direction": "Higher is Better", "default_target": 250000},
                {"kpi_name": "Days Sales Outstanding", "measurement_type": "Duration", "default_frequency": default_freq, "direction": "Lower is Better", "default_target": 35},
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
    }

    created = []
    for code, tmpl in templates.items():
        if frappe.db.exists("KPI Template", code):
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
    from productix.kpi_tracking.api.dashboard import _check_kpi_access
    role = _check_kpi_access()
    if role != "KPI Admin" and "System Manager" not in frappe.get_roles():
        frappe.throw("Only admins can apply templates", frappe.PermissionError)

    create_default_templates()
    templates = frappe.get_all("KPI Template", filters={"is_active": 1}, pluck="name")
    total_kpis = []

    for tmpl_code in templates:
        if frappe.db.exists("KPI Department", tmpl_code):
            template = frappe.get_doc("KPI Template", tmpl_code)
            created = template.apply_template(tmpl_code)
            total_kpis.extend(created)

    return {"applied_templates": templates, "created_kpis": total_kpis, "count": len(total_kpis)}


@frappe.whitelist()
def one_click_quick_setup(company_name=None, currency="PKR"):
    """One-click setup for admin: auto-configures Company, 9 Departments, Templates, and initial KPIs."""
    from productix.kpi_tracking.api.dashboard import _check_kpi_access
    role = _check_kpi_access()
    if role != "KPI Admin" and "System Manager" not in frappe.get_roles():
        frappe.throw("Only admins can run quick setup", frappe.PermissionError)

    # 1. Company with PKR / chosen currency
    companies = frappe.get_all("Company", pluck="name")
    chosen_company = company_name or (companies[0] if companies else "Apex Chemical Industries")
    setup_company(chosen_company, currency=currency)

    # 2. All 9 Departments
    all_9_depts = [
        {"name": "Production", "code": "PRODUCTION", "weight": 1.5},
        {"name": "Quality Control", "code": "QC", "weight": 1.3},
        {"name": "Safety", "code": "SAFETY", "weight": 1.0},
        {"name": "Procurement", "code": "PROCUREMENT", "weight": 1.0},
        {"name": "Supply Chain", "code": "SUPPLY_CHAIN", "weight": 1.1},
        {"name": "Sales", "code": "SALES", "weight": 1.2},
        {"name": "R&D", "code": "RND", "weight": 1.0},
        {"name": "Finance", "code": "FINANCE", "weight": 1.1},
        {"name": "Human Resources", "code": "HR", "weight": 1.0},
    ]
    setup_departments(all_9_depts)

    # 3. Templates & KPIs for all 9 departments
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
        "departments_count": len(all_9_depts),
        "kpis_created": apply_res.get("count", 0),
        "setup_completed": 1,
    }


@frappe.whitelist()
def complete_setup():
    from productix.kpi_tracking.api.dashboard import _check_kpi_access
    role = _check_kpi_access()
    if role != "KPI Admin" and "System Manager" not in frappe.get_roles():
        frappe.throw("Only admins can complete setup", frappe.PermissionError)

    settings = frappe.get_doc("KPI Settings")
    settings.setup_completed = 1
    settings.save(ignore_permissions=True)
    return {"status": "ok"}
