import frappe
from productix_kpi.kpi_tracking.security.permissions import (
    is_kpi_admin,
    is_kpi_ceo,
    get_user_authorized_department,
    get_ceo_authorized_departments,
    get_ceo_access,
    get_user_role,
)


def _check_kpi_access(user=None):
    user = user or frappe.session.user
    if user == "Administrator":
        return "KPI Admin"

    if not frappe.db.get_value("User", user, "enabled"):
        frappe.throw("Your user account has been disabled. Please contact your administrator.", frappe.PermissionError)

    if is_kpi_admin(user):
        return "KPI Admin"

    if is_kpi_ceo(user):
        return "KPI CEO"

    roles = frappe.get_roles(user)
    if "KPI Employee" in roles or "KPI Manager" in roles or "KPI Contributor" in roles:
        return "KPI Employee"

    has_active = frappe.db.exists("KPI User Assignment", {"user": user, "is_active": 1})
    if has_active:
        return "KPI Employee"

    dept = get_user_authorized_department(user)
    if dept:
        return "KPI Employee"

    frappe.throw("You do not have access to KPI Tracking. Please contact your administrator.", frappe.PermissionError)


def _get_user_departments(user=None):
    user = user or frappe.session.user
    role = _check_kpi_access(user)

    if role == "KPI Admin":
        return frappe.db.get_all(
            "KPI Department",
            filters={"is_active": 1},
            pluck="name",
            order_by="department_name asc",
        )

    if role == "KPI CEO":
        depts = get_ceo_authorized_departments(user)
        if depts:
            return frappe.db.get_all(
                "KPI Department",
                filters={"name": ["in", depts], "is_active": 1},
                pluck="name",
                order_by="department_name asc",
            )
        return frappe.db.get_all(
            "KPI Department",
            filters={"is_active": 1},
            pluck="name",
            order_by="department_name asc",
        )

    departments = set()
    assigned_depts = frappe.db.get_all(
        "KPI User Assignment",
        filters={"user": user, "is_active": 1},
        pluck="department",
    )
    for d in assigned_depts:
        if d:
            departments.add(d)

    emp_dept = get_user_authorized_department(user)
    if emp_dept:
        departments.add(emp_dept)

    if not departments:
        return []

    return frappe.db.get_all(
        "KPI Department",
        filters={"name": ["in", list(departments)], "is_active": 1},
        pluck="name",
        order_by="department_name asc",
    )


@frappe.whitelist()
def get_company_overview(timeframe="6_months", horizon="next_month", period=None, frequency=None):
    role = _check_kpi_access()

    if role == "KPI CEO":
        ceo = get_ceo_access()
        if not ceo or not ceo.can_view_company_overview:
            frappe.throw("Access denied: You do not have permission to view Company Overview.", frappe.PermissionError)
    elif role != "KPI Admin":
        frappe.throw("Access denied: Company Performance Overview is restricted to administrators.", frappe.PermissionError)

    if not frequency or frequency == "All":
        frequency = frappe.db.get_single_value("KPI Settings", "default_frequency") or "Daily"

    from productix_kpi.kpi_tracking.services.analytics import get_company_performance

    ceo_depts = None
    if role == "KPI CEO":
        ceo_depts = get_ceo_authorized_departments()

    perf = get_company_performance(
        timeframe=timeframe, horizon=horizon, period=period,
        frequency=frequency, departments=ceo_depts
    )

    crit_filter = {"status": "Active", "severity": "Critical"}
    warn_filter = {"status": "Active", "severity": "Warning"}
    info_filter = {"status": "Active", "severity": ["in", ["Info", "Informational"]]}
    ack_filter = {"status": "Acknowledged"}
    res_filter = {"status": "Resolved"}
    if ceo_depts:
        crit_filter["department"] = ["in", ceo_depts]
        warn_filter["department"] = ["in", ceo_depts]
        info_filter["department"] = ["in", ceo_depts]
        ack_filter["department"] = ["in", ceo_depts]
        res_filter["department"] = ["in", ceo_depts]

    critical_count = frappe.db.count("KPI Alert", crit_filter)
    warning_count = frappe.db.count("KPI Alert", warn_filter)
    info_count = frappe.db.count("KPI Alert", info_filter)
    ack_count = frappe.db.count("KPI Alert", ack_filter)
    res_count = frappe.db.count("KPI Alert", res_filter)

    perf["critical_alerts_count"] = critical_count
    perf["warning_alerts_count"] = warning_count
    perf["info_alerts_count"] = info_count
    perf["active_alerts_count"] = critical_count + warning_count + info_count
    perf["acknowledged_alerts_count"] = ack_count
    perf["resolved_alerts_count"] = res_count
    perf["alerts_summary"] = {
        "Critical": critical_count,
        "Warning": warning_count,
        "Info": info_count,
    }

    kpi_filters = {"is_active": 1}
    if ceo_depts:
        kpi_filters["department"] = ["in", ceo_depts]
    perf["total_kpis"] = frappe.db.count("KPI Definition", kpi_filters)
    perf["total_users"] = frappe.db.count("KPI User Assignment", {"is_active": 1})

    from productix_kpi.kpi_tracking.api.data_entry import _get_data_entry_monitoring_internal
    perf["data_entry_monitoring"] = _get_data_entry_monitoring_internal(
        frequency=frequency, period=period, departments=ceo_depts
    )

    can_view_machines = True
    if role == "KPI CEO":
        ceo = get_ceo_access()
        can_view_machines = bool(ceo and getattr(ceo, "can_view_machines", 0))

    if can_view_machines:
        try:
            from productix_kpi.kpi_tracking.services.machine_health import get_company_machines_health
            perf["machine_health_overview"] = get_company_machines_health(departments=ceo_depts)
        except Exception as e:
            frappe.log_error(f"Error getting company machine health: {e}")
            perf["machine_health_overview"] = None
    else:
        perf["machine_health_overview"] = None

    return perf


