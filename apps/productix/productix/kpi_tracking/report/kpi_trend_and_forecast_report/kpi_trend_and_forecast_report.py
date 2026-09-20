import frappe
from frappe import _
from frappe.utils import flt
from productix.kpi_tracking.report.report_utils import (
    get_authorized_departments_for_report,
    get_kpi_score_badge,
    get_status_badge,
)
from productix.kpi_tracking.services.analytics import (
    calculate_trend,
    calculate_growth,
    generate_multi_horizon_predictions,
)


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart(data, filters)
    summary = get_summary(data)
    return columns, data, None, chart, summary


def get_columns():
    return [
        {"label": _("Department"), "fieldname": "department_name", "fieldtype": "Data", "width": 140},
        {"label": _("KPI"), "fieldname": "kpi_name", "fieldtype": "Data", "width": 170},
        {"label": _("KPI Code"), "fieldname": "kpi", "fieldtype": "Link", "options": "KPI Definition", "width": 130},
        {"label": _("Latest Period"), "fieldname": "current_period", "fieldtype": "Data", "width": 110},
        {"label": _("Historical Score /100"), "fieldname": "score", "fieldtype": "Float", "width": 150},
        {"label": _("Previous Score"), "fieldname": "previous_score", "fieldtype": "Float", "width": 130},
        {"label": _("Growth %"), "fieldname": "growth_pct", "fieldtype": "Percent", "width": 100},
        {"label": _("Trend Direction"), "fieldname": "trend", "fieldtype": "Data", "width": 120},
        {"label": _("Trend Slope %"), "fieldname": "relative_slope", "fieldtype": "Percent", "width": 110},
        {"label": _("Forecast Horizon"), "fieldname": "forecast_horizon", "fieldtype": "Data", "width": 130},
        {"label": _("Forecast Value"), "fieldname": "predicted_value", "fieldtype": "Float", "width": 120},
        {"label": _("Forecast Confidence"), "fieldname": "confidence", "fieldtype": "Percent", "width": 140},
        {"label": _("Historical Points"), "fieldname": "data_points", "fieldtype": "Int", "width": 120},
        {"label": _("Prediction Status"), "fieldname": "prediction_status", "fieldtype": "Data", "width": 150},
        {"label": _("Prediction Notes"), "fieldname": "explanation", "fieldtype": "Data", "width": 280},
    ]


def get_data(filters):
    allowed_depts, active_dept = get_authorized_departments_for_report(filters)

    kpi_filters = {"is_active": 1, "department": ["in", allowed_depts]}
    if filters.get("kpi"):
        kpi_filters["name"] = filters.get("kpi")
    if filters.get("frequency") and filters.get("frequency") != "All":
        kpi_filters["frequency"] = filters.get("frequency")

    kpis = frappe.db.get_all(
        "KPI Definition",
        filters=kpi_filters,
        fields=["name", "kpi_name", "department", "frequency", "target_value", "unit", "direction"],
        order_by="department asc, kpi_name asc",
    )

    if not kpis:
        return []

    dept_names = {}
    for d in frappe.db.get_all("KPI Department", fields=["name", "department_name"]):
        dept_names[d.name] = d.department_name or d.name

    chosen_horizon = filters.get("horizon") or "next_month"
    trend_filter = filters.get("trend")

    data = []

    for kpi in kpis:
        dept_code = kpi.department
        dept_display = dept_names.get(dept_code, dept_code)

        # 1. Trend calculation from core analytics engine
        trend_res = calculate_trend(kpi.name, dept_code, periods=12)
        trend_val = trend_res.get("trend", "Stable")
        rel_slope = trend_res.get("relative_slope", 0.0)
        pts_count = trend_res.get("data_points", 0)

        # Apply trend filter
        if trend_filter and trend_filter != "All" and trend_val != trend_filter:
            continue

        # 2. Growth calculation from core analytics engine
        growth_res = calculate_growth(kpi.name, dept_code)
        growth_pct = growth_res.get("growth_percentage")
        cur_period = growth_res.get("current_period") or "No Data"

        # 3. Forecast / Prediction from core analytics engine
        pred_res = generate_multi_horizon_predictions(kpi.name, dept_code)

        # 4. Historical latest normalized scores
        entries = frappe.db.get_all(
            "KPI Data Entry",
            filters={"kpi": kpi.name, "department": dept_code, "docstatus": 1},
            fields=["achievement_percentage", "actual_value", "period"],
            order_by="entry_date desc",
            limit_page_length=2
        )

        cur_score = max(0.0, min(100.0, flt(entries[0].achievement_percentage))) if entries else None
        prev_score = max(0.0, min(100.0, flt(entries[1].achievement_percentage))) if len(entries) > 1 else None

        if pred_res.get("available"):
            h_data = pred_res.get(chosen_horizon) or pred_res.get("next_month") or {}
            predicted_val = h_data.get("predicted_value")
            confidence_val = h_data.get("confidence")
            h_name = h_data.get("horizon") or chosen_horizon.replace("_", " ").title()
            pred_status = "Ready"
            explanation = f"Confidence: {confidence_val}% | R²: {pred_res.get('r_squared', 'N/A')} ({pts_count} historical periods)"
        else:
            predicted_val = None
            confidence_val = None
            h_name = chosen_horizon.replace("_", " ").title()
            pred_status = "Unavailable"
            explanation = pred_res.get("message") or "Prediction unavailable: Requires at least 3 historical data entries."

        data.append({
            "department_name": dept_display,
            "department": dept_code,
            "kpi_name": kpi.kpi_name,
            "kpi": kpi.name,
            "current_period": cur_period,
            "score": round(cur_score, 1) if cur_score is not None else None,
            "previous_score": round(prev_score, 1) if prev_score is not None else None,
            "growth_pct": growth_pct,
            "trend": trend_val,
            "relative_slope": rel_slope,
            "forecast_horizon": h_name,
            "predicted_value": round(predicted_val, 2) if predicted_val is not None else None,
            "confidence": confidence_val,
            "data_points": pts_count,
            "prediction_status": pred_status,
            "explanation": explanation,
        })

    return data


