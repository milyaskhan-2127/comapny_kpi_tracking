import frappe
import json
from frappe.utils import today, getdate


def _get_period_for_frequency(freq, d=None):
    d = getdate(d) if d else getdate(today())
    if freq == "Daily":
        return d.strftime("%Y-%m-%d")
    elif freq == "Weekly":
        iso = d.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    elif freq == "Monthly":
        return d.strftime("%Y-%m")
    elif freq == "Quarterly":
        q = (d.month - 1) // 3 + 1
        return f"{d.year}-Q{q}"
    elif freq == "Yearly":
        return str(d.year)
    return d.strftime("%Y-%m")


@frappe.whitelist()
def get_pending_kpis(department=None, frequency=None, period=None):
    from productix.kpi_tracking.api.dashboard import _check_kpi_access, _get_user_departments
    role = _check_kpi_access()

    user_depts = _get_user_departments()
    if not user_depts:
        return []

    if department and department not in ("All", "ALL", "All Departments"):
        if department not in user_depts:
            frappe.throw(f"Access denied: You do not have permission for department '{department}'.", frappe.PermissionError)
        target_depts = [department]
    else:
        target_depts = user_depts if role == "KPI Admin" else ([user_depts[0]] if user_depts else [])

    company_freq = frappe.db.get_single_value("KPI Settings", "default_frequency") or "Daily"
    active_freq = frequency if (frequency and frequency != "All") else company_freq

    filters = {"is_active": 1, "department": ["in", target_depts]}
    if active_freq and active_freq != "All":
        filters["frequency"] = active_freq

    kpis = frappe.db.get_all(
        "KPI Definition",
        filters=filters,
        fields=["name", "kpi_name", "kpi_code", "department", "frequency",
                "target_value", "measurement_type", "unit", "source_type",
                "direction", "warning_threshold", "critical_threshold"],
        order_by="kpi_name asc",
    )

    d = getdate(today())
    results = []

    for kpi in kpis:
        freq = kpi.frequency or active_freq or company_freq
        target_period = period if period else _get_period_for_frequency(freq, d)

        # Check for existing submitted entry
        existing_entry = frappe.db.get_value(
            "KPI Data Entry",
            {"kpi": kpi.name, "department": kpi.department, "period": target_period, "docstatus": 1},
            ["name", "actual_value", "achievement_percentage", "status", "entry_date", "entered_by"],
            as_dict=True,
        )

        inputs = frappe.db.get_all(
            "KPI Input Definition",
            filters={"parent": kpi.name, "parenttype": "KPI Definition"},
            fields=["field_name", "label", "field_type", "is_required",
                    "minimum_value", "maximum_value", "unit"],
            order_by="calculation_order asc",
        )

        entered_by_name = ""
        if existing_entry and existing_entry.entered_by:
            entered_by_name = frappe.db.get_value("User", existing_entry.entered_by, "full_name") or existing_entry.entered_by

        results.append({
            "kpi": kpi.name,
            "kpi_name": kpi.kpi_name,
            "kpi_code": kpi.kpi_code or kpi.name,
            "department": kpi.department,
            "frequency": freq,
            "target": kpi.target_value,
            "measurement_type": kpi.measurement_type,
            "unit": kpi.unit or "",
            "period": target_period,
            "direction": kpi.direction or "Higher is Better",
            "submitted": bool(existing_entry),
            "submitted_value": existing_entry.actual_value if existing_entry else None,
            "achievement": existing_entry.achievement_percentage if existing_entry else None,
            "status": existing_entry.status if existing_entry else "Pending",
            "entered_by": existing_entry.entered_by if existing_entry else None,
            "entered_by_name": entered_by_name,
            "source_type": kpi.source_type,
            "inputs": inputs,
        })

    return results


