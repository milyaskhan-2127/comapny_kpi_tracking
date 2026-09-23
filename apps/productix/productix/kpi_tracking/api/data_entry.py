import frappe
import json
from frappe.utils import today, getdate
from productix.kpi_tracking.services.period_engine import (
    get_current_period,
    resolve_canonical_period,
    get_submission_monitoring,
    calculate_normalized_score,
)


def _get_period_for_frequency(freq, d=None, ref_period=None):
    return resolve_canonical_period(freq, ref_period, d)


@frappe.whitelist()
def get_pending_kpis(department=None, frequency=None, period=None):
    from productix.kpi_tracking.api.dashboard import _check_kpi_access, _get_user_departments
    role = _check_kpi_access()

    user_depts = _get_user_departments()
    if not user_depts and role != "KPI Admin":
        return []

    if department and department not in ("All", "ALL", "All Departments"):
        if role != "KPI Admin" and department not in user_depts:
            frappe.throw(f"Access denied: You do not have permission for department '{department}'.", frappe.PermissionError)
        target_depts = [department]
    else:
        target_depts = user_depts if role == "KPI Admin" else ([user_depts[0]] if user_depts else [])

    filters = {"is_active": 1, "department": ["in", target_depts]}
    if frequency and frequency != "All":
        filters["frequency"] = frequency

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
        freq = kpi.frequency or "Monthly"
        target_period = resolve_canonical_period(freq, period, d)

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
    role = _check_kpi_access()
    user_depts = _get_user_departments()

    if role != "KPI Admin" and department not in user_depts:
        frappe.throw(f"Access denied: You are not authorized for department '{department}'.", frappe.PermissionError)

    kpi_doc = frappe.get_doc("KPI Definition", kpi)
    if kpi_doc.department != department:
        frappe.throw(f"KPI '{kpi}' does not belong to department '{department}'.", frappe.PermissionError)

    d_val = getdate(entry_date) if entry_date else getdate(today())
    target_period = resolve_canonical_period(kpi_doc.frequency or "Monthly", period, d_val)

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

    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
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


def _get_data_entry_monitoring_internal(frequency=None, period=None, department=None, departments=None):
    """Authoritative data entry submission monitoring using central Period Engine."""
    return get_submission_monitoring(frequency=frequency, period=period, department=department, departments=departments)


@frappe.whitelist()
def get_data_entry_monitoring(frequency=None, period=None):
    """Overview of which departments have submitted data and which are missing."""
    from productix.kpi_tracking.api.dashboard import _check_kpi_access
    from productix.kpi_tracking.security.permissions import get_ceo_authorized_departments
    role = _check_kpi_access()
    if role == "KPI Employee":
        frappe.throw("Access denied: Monitoring is restricted to administrators and CEOs.", frappe.PermissionError)

    ceo_depts = None
    if role == "KPI CEO":
        ceo_depts = get_ceo_authorized_departments()

    return _get_data_entry_monitoring_internal(frequency=frequency, period=period, departments=ceo_depts)


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
