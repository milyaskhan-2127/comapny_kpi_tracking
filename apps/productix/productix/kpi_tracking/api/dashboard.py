import frappe
from productix.kpi_tracking.security.permissions import (
    is_kpi_admin,
    get_user_authorized_department,
)


def _check_kpi_access(user=None):
    user = user or frappe.session.user
    if user == "Administrator":
        return "KPI Admin"

    if not frappe.db.get_value("User", user, "enabled"):
        frappe.throw("Your user account has been disabled. Please contact your administrator.", frappe.PermissionError)

    if is_kpi_admin(user):
        return "KPI Admin"

    roles = frappe.get_roles(user)
    if "KPI Employee" in roles or "KPI Manager" in roles or "KPI Contributor" in roles:
        return "KPI Employee"

    # Check if assignment exists
    has_active = frappe.db.exists("KPI User Assignment", {"user": user, "is_active": 1})
    if has_active:
        return "KPI Employee"

    # Check if employee record exists with department
    dept = get_user_authorized_department(user)
    if dept:
        return "KPI Employee"

    frappe.throw("You do not have access to KPI Tracking. Please contact your administrator.", frappe.PermissionError)


def _get_user_departments(user=None):
    user = user or frappe.session.user
    role = _check_kpi_access(user)
    if role == "KPI Admin":
        return frappe.db.get_all("KPI Department", filters={"is_active": 1}, pluck="name")

    departments = set()

    # 1. From User Assignment
    assigned_depts = frappe.db.get_all(
        "KPI User Assignment",
        filters={"user": user, "is_active": 1},
        pluck="department",
    )
    for d in assigned_depts:
        if d:
            departments.add(d)

    # 2. From Employee record
    emp_dept = get_user_authorized_department(user)
    if emp_dept:
        departments.add(emp_dept)

    if departments:
        active_depts = frappe.db.get_all(
            "KPI Department",
            filters={"name": ["in", list(departments)], "is_active": 1},
            pluck="name"
        )
        return active_depts

    return []


@frappe.whitelist()
def get_company_overview(timeframe="6_months", horizon="next_month", period=None, frequency=None):
    role = _check_kpi_access()
    if role != "KPI Admin":
        frappe.throw("Access denied: Company Performance Overview is restricted to administrators.", frappe.PermissionError)

    if not frequency or frequency == "All":
        frequency = frappe.db.get_single_value("KPI Settings", "default_frequency") or "Daily"

    from productix.kpi_tracking.services.analytics import get_company_performance
    perf = get_company_performance(timeframe=timeframe, horizon=horizon, period=period, frequency=frequency)

    alerts = frappe.db.get_all(
        "KPI Alert",
        filters={"status": ["in", ["Active", "Acknowledged"]]},
        fields=["severity", "count(name) as cnt"],
        group_by="severity",
    )
    perf["alerts_summary"] = {a.severity: a.cnt for a in alerts}
    perf["total_kpis"] = frappe.db.count("KPI Definition", {"is_active": 1})
    perf["total_users"] = frappe.db.count("KPI User Assignment", {"is_active": 1})

    from productix.kpi_tracking.api.data_entry import get_data_entry_monitoring
    perf["data_entry_monitoring"] = get_data_entry_monitoring(frequency=frequency, period=period)

    return perf


@frappe.whitelist()
def get_department_dashboard(department=None, timeframe="6_months", horizon="next_month", period=None, frequency=None):
    role = _check_kpi_access()
    user_depts = _get_user_departments()

    if not user_depts:
        frappe.throw("No active department found or assigned to your account.", frappe.PermissionError)

    # For non-admin employees, strictly enforce their authorized department
    if role != "KPI Admin":
        if not department or department not in user_depts:
            department = user_depts[0]
    else:
        if not department:
            department = user_depts[0]
        elif department not in user_depts and not frappe.db.exists("KPI Department", department):
            frappe.throw(f"Department '{department}' does not exist.", frappe.DoesNotExistError)

    if not frequency or frequency == "All":
        frequency = frappe.db.get_single_value("KPI Settings", "default_frequency") or "Daily"

    from productix.kpi_tracking.services.analytics import get_department_performance
    perf = get_department_performance(
        department, timeframe=timeframe, horizon=horizon,
        period=period, frequency=frequency
    )

    alert_filters = {"department": department, "status": ["in", ["Active", "Acknowledged"]]}
    alerts = frappe.db.get_all(
        "KPI Alert",
        filters=alert_filters,
        fields=["name", "kpi", "alert_type", "severity", "subject", "message", "trigger_period", "status", "creation"],
        order_by="creation desc", limit_page_length=10,
    )
    perf["alerts"] = alerts

    dept_doc = frappe.get_doc("KPI Department", department)
    perf["department_name"] = dept_doc.department_name or dept_doc.name
    perf["department_code"] = dept_doc.name
    perf["is_admin"] = (role == "KPI Admin")

    return perf