@frappe.whitelist()
def submit_kpi_data(kpi, department, actual_value, entry_date=None,
                    input_values=None, customer=None, period=None):
    from productix.kpi_tracking.api.dashboard import _check_kpi_access, _get_user_departments
    _check_kpi_access()
    user_depts = _get_user_departments()

    if department not in user_depts:
        frappe.throw(f"Access denied: You are not authorized for department '{department}'.", frappe.PermissionError)

    kpi_doc = frappe.get_doc("KPI Definition", kpi)
    if kpi_doc.department != department:
        frappe.throw(f"KPI '{kpi}' does not belong to department '{department}'.", frappe.PermissionError)

    d_val = getdate(entry_date) if entry_date else getdate(today())
    target_period = period if period else _get_period_for_frequency(kpi_doc.frequency or "Monthly", d_val)

    # Check if entry exists for this KPI, dept, period
    existing_name = frappe.db.get_value(
        "KPI Data Entry",
        {
            "kpi": kpi,
            "department": department,
            "period": target_period,
            "customer": customer or "",
            "docstatus": ["<", 2],
        },
        "name"
    )

    if existing_name:
        doc = frappe.get_doc("KPI Data Entry", existing_name)
        if doc.docstatus == 1:
            doc.cancel()
            doc = frappe.get_doc({
                "doctype": "KPI Data Entry",
                "kpi": kpi,
                "department": department,
                "actual_value": float(actual_value),
                "entry_date": entry_date or today(),
                "period": target_period,
                "customer": customer,
                "entered_by": frappe.session.user,
            })
        else:
            doc.actual_value = float(actual_value)
            doc.entry_date = entry_date or today()
            doc.entered_by = frappe.session.user
    else:
        doc = frappe.get_doc({
            "doctype": "KPI Data Entry",
            "kpi": kpi,
            "department": department,
            "actual_value": float(actual_value),
            "entry_date": entry_date or today(),
            "period": target_period,
            "customer": customer,
            "entered_by": frappe.session.user,
        })

    if input_values:
        if isinstance(input_values, str):
            input_values = json.loads(input_values)
        doc.set("input_values", [])
        for iv in input_values:
            doc.append("input_values", iv)

    doc.save(ignore_permissions=True)
    doc.submit()

    return {
        "name": doc.name,
        "kpi": doc.kpi,
        "department": doc.department,
        "actual_value": doc.actual_value,
        "target_value": doc.target_value,
        "status": doc.status,
        "achievement": doc.achievement_percentage,
        "period": doc.period,
        "entered_by": doc.entered_by,
    }


@frappe.whitelist()
def get_data_entry_logs(department=None, frequency=None, period=None, limit=50, page=1):
    from productix.kpi_tracking.api.dashboard import _check_kpi_access, _get_user_departments
    role = _check_kpi_access()
    user_depts = _get_user_departments()

    if not user_depts:
        return {"logs": [], "total": 0}

    filters = {"docstatus": 1}

    if role != "KPI Admin":
        # Force employee department isolation
        filters["department"] = ["in", user_depts]
    else:
        if department and department in user_depts:
            filters["department"] = department
        else:
            filters["department"] = ["in", user_depts]

    if period:
        filters["period"] = period

    limit = int(limit or 50)
    page = int(page or 1)
    offset = (page - 1) * limit

    entries = frappe.db.get_all(
        "KPI Data Entry",
        filters=filters,
        fields=["name", "kpi", "department", "actual_value", "target_value",
                "achievement_percentage", "status", "period", "entry_date",
                "entered_by", "creation"],
        order_by="creation desc",
        limit_page_length=limit,
        limit_start=offset,
    )

    total_count = frappe.db.count("KPI Data Entry", filters=filters)

    # Gather user display names
    users = {e.entered_by for e in entries if e.entered_by}
    user_names = {}
    if users:
        for u in frappe.db.get_all("User", filters={"name": ["in", list(users)]}, fields=["name", "full_name"]):
            user_names[u.name] = u.full_name or u.name

    # Gather KPI names
    kpi_codes = {e.kpi for e in entries if e.kpi}
    kpi_names = {}
    kpi_freqs = {}
    if kpi_codes:
        for k in frappe.db.get_all("KPI Definition", filters={"name": ["in", list(kpi_codes)]}, fields=["name", "kpi_name", "frequency"]):
            kpi_names[k.name] = k.kpi_name
            kpi_freqs[k.name] = k.frequency

    # Gather Department names
    dept_codes = {e.department for e in entries if e.department}
    dept_names = {}
    if dept_codes:
        for d in frappe.db.get_all("KPI Department", filters={"name": ["in", list(dept_codes)]}, fields=["name", "department_name"]):
            dept_names[d.name] = d.department_name

    logs = []
    for e in entries:
        logs.append({
            "name": e.name,
            "kpi": e.kpi,
            "kpi_name": kpi_names.get(e.kpi, e.kpi),
            "department": e.department,
            "department_name": dept_names.get(e.department, e.department),
            "actual_value": e.actual_value,
            "target_value": e.target_value,
            "achievement": e.achievement_percentage,
            "status": e.status,
            "frequency": kpi_freqs.get(e.kpi, "Monthly"),
            "period": e.period,
            "entry_date": e.entry_date,
            "entered_by": e.entered_by,
            "entered_by_name": user_names.get(e.entered_by, e.entered_by or "System"),
            "timestamp": e.creation,
        })

    return {
        "logs": logs,
        "total": total_count,
        "page": page,
        "limit": limit,
    }


