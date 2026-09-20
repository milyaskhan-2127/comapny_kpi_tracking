import frappe
from frappe.utils import now_datetime, add_to_date, today, getdate


def evaluate_alerts(kpi_code, department, period):
    kpi = frappe.get_cached_doc("KPI Definition", kpi_code)
    if not kpi.alert_enabled:
        return

    settings = frappe.get_cached_doc("KPI Settings")
    if not settings.enable_alerts:
        return

    latest = frappe.db.get_value(
        "KPI Data Entry",
        {"kpi": kpi_code, "department": department, "docstatus": 1},
        ["actual_value", "achievement_percentage", "status", "period"],
        order_by="entry_date desc", as_dict=True,
    )
    if not latest:
        return

    if kpi.alert_target_miss:
        _check_target_miss(kpi, department, latest, settings)
    if kpi.alert_negative_trend:
        _check_negative_trend(kpi, department, settings)
    if kpi.alert_growth_decline:
        _check_growth_decline(kpi, department, settings)
    if kpi.alert_prediction_miss:
        _check_prediction_miss(kpi, department, period, settings)
    if kpi.alert_repeated_decline:
        _check_repeated_decline(kpi, department, settings)


def _check_target_miss(kpi, department, latest, settings):
    if not kpi.target_value:
        return
    ach = float(latest.achievement_percentage or 0.0)
    warn = float(kpi.warning_threshold or 80.0)
    crit = float(kpi.critical_threshold or 60.0)

    if ach >= warn:
        return

    severity = "Critical" if ach < crit else "Warning"
    _create_alert(
        kpi.name, department, "Target Miss", severity,
        f"{kpi.kpi_name} achieved {round(ach, 1)}% of target ({kpi.target_value}). Actual: {latest.actual_value}",
        latest.period, latest.actual_value, kpi.target_value, settings,
        subject=f"Target Miss: {kpi.kpi_name}"
    )


def _check_negative_trend(kpi, department, settings):
    from productix.kpi_tracking.services.analytics import calculate_trend

    trend_data = calculate_trend(kpi.name, department, 6)
    if trend_data["trend"] != "Declining":
        return

    _create_alert(
        kpi.name, department, "Negative Trend", "Warning",
        f"{kpi.kpi_name} is showing a declining trend (slope: {trend_data.get('relative_slope', 0)}%)",
        None, None, None, settings,
        subject=f"Negative Trend: {kpi.kpi_name}"
    )


def _check_growth_decline(kpi, department, settings):
    from productix.kpi_tracking.services.analytics import calculate_growth

    growth_data = calculate_growth(kpi.name, department)
    if growth_data.get("growth_percentage") is None or growth_data["growth_percentage"] >= 0:
        return

    severity = "Critical" if growth_data["growth_percentage"] < -20 else "Warning"
    _create_alert(
        kpi.name, department, "Growth Decline", severity,
        (f"{kpi.kpi_name} declined {abs(growth_data['growth_percentage'])}% "
         f"from {growth_data['previous_period']} to {growth_data['current_period']}"),
        growth_data.get("current_period"), growth_data.get("current_value"),
        growth_data.get("previous_value"), settings,
        subject=f"Growth Decline: {kpi.kpi_name}"
    )


def _check_prediction_miss(kpi, department, period, settings):
    predictions = frappe.db.get_all(
        "KPI Prediction",
        filters={
            "kpi": kpi.name, "department": department,
            "target_period": period, "status": "Prediction Miss",
        },
        fields=["predicted_value", "actual_value", "variance_percentage"],
    )
    for pred in predictions:
        _create_alert(
            kpi.name, department, "Prediction Miss", "Warning",
            (f"{kpi.kpi_name}: Actual ({pred.actual_value}) differs from "
             f"prediction ({pred.predicted_value}). Variance: {round(pred.variance_percentage, 1)}%"),
            period, pred.actual_value, pred.predicted_value, settings,
            subject=f"Prediction Miss: {kpi.kpi_name}"
        )


def _check_repeated_decline(kpi, department, settings):
    n = settings.repeated_decline_periods or 3
    entries = frappe.db.get_all(
        "KPI Data Entry",
        filters={"kpi": kpi.name, "department": department, "docstatus": 1},
        fields=["actual_value", "period"],
        order_by="entry_date desc", limit_page_length=n + 1,
    )
    if len(entries) < n + 1:
        return

    declining = all(entries[i].actual_value < entries[i + 1].actual_value for i in range(n))
    if not declining:
        return

    _create_alert(
        kpi.name, department, "Repeated Decline", "Critical",
        f"{kpi.kpi_name} has declined for {n} consecutive periods",
        entries[0].period, entries[0].actual_value, entries[-1].actual_value, settings,
        subject=f"Repeated Decline: {kpi.kpi_name}"
    )