@frappe.whitelist()
def get_kpi_detail(kpi_code, timeframe="6_months", horizon="next_month"):
    role = _check_kpi_access()
    if not frappe.db.exists("KPI Definition", kpi_code):
        frappe.throw(f"KPI '{kpi_code}' does not exist.", frappe.DoesNotExistError)

    kpi = frappe.get_doc("KPI Definition", kpi_code)
    user_depts = _get_user_departments()
    if role != "KPI Admin" and kpi.department and kpi.department not in user_depts:
        frappe.throw(f"Access denied: You do not have permission to view KPI '{kpi_code}'.", frappe.PermissionError)

    from productix.kpi_tracking.services.analytics import (
        calculate_trend,
        calculate_growth,
        generate_multi_horizon_predictions,
    )

    period_limit = 6 if timeframe == "6_months" else (12 if timeframe == "overall" else (1 if timeframe in ("today", "recent") else 3))

    history = frappe.db.get_all(
        "KPI Data Entry",
        filters={"kpi": kpi_code, "docstatus": 1},
        fields=["name", "actual_value", "target_value", "achievement_percentage",
                "status", "entry_date", "period", "entered_by"],
        order_by="entry_date desc", limit_page_length=period_limit,
    )

    trend = calculate_trend(kpi_code, kpi.department, period_limit)
    growth = calculate_growth(kpi_code, kpi.department)
    multi_preds = generate_multi_horizon_predictions(kpi_code, kpi.department)

    predictions = frappe.db.get_all(
        "KPI Prediction",
        filters={"kpi": kpi_code},
        fields=["predicted_value", "actual_value", "variance", "variance_percentage",
                "accuracy", "status", "target_period", "confidence"],
        order_by="prediction_date desc", limit_page_length=6,
    )

    return {
        "kpi": kpi.as_dict(),
        "history": history,
        "trend": trend,
        "growth": growth,
        "predictions": predictions,
        "predictions_all": multi_preds,
        "selected_prediction": multi_preds.get(horizon) or multi_preds.get("next_month") if multi_preds.get("available") else None,
        "latest": history[0] if history else None,
    }


@frappe.whitelist()
def get_user_context():
    user = frappe.session.user
    role = _check_kpi_access(user)
    departments = _get_user_departments(user)

    department_list = []
    if departments:
        department_list = frappe.get_all(
            "KPI Department",
            filters={"name": ["in", departments], "is_active": 1},
            fields=["name", "department_name", "department_code", "weight"],
            order_by="department_name asc",
        )

    assigned_dept = departments[0] if (role != "KPI Admin" and departments) else None

    user_full_name = frappe.db.get_value("User", user, "full_name") or user

    default_freq = frappe.db.get_single_value("KPI Settings", "default_frequency") or "Daily"
    default_curr = frappe.db.get_single_value("KPI Settings", "currency") or "PKR"

    return {
        "user": user,
        "full_name": user_full_name,
        "role": role,
        "is_admin": role == "KPI Admin",
        "is_employee": role != "KPI Admin",
        "assigned_department": assigned_dept,
        "departments": departments,
        "department_list": department_list,
        "setup_completed": frappe.db.get_single_value("KPI Settings", "setup_completed") or 0,
        "default_frequency": default_freq,
        "currency": default_curr,
    }


@frappe.whitelist()
def get_action_center():
    role = _check_kpi_access()
    if role != "KPI Admin":
        frappe.throw("Access denied: Action Center is restricted to administrators.", frappe.PermissionError)

    user_depts = _get_user_departments()

    filters = {"status": ["in", ["Active", "Acknowledged"]]}
    alerts = frappe.db.get_all(
        "KPI Alert", filters=filters,
        fields=["name", "kpi", "department", "alert_type", "severity", "subject",
                "message", "trigger_period", "status", "sender", "sender_name",
                "sender_role", "creation"],
        order_by="severity desc, creation desc", limit_page_length=40,
    )

    all_kpis = frappe.db.get_all(
        "KPI Definition",
        filters={"is_active": 1, "department": ["in", user_depts]},
        fields=["name", "kpi_name", "department", "frequency"],
    )
    missing = []
    for kpi in all_kpis:
        latest = frappe.db.get_value(
            "KPI Data Entry",
            {"kpi": kpi.name, "docstatus": 1},
            "entry_date", order_by="entry_date desc",
        )
        if not latest:
            missing.append({
                "kpi": kpi.kpi_name, "kpi_code": kpi.name,
                "department": kpi.department, "status": "No data submitted",
                "frequency": kpi.frequency or "Monthly",
            })

    return {
        "alerts": alerts,
        "missing_data": missing,
        "total_items": len(alerts) + len(missing),
        "is_admin": True,
    }


@frappe.whitelist()
def get_data_entry_monitoring(frequency="Monthly", period=None):
    from productix.kpi_tracking.api.data_entry import get_data_entry_monitoring as _gdem
    return _gdem(frequency=frequency, period=period)
