import frappe
from frappe import _
from frappe.utils import flt, getdate, today
from productix.kpi_tracking.report.report_utils import (
    get_authorized_departments_for_report,
    calculate_kpi_variance,
    get_kpi_score_badge,
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
        {"label": _("Company"), "fieldname": "company", "fieldtype": "Data", "width": 130},
        {"label": _("Department"), "fieldname": "department", "fieldtype": "Link", "options": "KPI Department", "width": 140},
        {"label": _("Business Unit"), "fieldname": "business_unit", "fieldtype": "Link", "options": "KPI Business Unit", "width": 130},
        {"label": _("KPI"), "fieldname": "kpi_name", "fieldtype": "Data", "width": 170},
        {"label": _("KPI Code"), "fieldname": "kpi_code", "fieldtype": "Link", "options": "KPI Definition", "width": 140},
        {"label": _("Reporting Period"), "fieldname": "period", "fieldtype": "Data", "width": 120},
        {"label": _("Target"), "fieldname": "target_value", "fieldtype": "Float", "width": 100},
        {"label": _("Actual"), "fieldname": "actual_value", "fieldtype": "Float", "width": 100},
        {"label": _("Unit"), "fieldname": "unit", "fieldtype": "Data", "width": 80},
        {"label": _("Normalized Score /100"), "fieldname": "normalized_score", "fieldtype": "Float", "width": 150},
        {"label": _("Variance"), "fieldname": "variance", "fieldtype": "Float", "width": 100},
        {"label": _("Variance %"), "fieldname": "variance_pct", "fieldtype": "Percent", "width": 110},
        {"label": _("Weight"), "fieldname": "weight", "fieldtype": "Float", "width": 80},
        {"label": _("Achievement Status"), "fieldname": "achievement_status", "fieldtype": "Data", "width": 140},
        {"label": _("KPI Direction"), "fieldname": "direction", "fieldtype": "Data", "width": 130},
        {"label": _("Operational Status"), "fieldname": "status", "fieldtype": "Data", "width": 130},
        {"label": _("Open Alerts"), "fieldname": "open_alerts", "fieldtype": "Int", "width": 100},
        {"label": _("Last Submission"), "fieldname": "entry_date", "fieldtype": "Date", "width": 110},
    ]


