import frappe
from frappe import _
from frappe.utils import flt
from productix.kpi_tracking.report.report_utils import (
    get_authorized_departments_for_report,
    get_status_badge,
)


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart(data)
    summary = get_summary(data)
    return columns, data, None, chart, summary


def get_columns():
    return [
        {"label": _("Alert ID"), "fieldname": "name", "fieldtype": "Link", "options": "KPI Alert", "width": 170},
        {"label": _("Alert Date"), "fieldname": "creation", "fieldtype": "Datetime", "width": 150},
        {"label": _("Department"), "fieldname": "department", "fieldtype": "Link", "options": "KPI Department", "width": 130},
        {"label": _("KPI"), "fieldname": "kpi", "fieldtype": "Link", "options": "KPI Definition", "width": 140},
        {"label": _("Alert Type"), "fieldname": "alert_type", "fieldtype": "Data", "width": 140},
        {"label": _("Severity"), "fieldname": "severity", "fieldtype": "Data", "width": 100},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 110},
        {"label": _("Subject"), "fieldname": "subject", "fieldtype": "Data", "width": 190},
        {"label": _("Alert Message"), "fieldname": "message", "fieldtype": "Small Text", "width": 240},
        {"label": _("Trigger Value"), "fieldname": "trigger_value", "fieldtype": "Float", "width": 110},
        {"label": _("Threshold"), "fieldname": "threshold_value", "fieldtype": "Float", "width": 100},
        {"label": _("Trigger Period"), "fieldname": "trigger_period", "fieldtype": "Data", "width": 110},
        {"label": _("Created By"), "fieldname": "sender_display", "fieldtype": "Data", "width": 140},
        {"label": _("Assigned Staff"), "fieldname": "assigned_staff", "fieldtype": "Data", "width": 160},
        {"label": _("Resolved By"), "fieldname": "resolved_by", "fieldtype": "Link", "options": "User", "width": 130},
        {"label": _("Resolution Date"), "fieldname": "resolved_at", "fieldtype": "Datetime", "width": 150},
        {"label": _("Last Modified"), "fieldname": "modified", "fieldtype": "Datetime", "width": 150},
    ]


def get_data(filters):
    allowed_depts, active_dept = get_authorized_departments_for_report(filters)

    conditions = []
    values = {}

    target_depts = [active_dept] if active_dept else allowed_depts
    conditions.append("(department IN %(depts)s OR department IS NULL OR department = '')")
    values["depts"] = tuple(target_depts)

    if filters.get("kpi"):
        conditions.append("kpi = %(kpi)s")
        values["kpi"] = filters.get("kpi")

    if filters.get("severity") and filters.get("severity") != "All":
        conditions.append("severity = %(severity)s")
        values["severity"] = filters.get("severity")

    if filters.get("alert_type") and filters.get("alert_type") != "All":
        conditions.append("alert_type = %(alert_type)s")
        values["alert_type"] = filters.get("alert_type")

    if filters.get("status") and filters.get("status") != "All":
        if filters.get("status") == "Open":
            conditions.append("status IN ('Active', 'Acknowledged')")
        else:
            conditions.append("status = %(status)s")
            values["status"] = filters.get("status")

    if filters.get("from_date"):
        conditions.append("DATE(creation) >= %(from_date)s")
        values["from_date"] = filters.get("from_date")

    if filters.get("to_date"):
        conditions.append("DATE(creation) <= %(to_date)s")
        values["to_date"] = filters.get("to_date")

    if filters.get("period"):
        conditions.append("trigger_period = %(period)s")
        values["period"] = filters.get("period")

    where_clause = " AND ".join(conditions)

    alerts = frappe.db.sql(f"""
        SELECT
            name,
            creation,
            department,
            kpi,
            alert_type,
            severity,
            status,
            subject,
            message,
            trigger_value,
            threshold_value,
            trigger_period,
            sender,
            sender_name,
            sender_role,
            resolved_by,
            resolved_at,
            modified
        FROM `tabKPI Alert`
        WHERE {where_clause}
        ORDER BY creation DESC
    """, values, as_dict=True)

    if not alerts:
        return []

    # Map assigned employees per department
    dept_assigned_map = {}
    assignments = frappe.db.get_all(
        "KPI User Assignment",
        filters={"is_active": 1, "department": ["in", target_depts]},
        fields=["department", "user"]
    )
    for asgn in assignments:
        dept_assigned_map.setdefault(asgn.department, []).append(asgn.user)

    data = []
    for a in alerts:
        dept_staff = dept_assigned_map.get(a.department, [])
        assigned_str = ", ".join(dept_staff) if dept_staff else "Department Staff"

        sender_label = a.sender_name or a.sender or "System"
        if a.sender_role and a.sender_role != "System":
            sender_label += f" ({a.sender_role})"

        data.append({
            "name": a.name,
            "creation": a.creation,
            "department": a.department or "All / General",
            "kpi": a.kpi or "N/A",
            "alert_type": a.alert_type,
            "severity": a.severity,
            "status": a.status,
            "subject": a.subject or f"[{a.severity}] {a.alert_type}",
            "message": a.message,
            "trigger_value": a.trigger_value,
            "threshold_value": a.threshold_value,
            "trigger_period": a.trigger_period or "--",
            "sender_display": sender_label,
            "assigned_staff": assigned_str,
            "resolved_by": a.resolved_by,
            "resolved_at": a.resolved_at,
            "modified": a.modified,
        })

    return data


def get_chart(data):
    if not data:
        return None

    crit_count = sum(1 for d in data if d["severity"] == "Critical")
    warn_count = sum(1 for d in data if d["severity"] == "Warning")
    info_count = sum(1 for d in data if d["severity"] in ("Info", "Informational"))

    return {
        "data": {
            "labels": [_("Critical"), _("Warning"), _("Info")],
            "datasets": [
                {"name": _("Alert Count"), "values": [crit_count, warn_count, info_count]}
            ],
        },
        "type": "donut",
        "title": _("KPI Alerts by Severity Breakdown"),
        "colors": ["#e74c3c", "#f39c12", "#3498db"],
    }


def get_summary(data):
    if not data:
        return []

    total_alerts = len(data)
    open_alerts = sum(1 for d in data if d["status"] in ("Active", "Acknowledged"))
    crit_count = sum(1 for d in data if d["severity"] == "Critical")
    warn_count = sum(1 for d in data if d["severity"] == "Warning")
    info_count = sum(1 for d in data if d["severity"] in ("Info", "Informational"))
    resolved_count = sum(1 for d in data if d["status"] == "Resolved")

    return [
        {"label": _("Total Alerts"), "value": total_alerts, "datatype": "Int", "indicator": "blue"},
        {"label": _("Open Alerts"), "value": open_alerts, "datatype": "Int", "indicator": "red" if open_alerts > 0 else "green"},
        {"label": _("Critical Alerts"), "value": crit_count, "datatype": "Int", "indicator": "red" if crit_count > 0 else "green"},
        {"label": _("Warning Alerts"), "value": warn_count, "datatype": "Int", "indicator": "orange" if warn_count > 0 else "green"},
        {"label": _("Info Alerts"), "value": info_count, "datatype": "Int", "indicator": "blue"},
        {"label": _("Resolved Alerts"), "value": resolved_count, "datatype": "Int", "indicator": "green"},
    ]