def _create_alert(kpi, department, alert_type, severity, message,
                   period, trigger_val, threshold_val, settings, subject=None):
    cooldown_hours = settings.alert_cooldown_hours or 24

    existing = frappe.db.get_all("KPI Alert", filters={
        "kpi": kpi, "department": department, "alert_type": alert_type,
        "status": ["in", ["Active", "Acknowledged"]],
    }, fields=["name", "cooldown_until"])

    for e in existing:
        if e.cooldown_until and now_datetime() < e.cooldown_until:
            return
        if not e.cooldown_until:
            return

    cooldown = add_to_date(now_datetime(), hours=cooldown_hours)
    alert = frappe.get_doc({
        "doctype": "KPI Alert",
        "kpi": kpi,
        "department": department,
        "alert_type": alert_type,
        "subject": subject or f"[{severity}] {alert_type}: {kpi}",
        "severity": severity,
        "message": message,
        "trigger_period": period,
        "trigger_value": trigger_val,
        "threshold_value": threshold_val,
        "cooldown_until": cooldown,
        "sender": "Administrator",
        "sender_name": "KPI Alert Engine",
        "sender_role": "System",
        "status": "Active",
    })
    alert.insert(ignore_permissions=True)
    _send_notification(alert)


def _send_notification(alert):
    recipients = []
    if alert.department:
        users = frappe.db.get_all(
            "KPI User Assignment",
            filters={"department": alert.department, "is_active": 1},
            fields=["user", "role"],
        )
        recipients = [u.user for u in users]

    if alert.severity == "Critical" or alert.alert_type == "Employee Escalation":
        admins = frappe.db.get_all(
            "KPI User Assignment",
            filters={"role": "KPI Admin", "is_active": 1},
            fields=["user"],
        )
        for a in admins:
            if a.user not in recipients:
                recipients.append(a.user)

        # Also notify System Managers
        sys_managers = frappe.db.sql(
            """SELECT parent FROM `tabHas Role` WHERE role IN ('System Manager', 'KPI Admin') AND parenttype='User'""",
            as_dict=True
        )
        for sm in sys_managers:
            if sm.parent not in recipients and sm.parent != "Guest":
                recipients.append(sm.parent)

    for user in recipients:
        try:
            frappe.get_doc({
                "doctype": "Notification Log",
                "for_user": user,
                "type": "Alert",
                "document_type": "KPI Alert",
                "document_name": alert.name,
                "subject": alert.subject or f"[{alert.severity}] {alert.alert_type}: {alert.department or 'General'}",
                "email_content": alert.message,
            }).insert(ignore_permissions=True)
        except Exception:
            pass


@frappe.whitelist()
def send_missing_data_reminders(department=None, period=None, frequency="Monthly", message=None):
    """Notify employees of departments with missing required data."""
    from productix.kpi_tracking.api.dashboard import _check_kpi_access
    role = _check_kpi_access()
    if role != "KPI Admin":
        frappe.throw("Access denied: Only administrators can dispatch reminders.", frappe.PermissionError)

    from productix.kpi_tracking.api.data_entry import get_data_entry_monitoring
    monitoring = get_data_entry_monitoring(frequency=frequency, period=period)

    depts_to_notify = []
    for d in monitoring.get("departments", []):
        if department and d["department_code"] != department:
            continue
        if d["missing_entries"] > 0:
            depts_to_notify.append(d)

    dispatched = []
    for d in depts_to_notify:
        dept_code = d["department_code"]
        dept_name = d["department"]
        target_period = d["period"]
        missing_count = d["missing_entries"]

        employees = frappe.db.get_all(
            "KPI User Assignment",
            filters={"department": dept_code, "is_active": 1},
            pluck="user",
        )

        custom_msg = message or (
            f"KPI data entry is pending for {dept_name}. "
            f"Please complete {missing_count} required {frequency.lower()} metric submission(s) for period {target_period}."
        )

        for emp in employees:
            try:
                frappe.get_doc({
                    "doctype": "Notification Log",
                    "for_user": emp,
                    "type": "Alert",
                    "document_type": "KPI Department",
                    "document_name": dept_code,
                    "subject": f"[Action Required] Pending KPI Submissions for {dept_name}",
                    "email_content": custom_msg,
                }).insert(ignore_permissions=True)
                dispatched.append({"user": emp, "department": dept_name, "period": target_period})
            except Exception:
                pass

    return {
        "status": "success",
        "departments_notified": [d["department"] for d in depts_to_notify],
        "notifications_sent": len(dispatched),
        "recipients": dispatched,
    }