@frappe.whitelist()
def get_data_entry_monitoring(frequency=None, period=None):
    """Admin page overview of which departments have submitted data and which are missing."""
    from productix.kpi_tracking.api.dashboard import _check_kpi_access
    role = _check_kpi_access()
    if role != "KPI Admin":
        frappe.throw("Access denied: Admin monitoring is restricted to administrators.", frappe.PermissionError)

    company_freq = frappe.db.get_single_value("KPI Settings", "default_frequency") or "Daily"
    active_freq = frequency if (frequency and frequency != "All") else company_freq

    d = getdate(today())
    target_period = period if period else _get_period_for_frequency(active_freq, d)

    departments = frappe.db.get_all(
        "KPI Department",
        filters={"is_active": 1},
        fields=["name", "department_name", "weight"],
        order_by="department_name asc",
    )

    overview = []
    total_required = 0
    total_completed = 0
    total_missing = 0

    for dept in departments:
        kpi_filters = {"department": dept.name, "is_active": 1}
        if active_freq and active_freq != "All":
            kpi_filters["frequency"] = active_freq

        dept_kpis = frappe.db.get_all("KPI Definition", filters=kpi_filters, fields=["name", "kpi_name", "frequency"])
        required_count = len(dept_kpis)

        # Submitted entries for this department and period
        submitted_entries = frappe.db.get_all(
            "KPI Data Entry",
            filters={"department": dept.name, "period": target_period, "docstatus": 1},
            fields=["kpi", "entry_date", "entered_by", "creation", "actual_value", "status"],
            order_by="creation desc",
        )

        completed_kpis = {e.kpi for e in submitted_entries}
        completed_count = len(completed_kpis)
        missing_count = max(0, required_count - completed_count)
        completion_pct = round((completed_count / required_count * 100), 1) if required_count > 0 else 0

        last_entry = submitted_entries[0] if submitted_entries else None
        last_entry_date = last_entry.entry_date if last_entry else None
        last_entered_by = last_entry.entered_by if last_entry else None
        last_entered_by_name = None
        if last_entered_by:
            last_entered_by_name = frappe.db.get_value("User", last_entered_by, "full_name") or last_entered_by

        # Find active employees assigned to this department
        employees = frappe.db.get_all(
            "KPI User Assignment",
            filters={"department": dept.name, "is_active": 1},
            fields=["user"],
        )
        employee_emails = [emp.user for emp in employees]
        employee_names = []
        if employee_emails:
            for u in frappe.db.get_all("User", filters={"name": ["in", employee_emails]}, fields=["name", "full_name"]):
                employee_names.append(u.full_name or u.name)

        total_required += required_count
        total_completed += completed_count
        total_missing += missing_count

        overview.append({
            "department": dept.department_name,
            "department_code": dept.name,
            "required_entries": required_count,
            "completed_entries": completed_count,
            "missing_entries": missing_count,
            "completion_percentage": completion_pct,
            "last_entry_date": last_entry_date,
            "last_entered_by": last_entered_by_name or ("None" if required_count > 0 and completed_count == 0 else "--"),
            "assigned_employees": employee_names,
            "assigned_count": len(employee_names),
            "period": target_period,
            "frequency": active_freq or "Daily",
            "is_complete": missing_count == 0 and required_count > 0,
        })

    overall_pct = round((total_completed / total_required * 100), 1) if total_required > 0 else 0

    return {
        "departments": overview,
        "summary": {
            "total_departments": len(departments),
            "total_required": total_required,
            "total_completed": total_completed,
            "total_missing": total_missing,
            "overall_completion_percentage": overall_pct,
            "period": target_period,
            "frequency": active_freq or "Daily",
        }
    }


@frappe.whitelist()
def get_operational_table_form(table_code):
    from productix.kpi_tracking.api.dashboard import _check_kpi_access
    role = _check_kpi_access()
    if role != "KPI Admin":
        frappe.throw("Access denied: Operational Tables are restricted to administrators.", frappe.PermissionError)

    table = frappe.get_doc("KPI Operational Table", table_code)
    variables = []
    for v in table.variables:
        var_doc = frappe.get_cached_doc("KPI Variable", v.variable)
        variables.append({
            "variable": v.variable,
            "variable_code": var_doc.variable_code,
            "label": v.variable_label or var_doc.get_display_name(),
            "type": var_doc.variable_type,
            "unit": var_doc.unit,
            "is_customer_specific": v.is_customer_specific,
            "allow_negative": var_doc.allow_negative,
            "decimal_precision": var_doc.decimal_precision,
        })

    customers = [{"customer": c.customer, "customer_name": c.customer_name}
                 for c in table.customers]

    return {"table": table.as_dict(), "variables": variables, "customers": customers}


@frappe.whitelist()
def submit_operational_data(table_code, department, entry_date, values, customer=None):
    from productix.kpi_tracking.api.dashboard import _check_kpi_access
    role = _check_kpi_access()
    if role != "KPI Admin":
        frappe.throw("Access denied: Operational Data Entry is restricted to administrators.", frappe.PermissionError)

    if isinstance(values, str):
        values = json.loads(values)

    table = frappe.get_doc("KPI Operational Table", table_code)

    doc = frappe.get_doc({
        "doctype": "KPI Operational Data",
        "operational_table": table_code,
        "department": department,
        "business_unit": table.business_unit,
        "entry_date": entry_date,
        "customer": customer,
    })

    for val in values:
        doc.append("values", val)

    doc.insert(ignore_permissions=True)
    doc.submit()

    return {"name": doc.name, "period": doc.period}