@frappe.whitelist()
def get_department_dashboard(department=None, timeframe="6_months", horizon="next_month", period=None, frequency=None):
    role = _check_kpi_access()
    user_depts = _get_user_departments()

    if not user_depts and role not in ("KPI Admin", "KPI CEO"):
        frappe.throw("No active department found or assigned to your account.", frappe.PermissionError)

    if role == "KPI Employee":
        if department and department not in user_depts:
            frappe.throw("Access denied: You can only view your assigned department.", frappe.PermissionError)
        department = user_depts[0] if user_depts else None
        if not department:
            frappe.throw("No active department assigned to your account.", frappe.PermissionError)
    elif role == "KPI CEO":
        if department and department not in user_depts:
            frappe.throw("Access denied: You do not have access to this department.", frappe.PermissionError)
        if not department:
            if not user_depts:
                frappe.throw("No KPI departments are configured in your CEO access. "
                             "Ask an Administrator to configure your CEO Access.", frappe.PermissionError)
            department = user_depts[0]
    else:
        if not department:
            if not user_depts:
                frappe.throw("No active KPI Departments found. "
                             "Please create at least one active KPI Department before using this dashboard.",
                             frappe.DoesNotExistError)
            department = user_depts[0]
        elif not frappe.db.exists("KPI Department", department):
            dept_match = frappe.db.get_value("KPI Department", {"department_code": department}, "name") or \
                         frappe.db.get_value("KPI Department", {"department_name": department}, "name")
            if dept_match:
                department = dept_match
            else:
                frappe.throw(f"Department '{department}' does not exist.", frappe.DoesNotExistError)

    if not frequency or frequency == "All":
        frequency = frappe.db.get_single_value("KPI Settings", "default_frequency") or "Daily"

    from productix_kpi.kpi_tracking.services.analytics import get_department_performance
    perf = get_department_performance(
        department, timeframe=timeframe, horizon=horizon,
        period=period, frequency=frequency, include_predictions=True
    )

    alert_filters = {"department": department, "status": ["in", ["Active", "Acknowledged"]]}
    alerts = frappe.db.get_all(
        "KPI Alert",
        filters=alert_filters,
        fields=["name", "kpi", "alert_type", "severity", "subject", "message", "trigger_period", "status", "creation"],
        order_by="creation desc", limit_page_length=10,
    )
    perf["alerts"] = alerts
    perf["critical_count"] = frappe.db.count("KPI Alert", {"department": department, "status": "Active", "severity": "Critical"})
    perf["warning_count"] = frappe.db.count("KPI Alert", {"department": department, "status": "Active", "severity": "Warning"})
    perf["acknowledged_count"] = frappe.db.count("KPI Alert", {"department": department, "status": "Acknowledged"})
    perf["resolved_count"] = frappe.db.count("KPI Alert", {"department": department, "status": "Resolved"})
    perf["active_alerts_count"] = perf["critical_count"] + perf["warning_count"]

    dept_doc = frappe.get_doc("KPI Department", department)
    perf["department_name"] = dept_doc.get_disambiguated_name() if hasattr(dept_doc, "get_disambiguated_name") else (dept_doc.department_name or dept_doc.name)
    perf["department_raw_name"] = dept_doc.department_name or dept_doc.name
    perf["location"] = getattr(dept_doc, "location", "") or ""
    perf["department_code"] = getattr(dept_doc, "department_code", dept_doc.name) or dept_doc.name
    perf["is_admin"] = (role == "KPI Admin")
    perf["is_ceo"] = (role == "KPI CEO")
    perf["role"] = role

    try:
        from productix_kpi.kpi_tracking.services.machine_health import get_department_machines_health
        perf["machine_health"] = get_department_machines_health(department)
    except Exception as e:
        frappe.log_error(f"Error getting department machine health: {e}")
        perf["machine_health"] = None

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

    if role == "KPI CEO":
        from productix_kpi.kpi_tracking.security.permissions import get_ceo_authorized_kpis
        allowed_kpis = get_ceo_authorized_kpis(department=kpi.department)
        if allowed_kpis is not None and kpi_code not in allowed_kpis:
            frappe.throw(f"Access denied: You do not have permission to view KPI '{kpi_code}'.", frappe.PermissionError)

    from productix_kpi.kpi_tracking.services.analytics import (
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

    kpi_alerts = frappe.db.get_all(
        "KPI Alert",
        filters={"kpi": kpi_code},
        fields=["name", "alert_type", "severity", "trigger_period", "creation", "status", "message"],
        order_by="creation desc", limit_page_length=5,
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
        "alerts": kpi_alerts,
    }


@frappe.whitelist()
def get_kpi_options():
    """Active KPI options (name + label) for selectors, scoped to the user's access."""
    role = _check_kpi_access()
    filters = {"is_active": 1}
    if role == "KPI CEO":
        ceo_depts = get_ceo_authorized_departments()
        if ceo_depts:
            filters["department"] = ["in", ceo_depts]
    elif role == "KPI Employee":
        user_depts = _get_user_departments()
        if user_depts:
            filters["department"] = ["in", user_depts]
        else:
            filters["name"] = ["in", ["__none__"]]

    kpis = frappe.db.get_all(
        "KPI Definition",
        filters=filters,
        fields=["name", "kpi_name", "kpi_code", "department"],
        order_by="kpi_name asc",
    )
    return {"kpis": kpis}


@frappe.whitelist()
def get_user_context():
    user = frappe.session.user
    role = _check_kpi_access(user)
    departments = _get_user_departments(user)

    if role in ("KPI Admin", "KPI CEO"):
        dept_filters = {"is_active": 1}
        if role == "KPI CEO" and departments:
            dept_filters["name"] = ["in", departments]
        department_list = frappe.get_all(
            "KPI Department",
            filters=dept_filters,
            fields=["name", "department_name", "department_code", "weight", "location"],
            order_by="department_name asc",
        )
    else:
        department_list = []
        if departments:
            department_list = frappe.get_all(
                "KPI Department",
                filters={"name": ["in", departments], "is_active": 1},
                fields=["name", "department_name", "department_code", "weight", "location"],
                order_by="department_name asc",
            )

    for d in department_list:
        label = d.department_name or d.name
        if d.get("location"):
            label += f" — {d.location}"
        code = d.get("department_code") or d.name
        if code and code != label:
            label += f" [{code}]"
        d["display_name"] = label

    assigned_dept = department_list[0].name if (role == "KPI Employee" and department_list) else None

    user_full_name = frappe.db.get_value("User", user, "full_name") or user

    default_freq = frappe.db.get_single_value("KPI Settings", "default_frequency") or "Daily"
    default_curr = frappe.db.get_single_value("KPI Settings", "currency") or "PKR"

    ceo_config = None
    if role == "KPI CEO":
        ceo = get_ceo_access(user)
        if ceo:
            ceo_config = {
                "access_scope": ceo.access_scope,
                "can_view_company_overview": ceo.can_view_company_overview,
                "can_view_machines": ceo.can_view_machines,
            }

    return {
        "user": user,
        "full_name": user_full_name,
        "role": role,
        "is_admin": role == "KPI Admin",
        "is_ceo": role == "KPI CEO",
        "is_employee": role == "KPI Employee",
        "assigned_department": assigned_dept,
        "departments": [d.name for d in department_list] if department_list else departments,
        "department_list": department_list,
        "ceo_config": ceo_config,
        "setup_completed": frappe.db.get_single_value("KPI Settings", "setup_completed") or 0,
        "default_frequency": default_freq,
        "currency": default_curr,
    }


@frappe.whitelist()
def get_action_center(period=None, frequency=None):
    role = _check_kpi_access()

    if role == "KPI Employee":
        frappe.throw("Access denied: Action Center is restricted to administrators and CEOs.", frappe.PermissionError)

    ceo_depts = None
    if role == "KPI CEO":
        ceo_depts = get_ceo_authorized_departments()

    filters = {"status": ["in", ["Active", "Acknowledged"]]}
    if ceo_depts:
        filters["department"] = ["in", ceo_depts]

    alerts = frappe.db.get_all(
        "KPI Alert", filters=filters,
        fields=["name", "kpi", "department", "alert_type", "severity", "subject",
                "message", "trigger_period", "status", "sender", "sender_name",
                "sender_role", "creation"],
        order_by="creation desc",
        limit_page_length=200,
    )
    severity_order = {"Critical": 1, "Warning": 2, "Info": 3, "Informational": 3}
    alerts.sort(key=lambda a: severity_order.get(a.get("severity"), 4))

    from productix_kpi.kpi_tracking.api.data_entry import _get_data_entry_monitoring_internal
    monitoring = _get_data_entry_monitoring_internal(
        frequency=frequency, period=period, departments=ceo_depts
    )

    missing = []
    for dept_info in monitoring.get("departments", []):
        if dept_info.get("missing_entries", 0) > 0:
            missing.append({
                "kpi": f"{dept_info['missing_entries']} Pending Metric(s)",
                "department": dept_info["department_code"],
                "department_name": dept_info["department"],
                "missing_entries": dept_info["missing_entries"],
                "completed_entries": dept_info["completed_entries"],
                "required_entries": dept_info["required_entries"],
                "period": dept_info["period"],
                "frequency": dept_info.get("frequency", "Monthly"),
                "assigned_employees": dept_info.get("assigned_employees", []),
                "status": f"{dept_info['missing_entries']} pending submissions",
            })

    active_alerts = [a for a in alerts if a.status == "Active"]

    base_alert_filter = {}
    if ceo_depts:
        base_alert_filter["department"] = ["in", ceo_depts]

    critical_count = frappe.db.count("KPI Alert", {**base_alert_filter, "status": "Active", "severity": "Critical"})
    warning_count = frappe.db.count("KPI Alert", {**base_alert_filter, "status": "Active", "severity": "Warning"})
    acknowledged_count = frappe.db.count("KPI Alert", {**base_alert_filter, "status": "Acknowledged"})
    resolved_count = frappe.db.count("KPI Alert", {**base_alert_filter, "status": "Resolved"})
    total_active_alerts = critical_count + warning_count
    missing_count = sum(m["missing_entries"] for m in missing)

    return {
        "alerts": alerts,
        "active_alerts": active_alerts,
        "missing_data": missing,
        "critical_count": critical_count,
        "warning_count": warning_count,
        "acknowledged_count": acknowledged_count,
        "resolved_count": resolved_count,
        "missing_count": missing_count,
        "total_active_items": total_active_alerts + missing_count,
        "total_items": total_active_alerts + acknowledged_count + missing_count,
        "is_admin": role == "KPI Admin",
        "is_ceo": role == "KPI CEO",
        "role": role,
    }


@frappe.whitelist()
def get_data_entry_monitoring(frequency="Monthly", period=None):
    from productix_kpi.kpi_tracking.api.data_entry import get_data_entry_monitoring as _gdem
    return _gdem(frequency=frequency, period=period)