@frappe.whitelist()
def dispatch_ai_department_alert(department, message, severity="Info", kpi=None):
    """Send an alert to all employees assigned to a specific department or All Departments from Admin / AI."""
    from productix.kpi_tracking.api.dashboard import _check_kpi_access
    role = _check_kpi_access()
    if role != "KPI Admin":
        frappe.throw("Access denied: Only administrators can dispatch department alerts.", frappe.PermissionError)

    if not message or not str(message).strip():
        frappe.throw("Alert message is required.")

    # Normalize severity
    if severity not in ("Info", "Warning", "Critical"):
        severity = "Info" if severity in ("Informational", "info") else "Warning"

    is_all_depts = department in ("ALL", "All", "All Departments", "__all__", None, "")

    valid_dept = None
    if is_all_depts:
        target_dept_name = "All Departments"
        employees = frappe.db.get_all(
            "KPI User Assignment",
            filters={"is_active": 1, "role": ["in", ["KPI Employee", "KPI Manager", "KPI Contributor"]]},
            pluck="user",
        )
    else:
        if frappe.db.exists("KPI Department", department):
            dept_doc = frappe.get_doc("KPI Department", department)
            target_dept_name = dept_doc.department_name
            valid_dept = department
        else:
            target_dept_name = department
            valid_dept = None

        employees = frappe.db.get_all(
            "KPI User Assignment",
            filters={"department": department, "is_active": 1},
            pluck="user",
        )

    # Validate KPI link field
    valid_kpi = None
    if kpi and frappe.db.exists("KPI Definition", kpi):
        valid_kpi = kpi

    subject = f"[{severity} Directive] {target_dept_name} Management Directive"
    sender_user = frappe.session.user
    sender_full_name = frappe.db.get_value("User", sender_user, "full_name") or sender_user

    # Record in KPI Alert for auditing
    alert = frappe.get_doc({
        "doctype": "KPI Alert",
        "department": valid_dept,
        "kpi": valid_kpi,
        "alert_type": "Admin Directive",
        "severity": severity,
        "subject": subject,
        "message": message.strip(),
        "trigger_period": today(),
        "status": "Active",
        "sender": sender_user,
        "sender_name": sender_full_name,
        "sender_role": "Admin",
    })
    alert.insert(ignore_permissions=True)

    recipient_names = []
    seen_users = set()
    for emp in (employees or []):
        if emp in seen_users or emp == sender_user:
            continue
        seen_users.add(emp)
        u_name = frappe.db.get_value("User", emp, "full_name") or emp
        recipient_names.append(f"{u_name} ({emp})")
        try:
            frappe.get_doc({
                "doctype": "Notification Log",
                "for_user": emp,
                "type": "Alert",
                "document_type": "KPI Alert",
                "document_name": alert.name,
                "subject": subject,
                "email_content": message,
            }).insert(ignore_permissions=True)
        except Exception:
            pass

    return {
        "status": "success",
        "alert_id": alert.name,
        "department": target_dept_name,
        "department_code": department,
        "recipients": recipient_names,
        "count": len(recipient_names),
        "severity": severity,
        "initiated_by": sender_user,
        "timestamp": now_datetime(),
    }