def get_chart(data, filters):
    if not data:
        return None

    # If specific KPI is filtered, show detailed timeline: Historical Performance -> Forecast
    if filters.get("kpi"):
        target_kpi = filters.get("kpi")
        entries = frappe.db.get_all(
            "KPI Data Entry",
            filters={"kpi": target_kpi, "docstatus": 1},
            fields=["actual_value", "period", "achievement_percentage"],
            order_by="entry_date asc",
            limit_page_length=12
        )

        row = next((d for d in data if d["kpi"] == target_kpi), None)
        if not row:
            return None

        labels = [e.period for e in entries]
        historical_values = [flt(e.actual_value) for e in entries]
        forecast_values = [None] * len(historical_values)

        if row.get("predicted_value") is not None:
            labels.append(f"Forecast ({row.get('forecast_horizon')})")
            historical_values.append(None)
            # Connect the last historical point to forecast point
            forecast_values[-1] = flt(entries[-1].actual_value) if entries else None
            forecast_values.append(flt(row["predicted_value"]))

        return {
            "data": {
                "labels": labels,
                "datasets": [
                    {"name": _("Historical Actual"), "values": historical_values},
                    {"name": _("Forecast / Prediction"), "values": forecast_values},
                ],
            },
            "type": "line",
            "title": _("Historical Performance → Forecast Progression"),
            "colors": ["#3498db", "#e67e22"],
        }

    # If all KPIs, show distribution of Trend Directions
    improving = sum(1 for d in data if d["trend"] == "Improving")
    declining = sum(1 for d in data if d["trend"] == "Declining")
    stable = sum(1 for d in data if d["trend"] == "Stable")

    return {
        "data": {
            "labels": [_("Improving"), _("Stable"), _("Declining")],
            "datasets": [
                {"name": _("KPI Count"), "values": [improving, stable, declining]}
            ],
        },
        "type": "donut",
        "title": _("KPI Trend Direction Distribution"),
        "colors": ["#27ae60", "#3498db", "#e74c3c"],
    }


def get_summary(data):
    if not data:
        return []

    total_kpis = len(data)
    improving = sum(1 for d in data if d["trend"] == "Improving")
    declining = sum(1 for d in data if d["trend"] == "Declining")
    stable = sum(1 for d in data if d["trend"] == "Stable")
    ready_preds = sum(1 for d in data if d["prediction_status"] == "Ready")
    unavail_preds = sum(1 for d in data if d["prediction_status"] != "Ready")

    return [
        {"label": _("Total Tracked KPIs"), "value": total_kpis, "datatype": "Int", "indicator": "blue"},
        {"label": _("Improving Trend"), "value": improving, "datatype": "Int", "indicator": "green"},
        {"label": _("Stable Trend"), "value": stable, "datatype": "Int", "indicator": "blue"},
        {"label": _("Declining Trend"), "value": declining, "datatype": "Int", "indicator": "red" if declining > 0 else "green"},
        {"label": _("Predictions Ready"), "value": ready_preds, "datatype": "Int", "indicator": "green"},
        {"label": _("Insufficient History"), "value": unavail_preds, "datatype": "Int", "indicator": "orange" if unavail_preds > 0 else "green"},
    ]
