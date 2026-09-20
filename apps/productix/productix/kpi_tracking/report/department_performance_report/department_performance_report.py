import frappe
from frappe import _
from frappe.utils import flt
from productix.kpi_tracking.report.report_utils import (
    get_authorized_departments_for_report,
    get_kpi_score_badge,
    get_status_badge,
)
from productix.kpi_tracking.services.analytics import (
    get_department_performance,
    compute_growth,
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
        {"label": _("Department"), "fieldname": "department_name", "fieldtype": "Data", "width": 160},
        {"label": _("Department Code"), "fieldname": "department", "fieldtype": "Link", "options": "KPI Department", "width": 140},
        {"label": _("Reporting Period"), "fieldname": "period", "fieldtype": "Data", "width": 130},
        {"label": _("Department Score /100"), "fieldname": "score", "fieldtype": "Float", "width": 160},
        {"label": _("Previous Period Score"), "fieldname": "previous_score", "fieldtype": "Float", "width": 160},
        {"label": _("Change"), "fieldname": "score_change", "fieldtype": "Float", "width": 90},
        {"label": _("Growth %"), "fieldname": "growth_pct", "fieldtype": "Percent", "width": 100},
        {"label": _("Total KPIs"), "fieldname": "total_kpis", "fieldtype": "Int", "width": 90},
        {"label": _("KPIs Meeting Target"), "fieldname": "on_track", "fieldtype": "Int", "width": 150},
        {"label": _("KPIs Below Target"), "fieldname": "below_target", "fieldtype": "Int", "width": 140},
        {"label": _("Critical Exception KPIs"), "fieldname": "critical_count", "fieldtype": "Int", "width": 160},
        {"label": _("Critical KPI List"), "fieldname": "critical_kpi_names", "fieldtype": "Data", "width": 180},
        {"label": _("Open Alerts"), "fieldname": "open_alerts", "fieldtype": "Int", "width": 100},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 120},
    ]


def get_data(filters):
    allowed_depts, active_dept = get_authorized_departments_for_report(filters)

    target_depts = [active_dept] if active_dept else allowed_depts

    depts_doc = frappe.db.get_all(
        "KPI Department",
        filters={"name": ["in", target_depts], "is_active": 1},
        fields=["name", "department_name", "weight"],
        order_by="department_name asc",
    )

    if not depts_doc:
        return []

    # Map open alerts per department
    open_alerts_map = {}
    alerts_data = frappe.db.get_all(
        "KPI Alert",
        filters={"status": ["in", ["Active", "Acknowledged"]], "department": ["in", target_depts]},
        fields=["department", "count(name) as cnt"],
        group_by="department"
    )
    for a in alerts_data:
        open_alerts_map[a.department] = a.cnt

    period_filter = filters.get("period")
    frequency_filter = filters.get("frequency") if (filters.get("frequency") and filters.get("frequency") != "All") else None

    data = []

    for dept in depts_doc:
        dept_code = dept.name
        dept_title = dept.department_name or dept.name

        # Query all distinct historical periods for this department
        dept_periods = [r[0] for r in frappe.db.sql(
            """SELECT DISTINCT period FROM `tabKPI Data Entry` WHERE department = %s AND docstatus = 1 ORDER BY entry_date ASC""",
            (dept_code,)
        )]

        if period_filter:
            # Selected period
            eval_periods = [period_filter]
        elif dept_periods:
            # Show all historical periods for comprehensive comparison
            eval_periods = dept_periods
        else:
            # No data recorded yet
            eval_periods = ["No Data"]

        for idx, p_val in enumerate(eval_periods):
            if p_val == "No Data":
                perf = get_department_performance(dept_code, frequency=frequency_filter)
                cur_score = None
                prev_score = None
                change = 0.0
                growth_val = None
                on_track = 0
                warning = 0
                critical = 0
                critical_kpis = []
                total_kpis = perf.get("total_kpis", 0)
                status_label = "Pending / No Data"
            else:
                perf = get_department_performance(dept_code, period=p_val, frequency=frequency_filter)
                cur_score = perf.get("score")
                total_kpis = perf.get("total_kpis", 0)
                on_track = perf.get("on_track", 0)
                warning = perf.get("warning", 0)
                critical = perf.get("critical", 0)

                # Identify critical KPI names for drill-down visibility
                critical_kpis = [k["kpi"] for k in perf.get("kpis", []) if k.get("status") == "Critical"]

                # Find previous period score from historical sequence
                prev_period = None
                if p_val in dept_periods:
                    p_idx = dept_periods.index(p_val)
                    if p_idx > 0:
                        prev_period = dept_periods[p_idx - 1]
                elif idx > 0 and eval_periods[idx - 1] != "No Data":
                    prev_period = eval_periods[idx - 1]

                if prev_period:
                    prev_perf = get_department_performance(dept_code, period=prev_period, frequency=frequency_filter)
                    prev_score = prev_perf.get("score")
                else:
                    prev_score = None

                if cur_score is not None and prev_score is not None:
                    change = round(cur_score - prev_score, 1)
                    growth_res = compute_growth(cur_score, prev_score)
                    growth_val = growth_res.get("growth_percentage")
                else:
                    change = 0.0
                    growth_val = None

                if cur_score is not None:
                    if cur_score >= 80.0:
                        status_label = "On Track"
                    elif cur_score >= 60.0:
                        status_label = "Warning"
                    else:
                        status_label = "Critical"
                else:
                    status_label = "Pending / No Data"

            below_target = warning + critical
            open_alerts = open_alerts_map.get(dept_code, 0)

            # Apply status filter if present
            if filters.get("status") and filters.get("status") != "All":
                if status_label != filters.get("status"):
                    continue

            data.append({
                "department_name": dept_title,
                "department": dept_code,
                "period": p_val,
                "score": round(cur_score, 1) if cur_score is not None else None,
                "previous_score": round(prev_score, 1) if prev_score is not None else None,
                "score_change": change,
                "growth_pct": growth_val,
                "total_kpis": total_kpis,
                "on_track": on_track,
                "below_target": below_target,
                "critical_count": critical,
                "critical_kpi_names": ", ".join(critical_kpis) if critical_kpis else "None",
                "open_alerts": open_alerts,
                "status": status_label,
            })

    return data