@frappe.whitelist()
def send_employee_escalation_alert(department, message, subject=None, severity="Warning", kpi=None):
    """
    Dedicated Employee-to-Admin Messaging & Escalation Endpoint.
    Allows employees to send operational updates, blockers, or escalation alerts directly to Admins.
    """
    from productix.kpi_tracking.api.dashboard import _check_kpi_access, _get_user_departments
    role = _check_kpi_access()

    if not message or not str(message).strip():
        frappe.throw("Message is required for escalation.")

    user = frappe.session.user
    user_depts = _get_user_departments(user)

    # Validate department
    if not department and user_depts:
        department = user_depts[0]

    valid_dept = None
    target_dept_name = department or "Department"
    if department and frappe.db.exists("KPI Department", department):
        valid_dept = department
        target_dept_name = frappe.db.get_value("KPI Department", department, "department_name") or department

    # Validate KPI if provided
    valid_kpi = None
    if kpi and frappe.db.exists("KPI Definition", kpi):
        valid_kpi = kpi

    # Normalize severity
    if severity not in ("Info", "Warning", "Critical"):
        severity = "Warning"

    user_full_name = frappe.db.get_value("User", user, "full_name") or user
    escalation_subject = (subject or f"Operational Update / Blocker from {target_dept_name}").strip()

    alert = frappe.get_doc({
        "doctype": "KPI Alert",
        "department": valid_dept,
        "kpi": valid_kpi,
        "alert_type": "Employee Escalation",
        "severity": severity,
        "subject": escalation_subject,
        "message": message.strip(),
        "trigger_period": today(),
        "status": "Active",
        "sender": user,
        "sender_name": user_full_name,
        "sender_role": "Employee" if role != "KPI Admin" else "Admin",
    })
    alert.insert(ignore_permissions=True)

    # Notify all KPI Admins and System Managers
    admin_users = set()
    admin_assignments = frappe.db.get_all(
        "KPI User Assignment",
        filters={"role": "KPI Admin", "is_active": 1},
        pluck="user",
    )
    for u in admin_assignments:
        admin_users.add(u)

    sys_managers = frappe.db.sql(
        """SELECT parent FROM `tabHas Role` WHERE role IN ('System Manager', 'KPI Admin') AND parenttype='User'""",
        as_dict=True
    )
    for sm in sys_managers:
        if sm.parent and sm.parent != "Guest" and sm.parent != user:
            admin_users.add(sm.parent)

    for admin_email in admin_users:
        try:
            frappe.get_doc({
                "doctype": "Notification Log",
                "for_user": admin_email,
                "type": "Alert",
                "document_type": "KPI Alert",
                "document_name": alert.name,
                "subject": f"[{severity} Escalation] {escalation_subject} ({user_full_name})",
                "email_content": message,
            }).insert(ignore_permissions=True)
        except Exception:
            pass

    return {
        "status": "success",
        "alert_id": alert.name,
        "subject": escalation_subject,
        "department": target_dept_name,
        "severity": severity,
        "sender": user_full_name,
        "timestamp": now_datetime(),
    }


@frappe.whitelist()
def get_department_escalations(department=None, limit=10):
    """Fetch recent messages / escalation alerts sent by employees of a department."""
    from productix.kpi_tracking.api.dashboard import _check_kpi_access, _get_user_departments
    role = _check_kpi_access()
    user_depts = _get_user_departments()

    filters = {"alert_type": ["in", ["Employee Escalation", "Admin Directive"]]}

    if role != "KPI Admin":
        if department and department in user_depts:
            filters["department"] = department
        elif user_depts:
            filters["department"] = ["in", user_depts]
    else:
        if department and department != "All":
            filters["department"] = department

    alerts = frappe.db.get_all(
        "KPI Alert",
        filters=filters,
        fields=[
            "name", "alert_type", "subject", "message", "severity",
            "status", "department", "kpi", "sender", "sender_name",
            "sender_role", "creation", "trigger_period"
        ],
        order_by="creation desc",
        limit_page_length=int(limit),
    )

    return alerts


@frappe.whitelist()
def acknowledge_alert(alert_name):
    """Mark an alert as Acknowledged."""
    from productix.kpi_tracking.api.dashboard import _check_kpi_access
    _check_kpi_access()

    if not frappe.db.exists("KPI Alert", alert_name):
        frappe.throw(f"Alert {alert_name} does not exist.", frappe.DoesNotExistError)

    doc = frappe.get_doc("KPI Alert", alert_name)
    doc.status = "Acknowledged"
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"status": "ok", "message": f"Alert {alert_name} acknowledged."}


@frappe.whitelist()
def resolve_alert(alert_name):
    """Mark an alert as Resolved."""
    from productix.kpi_tracking.api.dashboard import _check_kpi_access
    role = _check_kpi_access()
    if role != "KPI Admin":
        frappe.throw("Access denied: Only administrators can resolve alerts.", frappe.PermissionError)

    if not frappe.db.exists("KPI Alert", alert_name):
        frappe.throw(f"Alert {alert_name} does not exist.", frappe.DoesNotExistError)

    doc = frappe.get_doc("KPI Alert", alert_name)
    doc.status = "Resolved"
    doc.resolved_at = now_datetime()
    doc.resolved_by = frappe.session.user
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"status": "ok", "message": f"Alert {alert_name} resolved."}


def run_scheduled_alert_check():
    kpis = frappe.db.get_all(
        "KPI Definition",
        filters={"is_active": 1, "alert_enabled": 1},
        fields=["name", "department"],
    )
    for kpi in kpis:
        try:
            evaluate_alerts(kpi.name, kpi.department, None)
        except Exception:
            frappe.log_error(f"Alert check failed for KPI {kpi.name}")