def get_data(filters):
    allowed_depts, active_dept = get_authorized_departments_for_report(filters)

    kpi_filters = {"is_active": 1, "department": ["in", allowed_depts]}
    if filters.get("business_unit"):
        kpi_filters["business_unit"] = filters.get("business_unit")
    if filters.get("kpi"):
        kpi_filters["name"] = filters.get("kpi")
    if filters.get("frequency") and filters.get("frequency") != "All":
        kpi_filters["frequency"] = filters.get("frequency")

    kpis = frappe.db.get_all(
        "KPI Definition",
        filters=kpi_filters,
        fields=[
            "name", "kpi_name", "kpi_code", "department", "business_unit",
            "target_value", "unit", "direction", "weight", "frequency",
            "warning_threshold", "critical_threshold", "target_type",
            "minimum_acceptable", "start_date"
        ],
        order_by="department asc, kpi_name asc",
    )

    if not kpis:
        return []

    # Pre-fetch department names
    dept_names = {}
    for d in frappe.db.get_all("KPI Department", fields=["name", "department_name"]):
        dept_names[d.name] = d.department_name or d.name

    # Pre-fetch open alerts count grouped by (kpi, department)
    open_alerts_map = {}
    alerts_data = frappe.db.get_all(
        "KPI Alert",
        filters={"status": ["in", ["Active", "Acknowledged"]], "department": ["in", allowed_depts]},
        fields=["kpi", "department", "count(name) as cnt"],
        group_by="kpi, department"
    )
    for a in alerts_data:
        key = (a.kpi, a.department)
        open_alerts_map[key] = a.cnt

    company_name = frappe.db.get_single_value("KPI Settings", "company") or "Productix Enterprise"
    status_filter = filters.get("status")
    period_filter = filters.get("period")
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")

    data = []

    for kpi in kpis:
        entry_filters = {"kpi": kpi.name, "docstatus": 1}
        if active_dept:
            entry_filters["department"] = active_dept
        else:
            entry_filters["department"] = kpi.department

        if period_filter:
            entry_filters["period"] = period_filter
        if from_date:
            entry_filters["entry_date"] = [">=", from_date]
        if to_date:
            if "entry_date" in entry_filters:
                entry_filters["entry_date"] = ["between", [from_date, to_date]]
            else:
                entry_filters["entry_date"] = ["<=", to_date]

        # Fetch latest entry matching filters
        entry = frappe.db.get_value(
            "KPI Data Entry",
            entry_filters,
            ["name", "actual_value", "target_value", "achievement_percentage", "status", "period", "entry_date", "creation"],
            order_by="entry_date desc, creation desc",
            as_dict=True,
        )

        open_alerts = open_alerts_map.get((kpi.name, kpi.department), 0)
        target_val = flt(kpi.target_value)

        if entry:
            actual_val = flt(entry.actual_value)
            target_val = flt(entry.target_value if entry.target_value is not None else kpi.target_value)
            # Use strictly the normalized score 0-100 from calculation engine
            norm_score = max(0.0, min(100.0, flt(entry.achievement_percentage or 0.0)))
            period_val = entry.period
            entry_date_val = entry.entry_date
            op_status = entry.status or "On Track"

            variance, variance_pct, ach_status = calculate_kpi_variance(
                actual_val, target_val, kpi.direction
            )

            # Refine achievement status based on warning/critical thresholds
            warn_th = flt(kpi.warning_threshold if kpi.warning_threshold is not None else 80.0)
            if norm_score >= 100.0 and actual_val != target_val and kpi.direction in ("Higher is Better", "Lower is Better"):
                ach_status = "Above Target"
            elif norm_score >= warn_th:
                ach_status = "Meeting Target"
            else:
                ach_status = "Below Target"

        else:
            actual_val = None
            norm_score = None
            period_val = period_filter or "No Data"
            entry_date_val = None
            variance = 0.0
            variance_pct = 0.0
            op_status = "Pending / No Data"

            # Check if unavailable (future start date)
            if kpi.start_date and getdate(kpi.start_date) > getdate(today()):
                ach_status = "Unavailable"
            else:
                ach_status = "Missing Data"

        # Apply status filter if supplied
        if status_filter and status_filter != "All":
            if status_filter in ("Meeting Target", "Above Target", "Below Target", "Missing Data", "Unavailable"):
                if ach_status != status_filter:
                    continue
            elif status_filter in ("On Track", "Warning", "Critical", "Pending / No Data"):
                if op_status != status_filter:
                    continue

        dept_display = dept_names.get(kpi.department, kpi.department)

        row = {
            "company": company_name,
            "department": dept_display,
            "business_unit": kpi.business_unit or "",
            "kpi_name": kpi.kpi_name,
            "kpi_code": kpi.name,
            "period": period_val,
            "target_value": target_val,
            "actual_value": actual_val,
            "unit": kpi.unit or "",
            "normalized_score": round(norm_score, 1) if norm_score is not None else None,
            "variance": variance,
            "variance_pct": variance_pct,
            "weight": flt(kpi.weight or 1.0),
            "achievement_status": ach_status,
            "direction": kpi.direction or "Higher is Better",
            "status": op_status,
            "open_alerts": open_alerts,
            "entry_date": entry_date_val,
        }
        data.append(row)

    return data


def get_chart(data):
    if not data:
        return None

    status_counts = {
        "Above Target": 0,
        "Meeting Target": 0,
        "Below Target": 0,
        "Missing Data": 0,
        "Unavailable": 0,
    }
    for d in data:
        st = d.get("achievement_status")
        if st in status_counts:
            status_counts[st] += 1
        else:
            status_counts["Missing Data"] += 1

    labels = [k for k, v in status_counts.items() if v > 0]
    values = [status_counts[k] for k in labels]

    if not values:
        return None

    return {
        "data": {
            "labels": labels,
            "datasets": [{"name": _("KPI Count"), "values": values}],
        },
        "type": "donut",
        "title": _("KPI Achievement & Target Status Distribution"),
        "colors": ["#27ae60", "#2ecc71", "#e74c3c", "#f39c12", "#95a5a6"],
    }


def get_summary(data):
    if not data:
        return []

    total_kpis = len(data)
    meeting = sum(1 for d in data if d.get("achievement_status") in ("Meeting Target", "Above Target"))
    below = sum(1 for d in data if d.get("achievement_status") == "Below Target")
    above = sum(1 for d in data if d.get("achievement_status") == "Above Target")
    missing = sum(1 for d in data if d.get("achievement_status") in ("Missing Data", "Unavailable"))

    scores = [flt(d["normalized_score"]) for d in data if d.get("normalized_score") is not None]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0

    return [
        {"label": _("Total KPIs"), "value": total_kpis, "datatype": "Int", "indicator": "blue"},
        {"label": _("Meeting Target"), "value": meeting, "datatype": "Int", "indicator": "green"},
        {"label": _("Above Target"), "value": above, "datatype": "Int", "indicator": "green"},
        {"label": _("Below Target"), "value": below, "datatype": "Int", "indicator": "red"},
        {"label": _("Missing Data"), "value": missing, "datatype": "Int", "indicator": "orange"},
        {"label": _("Avg Score /100"), "value": f"{avg_score}/100", "datatype": "Data", "indicator": "green" if avg_score >= 80 else ("orange" if avg_score >= 60 else "red")},
    ]