def get_chart(data):
    if not data:
        return None

    # Group scores by department
    dept_scores = {}
    for d in data:
        dept = d.get("department_name")
        sc = d.get("score")
        if sc is not None:
            dept_scores.setdefault(dept, []).append(flt(sc))

    if not dept_scores:
        return None

    labels = list(dept_scores.keys())
    values = [round(sum(v) / len(v), 1) for v in dept_scores.values()]

    return {
        "data": {
            "labels": labels,
            "datasets": [
                {"name": _("Average Department Score"), "values": values}
            ],
        },
        "type": "bar",
        "title": _("Department Performance Score Comparison (/100)"),
        "colors": ["#4C51BF"],
    }


def get_summary(data):
    if not data:
        return []

    valid_scores = [flt(d["score"]) for d in data if d.get("score") is not None]
    avg_score = round(sum(valid_scores) / len(valid_scores), 1) if valid_scores else 0.0

    total_depts = len({d["department"] for d in data})
    total_kpis = sum(d.get("total_kpis", 0) for d in data)
    total_on_track = sum(d.get("on_track", 0) for d in data)
    total_below = sum(d.get("below_target", 0) for d in data)
    total_critical = sum(d.get("critical_count", 0) for d in data)
    total_alerts = sum(d.get("open_alerts", 0) for d in data)

    return [
        {"label": _("Departments"), "value": total_depts, "datatype": "Int", "indicator": "blue"},
        {"label": _("Avg Department Score"), "value": f"{avg_score}/100", "datatype": "Data", "indicator": "green" if avg_score >= 80 else ("orange" if avg_score >= 60 else "red")},
        {"label": _("KPIs Meeting Target"), "value": total_on_track, "datatype": "Int", "indicator": "green"},
        {"label": _("KPIs Below Target"), "value": total_below, "datatype": "Int", "indicator": "orange" if total_below > 0 else "green"},
        {"label": _("Critical Exceptions"), "value": total_critical, "datatype": "Int", "indicator": "red" if total_critical > 0 else "green"},
        {"label": _("Open Alerts"), "value": total_alerts, "datatype": "Int", "indicator": "red" if total_alerts > 0 else "green"},
    ]
