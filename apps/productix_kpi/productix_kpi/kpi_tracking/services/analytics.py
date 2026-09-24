import frappe
from frappe.utils import getdate, add_days, add_months, today
import math
from productix_kpi.kpi_tracking.services.period_engine import (
    get_current_period,
    resolve_canonical_period,
    get_next_period,
    get_previous_period,
    calculate_normalized_score,
    get_status_from_score,
)


def run_post_entry_analytics(kpi_data_entry):
    doc = frappe.get_doc("KPI Data Entry", kpi_data_entry)
    kpi = frappe.get_cached_doc("KPI Definition", doc.kpi)

    update_prediction_actual(doc.kpi, doc.department, doc.period, doc.actual_value)

    if kpi.prediction_enabled:
        generate_prediction(doc.kpi, doc.department)

    if kpi.alert_enabled:
        from productix_kpi.kpi_tracking.services.alert_engine import evaluate_alerts
        evaluate_alerts(doc.kpi, doc.department, doc.period)


def calculate_trend(kpi_code, department=None, periods=6):
    """
    Calculate chronological trend using the latest N periods.
    Queries latest entries in descending order then reverses to chronological order.
    """
    filters = {"kpi": kpi_code, "docstatus": 1}
    if department:
        filters["department"] = department

    # Query latest entries in descending order
    entries = frappe.db.get_all(
        "KPI Data Entry", filters=filters,
        fields=["actual_value", "entry_date", "period"],
        order_by="entry_date desc", limit_page_length=periods if periods else 50
    )

    if not entries or len(entries) < 2:
        return {
            "trend": "Stable",
            "slope": 0.0,
            "relative_slope": 0.0,
            "data_points": len(entries) if entries else 0
        }

    # Reverse to strictly chronological order (oldest to newest)
    entries.reverse()

    kpi_doc = frappe.get_cached_doc("KPI Definition", kpi_code)
    values = [float(e.actual_value or 0) for e in entries]

    n = len(values)
    x_vals = list(range(n))
    x_mean = sum(x_vals) / n
    y_mean = sum(values) / n
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, values))
    denominator = sum((x - x_mean) ** 2 for x in x_vals)
    slope = numerator / denominator if denominator != 0 else 0

    relative_slope = (slope / y_mean * 100) if y_mean != 0 else 0
    threshold = 0.5

    if abs(relative_slope) < threshold:
        trend = "Stable"
    elif kpi_doc.direction == "Lower is Better":
        trend = "Improving" if relative_slope < 0 else "Declining"
    else:
        trend = "Improving" if relative_slope > 0 else "Declining"

    return {
        "trend": trend,
        "slope": round(slope, 4),
        "relative_slope": round(relative_slope, 2),
        "data_points": n,
    }


def calculate_growth(kpi_code, department=None):
    """
    Calculate period-over-period growth between the two latest reporting periods.
    Handles zero baseline, negative values, and missing periods safely without NaN or Infinity.
    """
    filters = {"kpi": kpi_code, "docstatus": 1}
    if department:
        filters["department"] = department

    entries = frappe.db.get_all(
        "KPI Data Entry", filters=filters,
        fields=["actual_value", "period", "entry_date"],
        order_by="entry_date desc", limit_page_length=2
    )

    if not entries or len(entries) < 2:
        return {
            "growth_percentage": None,
            "formatted": "N/A",
            "status": "New Baseline" if entries else "Not Available",
            "current_value": entries[0].actual_value if entries else None,
            "previous_value": None,
            "current_period": entries[0].period if entries else None,
            "previous_period": None,
        }

    current = float(entries[0].actual_value or 0.0)
    previous = float(entries[1].actual_value or 0.0)

    growth_res = compute_growth(current, previous)

    # Check direction for status interpretation
    try:
        kpi_doc = frappe.get_cached_doc("KPI Definition", kpi_code)
        if kpi_doc and kpi_doc.direction == "Lower is Better":
            raw_growth = growth_res.get("growth_percentage")
            if raw_growth is not None:
                growth_res["status"] = "Improving" if raw_growth < 0 else ("Decline" if raw_growth > 0 else "Stable")
    except Exception:
        pass

    growth_res.update({
        "current_value": current,
        "previous_value": previous,
        "current_period": entries[0].period,
        "previous_period": entries[1].period,
    })
    return growth_res


def compute_growth(current, previous):
    """
    Pure mathematical growth calculation handling zero baselines, nulls, and negative values.
    """
    if current is None or previous is None:
        return {"growth_percentage": None, "formatted": "N/A", "status": "Not Available"}

    try:
        cur = float(current)
        prev = float(previous)
    except (ValueError, TypeError):
        return {"growth_percentage": None, "formatted": "N/A", "status": "Not Available"}

    if prev == 0.0:
        if cur == 0.0:
            return {"growth_percentage": 0.0, "formatted": "0.0%", "status": "Stable"}
        elif cur > 0.0:
            return {"growth_percentage": 100.0, "formatted": "+100.0%", "status": "Growth"}
        else:
            return {"growth_percentage": -100.0, "formatted": "-100.0%", "status": "Decline"}

    raw_growth = ((cur - prev) / abs(prev)) * 100.0
    if math.isnan(raw_growth) or math.isinf(raw_growth):
        return {"growth_percentage": 0.0, "formatted": "0.0%", "status": "Stable"}

    growth_pct = round(raw_growth, 2)
    prefix = "+" if growth_pct > 0 else ""
    formatted = f"{prefix}{growth_pct:.1f}%"
    status = "Growth" if growth_pct > 0.0 else ("Decline" if growth_pct < 0.0 else "Stable")

    return {
        "growth_percentage": growth_pct,
        "formatted": formatted,
        "status": status,
    }


def generate_multi_horizon_predictions(kpi_code, department=None):
    """
    Generate forecasts for Tomorrow, Next Week, Next Month, and Next Quarter
    using Ordinary Least Squares (OLS) Linear Regression with R² confidence modeling.
    Requires at least 3 historical data points; returns unavailable status otherwise.
    """
    filters = {"kpi": kpi_code, "docstatus": 1}
    if department:
        filters["department"] = department

    # Fetch up to 60 historical entries chronologically
    entries = frappe.db.get_all(
        "KPI Data Entry", filters=filters,
        fields=["actual_value", "period", "entry_date"],
        order_by="entry_date desc", limit_page_length=60
    )

    if not entries or len(entries) < 3:
        return {
            "available": False,
            "status": "insufficient_data",
            "message": "Prediction unavailable: Requires at least 3 historical data entries.",
            "data_points": len(entries) if entries else 0,
            "tomorrow": None,
            "next_week": None,
            "next_month": None,
            "next_quarter": None,
        }

    # Chronological order
    entries.reverse()

    kpi_doc = frappe.get_cached_doc("KPI Definition", kpi_code)
    freq = (kpi_doc.frequency or "Daily").capitalize()

    values = [float(e.actual_value or 0) for e in entries]
    n = len(values)
    x_vals = list(range(n))
    x_mean = sum(x_vals) / n
    y_mean = sum(values) / n

    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, values))
    denominator = sum((x - x_mean) ** 2 for x in x_vals)
    slope = numerator / denominator if denominator != 0 else 0
    intercept = y_mean - slope * x_mean

    y_pred = [slope * x + intercept for x in x_vals]
    ss_res = sum((y - yp) ** 2 for y, yp in zip(values, y_pred))
    ss_tot = sum((y - y_mean) ** 2 for y in values)
    r_squared = 1.0 - (ss_res / ss_tot) if ss_tot != 0 else 1.0
    r_squared = max(0.0, min(1.0, r_squared))

    # Base confidence score scaled between 70% and 98% based on real R²
    confidence = round(max(70.0, min(98.0, 70.0 + (r_squared * 28.0))), 1)

    cur_val = values[-1]

    # Compute horizon steps based on reporting frequency
    if freq == "Daily":
        pred_tomorrow = slope * n + intercept
        pred_next_week = slope * (n + 6) + intercept
        pred_next_month = slope * (n + 29) + intercept
        pred_next_quarter = slope * (n + 89) + intercept
    elif freq == "Weekly":
        pred_tomorrow = cur_val + (slope / 7.0)
        pred_next_week = slope * n + intercept
        pred_next_month = slope * (n + 3) + intercept
        pred_next_quarter = slope * (n + 12) + intercept
    elif freq == "Monthly":
        pred_tomorrow = cur_val + (slope / 30.0)
        pred_next_week = cur_val + (slope / 4.0)
        pred_next_month = slope * n + intercept
        pred_next_quarter = slope * (n + 2) + intercept
    else:  # Quarterly or Yearly
        pred_tomorrow = cur_val + (slope / 90.0)
        pred_next_week = cur_val + (slope / 12.0)
        pred_next_month = cur_val + (slope / 3.0)
        pred_next_quarter = slope * n + intercept

    # Prevent negative values if all historical values and targets are positive
    target_val = float(kpi_doc.target_value or 0)
    if all(v >= 0 for v in values) and target_val >= 0:
        pred_tomorrow = max(0.0, pred_tomorrow)
        pred_next_week = max(0.0, pred_next_week)
        pred_next_month = max(0.0, pred_next_month)
        pred_next_quarter = max(0.0, pred_next_quarter)

    return {
        "available": True,
        "status": "ready",
        "data_points": n,
        "r_squared": round(r_squared, 3),
        "tomorrow": {
            "predicted_value": round(pred_tomorrow, 2),
            "confidence": max(65.0, min(98.0, confidence)),
            "horizon": "Tomorrow",
            "target_period": "Next Day"
        },
        "next_week": {
            "predicted_value": round(pred_next_week, 2),
            "confidence": max(60.0, min(98.0, round(confidence - 1.0, 1))),
            "horizon": "Next Week",
            "target_period": "Next Week"
        },
        "next_month": {
            "predicted_value": round(pred_next_month, 2),
            "confidence": max(55.0, min(98.0, round(confidence - 2.0, 1))),
            "horizon": "Next Month",
            "target_period": "Next Month"
        },
        "next_quarter": {
            "predicted_value": round(pred_next_quarter, 2),
            "confidence": max(50.0, min(98.0, round(confidence - 4.0, 1))),
            "horizon": "Next Quarter",
            "target_period": "Next Quarter"
        },
    }


def generate_prediction(kpi_code, department=None):
    settings = frappe.get_cached_doc("KPI Settings")
    min_points = settings.min_prediction_data_points or 3

    filters = {"kpi": kpi_code, "docstatus": 1}
    if department:
        filters["department"] = department

    entries = frappe.db.get_all(
        "KPI Data Entry", filters=filters,
        fields=["actual_value", "period", "entry_date"],
        order_by="entry_date desc", limit_page_length=50
    )

    if not entries or len(entries) < min_points:
        return None

    entries.reverse()

    values = [float(e.actual_value or 0) for e in entries]
    n = len(values)
    x_vals = list(range(n))
    x_mean = sum(x_vals) / n
    y_mean = sum(values) / n

    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, values))
    denominator = sum((x - x_mean) ** 2 for x in x_vals)
    slope = numerator / denominator if denominator != 0 else 0
    intercept = y_mean - slope * x_mean

    predicted_value = slope * n + intercept

    y_pred = [slope * x + intercept for x in x_vals]
    ss_res = sum((y - yp) ** 2 for y, yp in zip(values, y_pred))
    ss_tot = sum((y - y_mean) ** 2 for y in values)
    r_squared = 1.0 - (ss_res / ss_tot) if ss_tot != 0 else 1.0
    confidence = max(65.0, min(98.0, round(70.0 + (r_squared * 28.0), 1)))

    kpi_doc = frappe.get_cached_doc("KPI Definition", kpi_code)
    if all(v >= 0 for v in values) and float(kpi_doc.target_value or 0) >= 0:
        predicted_value = max(0.0, predicted_value)

    last_period = entries[-1].period if entries else None
    if last_period:
        target_period = get_next_period(kpi_doc.frequency or "Daily", last_period)
    else:
        target_period = get_next_period(kpi_doc.frequency or "Daily", get_current_period(kpi_doc.frequency or "Daily"))

    existing = frappe.db.exists("KPI Prediction", {
        "kpi": kpi_code, "department": department or "",
        "target_period": target_period, "status": "Pending",
    })
    if existing:
        doc = frappe.get_doc("KPI Prediction", existing)
        doc.predicted_value = round(predicted_value, 2)
        doc.confidence = round(confidence, 1)
        doc.data_points_used = n
        doc.save(ignore_permissions=True)
        return doc

    pred = frappe.get_doc({
        "doctype": "KPI Prediction",
        "kpi": kpi_code,
        "department": department or "",
        "target_period": target_period,
        "predicted_value": round(predicted_value, 2),
        "prediction_method": "Linear Regression",
        "confidence": round(confidence, 1),
        "data_points_used": n,
        "status": "Pending",
    })
    pred.insert(ignore_permissions=True)
    return pred


def update_prediction_actual(kpi_code, department, period, actual_value):
    predictions = frappe.db.get_all(
        "KPI Prediction",
        filters={
            "kpi": kpi_code, "department": department,
            "target_period": period, "status": "Pending",
        },
        fields=["name"],
    )
    for p in predictions:
        pred_doc = frappe.get_doc("KPI Prediction", p.name)
        pred_doc.update_actual(actual_value)


def get_department_performance(department, timeframe="6_months", horizon="next_month", period=None, frequency=None, include_predictions=False):
    period_limit = 6 if timeframe == "6_months" else (12 if timeframe == "overall" else (1 if timeframe in ("today", "recent") else 3))

    filters = {"department": department, "is_active": 1}
    if frequency and frequency != "All":
        filters["frequency"] = frequency

    kpis = frappe.db.get_all(
        "KPI Definition",
        filters=filters,
        fields=["name", "kpi_name", "weight", "target_value", "direction",
                "unit", "warning_threshold", "critical_threshold", "frequency"],
    )

    if not kpis:
        return {
            "score": None, "status": "No KPIs", "total_kpis": 0,
            "on_track": 0, "warning": 0, "critical": 0, "missing": 0,
            "kpis": [], "history": [], "predictions": {"available": False, "message": "No KPIs defined."},
            "trend": "Stable",
        }

    total_weight = 0.0
    weighted_score = 0.0
    on_track = warning = critical = missing = 0
    kpi_details = []
    d_today = getdate(today())

    for kpi in kpis:
        freq = kpi.frequency or "Monthly"
        target_period = resolve_canonical_period(freq, period, d_today)
        entry_filters = {
            "kpi": kpi.name,
            "department": department,
            "period": target_period,
            "docstatus": 1
        }

        latest = frappe.db.get_value(
            "KPI Data Entry",
            entry_filters,
            ["actual_value", "achievement_percentage", "normalized_score", "status", "period", "entry_date"],
            order_by="creation desc", as_dict=True,
        )

        if include_predictions:
            multi_preds = generate_multi_horizon_predictions(kpi.name, department)
            chosen_pred = multi_preds.get(horizon) or multi_preds.get("next_month") if multi_preds.get("available") else None
        else:
            multi_preds = {"available": False}
            chosen_pred = None

        if not latest:
            missing += 1
            kpi_details.append({
                "kpi": kpi.kpi_name,
                "kpi_code": kpi.name,
                "status": "Pending / No Data",
                "actual": None,
                "target": kpi.target_value,
                "unit": kpi.unit or "",
                "weight": float(kpi.weight or 1.0),
                "frequency": freq,
                "achievement": None,
                "normalized_score": None,
                "trend": "Stable",
                "growth": None,
                "period": target_period,
                "prediction": chosen_pred,
                "predictions_all": multi_preds,
            })
            continue

        weight = float(kpi.weight or 1.0)
        total_weight += weight
        norm_sc = float(latest.normalized_score) if latest.get("normalized_score") is not None else max(0.0, min(100.0, float(latest.achievement_percentage or 0.0)))
        ach = float(latest.achievement_percentage) if latest.get("achievement_percentage") is not None else None
        weighted_score += norm_sc * weight

        status_val = latest.status or "Pending / No Data"
        if status_val == "On Track":
            on_track += 1
        elif status_val == "Warning":
            warning += 1
        elif status_val == "Critical":
            critical += 1
        else:
            missing += 1

        trend_data = calculate_trend(kpi.name, department, period_limit)
        growth_data = calculate_growth(kpi.name, department)

        kpi_details.append({
            "kpi": kpi.kpi_name, "kpi_code": kpi.name,
            "actual": latest.actual_value, "target": kpi.target_value,
            "unit": kpi.unit or "",
            "achievement": ach,
            "normalized_score": norm_sc,
            "status": status_val,
            "period": latest.period or target_period, "weight": weight,
            "frequency": freq,
            "trend": trend_data.get("trend"),
            "growth": growth_data.get("growth_percentage"),
            "prediction": chosen_pred,
            "predictions_all": multi_preds,
        })

    score = round(max(0.0, min(100.0, weighted_score / total_weight)), 1) if total_weight > 0 else None

    # Department-level historical timeline
    dept_periods = [r[0] for r in frappe.db.sql(
        """SELECT DISTINCT period FROM `tabKPI Data Entry` WHERE department = %s AND docstatus = 1 ORDER BY entry_date ASC""",
        (department,)
    )]
    if period_limit and len(dept_periods) > period_limit:
        dept_periods = dept_periods[-period_limit:]

    dept_history = []
    for p in dept_periods:
        entries = frappe.db.get_all(
            "KPI Data Entry",
            filters={"department": department, "period": p, "docstatus": 1},
            fields=["achievement_percentage"]
        )
        if entries:
            avg_sc = sum(max(0.0, min(100.0, float(e.achievement_percentage or 0.0))) for e in entries) / len(entries)
            dept_history.append({"period": p, "score": round(max(0.0, min(100.0, avg_sc)), 1)})

    # Department predictions
    dept_predictions = {"available": False, "message": "Prediction unavailable: Insufficient historical periods (requires ≥ 3 periods)."}
    dept_trend = "Stable"
    dept_growth = None
    if len(dept_history) >= 2:
        sc_vals = [h["score"] for h in dept_history]
        if sc_vals[-2] != 0:
            dept_growth = round(((sc_vals[-1] - sc_vals[-2]) / sc_vals[-2]) * 100, 2)
        else:
            dept_growth = 0.0

    if len(dept_history) >= 3:
        sc_vals = [h["score"] for h in dept_history]
        n_sc = len(sc_vals)
        x_m = (n_sc - 1) / 2
        y_m = sum(sc_vals) / n_sc
        num_sc = sum((i - x_m) * (s - y_m) for i, s in enumerate(sc_vals))
        den_sc = sum((i - x_m) ** 2 for i in range(n_sc))
        sc_slope = num_sc / den_sc if den_sc != 0 else 0
        sc_cur = sc_vals[-1]

        yp = [sc_slope * i + (y_m - sc_slope * x_m) for i in range(n_sc)]
        ss_r = sum((s - ypi) ** 2 for s, ypi in zip(sc_vals, yp))
        ss_t = sum((s - y_m) ** 2 for s in sc_vals)
        r2_sc = 1.0 - (ss_r / ss_t) if ss_t != 0 else 1.0
        conf_sc = round(max(70.0, min(98.0, 70.0 + (r2_sc * 28.0))), 1)

        dept_trend = "Improving" if sc_slope > 0.5 else ("Declining" if sc_slope < -0.5 else "Stable")
        dept_predictions = {
            "available": True,
            "tomorrow": {"predicted_score": round(max(0.0, min(100.0, sc_cur + (sc_slope / 30.0))), 1), "confidence": conf_sc, "horizon": "Tomorrow", "target_period": "Tomorrow"},
            "next_week": {"predicted_score": round(max(0.0, min(100.0, sc_cur + (sc_slope / 4.0))), 1), "confidence": max(65.0, round(conf_sc - 1.0, 1)), "horizon": "Next Week", "target_period": "Next Week"},
            "next_month": {"predicted_score": round(max(0.0, min(100.0, sc_cur + sc_slope)), 1), "confidence": max(60.0, round(conf_sc - 2.0, 1)), "horizon": "Next Month", "target_period": "Next Month"},
            "next_quarter": {"predicted_score": round(max(0.0, min(100.0, sc_cur + (sc_slope * 3.0))), 1), "confidence": max(55.0, round(conf_sc - 4.0, 1)), "horizon": "Next Quarter", "target_period": "Next Quarter"},
        }

    return {
        "score": score, "total_kpis": len(kpis),
        "on_track": on_track, "warning": warning,
        "critical": critical, "missing": missing,
        "kpis": kpi_details,
        "history": dept_history,
        "growth": dept_growth,
        "trend": dept_trend,
        "predictions": dept_predictions,
        "selected_prediction": dept_predictions.get(horizon) or dept_predictions.get("next_month") if dept_predictions.get("available") else None,
    }


def get_company_performance(timeframe="6_months", horizon="next_month", period=None, frequency=None, departments=None):
    period_limit = 6 if timeframe == "6_months" else (12 if timeframe == "overall" else (1 if timeframe in ("today", "recent") else 3))

    dept_filters = {"is_active": 1}
    if departments:
        dept_filters["name"] = ["in", departments]

    dept_docs = frappe.db.get_all(
        "KPI Department", filters=dept_filters,
        fields=["name", "department_name", "department_code", "weight", "location"],
        order_by="department_name asc"
    )

    distinct_periods = [r[0] for r in frappe.db.sql(
        "SELECT DISTINCT period FROM `tabKPI Data Entry` WHERE docstatus = 1 ORDER BY entry_date ASC"
    )]
    if period_limit and len(distinct_periods) > period_limit:
        distinct_periods = distinct_periods[-period_limit:]

    company_history = []
    for p in distinct_periods:
        weighted_sum = 0.0
        total_w = 0.0
        for dept in dept_docs:
            entries = frappe.db.get_all(
                "KPI Data Entry",
                filters={"department": dept.name, "period": p, "docstatus": 1},
                fields=["achievement_percentage", "normalized_score"]
            )
            if entries:
                avg_ach = sum(
                    float(e.normalized_score) if e.get("normalized_score") is not None
                    else max(0.0, min(100.0, float(e.achievement_percentage or 0.0)))
                    for e in entries
                ) / len(entries)
                w = float(dept.weight or 1.0)
                weighted_sum += avg_ach * w
                total_w += w
        sc = round(max(0.0, min(100.0, weighted_sum / total_w)), 1) if total_w > 0 else None
        if sc is not None:
            company_history.append({"period": p, "score": sc})

    company_growth = None
    company_trend = "Stable"
    company_slope = 0.0
    company_rel_slope = 0.0
    company_predictions = {"available": False, "message": "Prediction unavailable: Insufficient historical periods (requires ≥ 3 periods)."}

    if len(company_history) >= 2:
        scores = [h["score"] for h in company_history]
        if scores[-2] != 0:
            company_growth = round(((scores[-1] - scores[-2]) / scores[-2]) * 100, 2)
        else:
            company_growth = 0.0

    if len(company_history) >= 3:
        scores = [h["score"] for h in company_history]
        n = len(scores)
        x_mean = (n - 1) / 2
        y_mean = sum(scores) / n
        num = sum((i - x_mean) * (s - y_mean) for i, s in enumerate(scores))
        den = sum((i - x_mean) ** 2 for i in range(n))
        slope = num / den if den != 0 else 0
        intercept = y_mean - slope * x_mean
        company_slope = round(slope, 2)
        company_rel_slope = round((slope / y_mean) * 100, 2) if y_mean != 0 else 0.0
        company_trend = "Improving" if company_rel_slope > 0.5 else ("Declining" if company_rel_slope < -0.5 else "Stable")

        y_pred = [slope * i + intercept for i in range(n)]
        ss_res = sum((s - yp) ** 2 for s, yp in zip(scores, y_pred))
        ss_tot = sum((s - y_mean) ** 2 for s in scores)
        r2 = 1.0 - (ss_res / ss_tot) if ss_tot != 0 else 1.0
        conf = round(max(70.0, min(98.0, 70.0 + (r2 * 28.0))), 1)

        cur_sc = scores[-1]
        company_predictions = {
            "available": True,
            "tomorrow": {"predicted_score": round(max(0.0, min(100.0, cur_sc + (slope / 30.0))), 1), "confidence": conf, "horizon": "Tomorrow", "target_period": "Tomorrow"},
            "next_week": {"predicted_score": round(max(0.0, min(100.0, cur_sc + (slope / 4.0))), 1), "confidence": max(65.0, round(conf - 1.0, 1)), "horizon": "Next Week", "target_period": "Next Week"},
            "next_month": {"predicted_score": round(max(0.0, min(100.0, cur_sc + slope)), 1), "confidence": max(60.0, round(conf - 2.0, 1)), "horizon": "Next Month", "target_period": "Next Month"},
            "next_quarter": {"predicted_score": round(max(0.0, min(100.0, cur_sc + (slope * 3.0))), 1), "confidence": max(55.0, round(conf - 4.0, 1)), "horizon": "Next Quarter", "target_period": "Next Quarter"},
        }

    total_weight = 0.0
    weighted_score = 0.0
    dept_details = []

    for dept in dept_docs:
        perf = get_department_performance(
            dept.name, timeframe=timeframe, horizon=horizon,
            period=period, frequency=frequency
        )
        weight = float(dept.weight or 1.0)
        if perf["score"] is not None:
            total_weight += weight
            weighted_score += perf["score"] * weight

        label = dept.department_name or dept.name
        if dept.get("location"):
            label += f" — {dept.location}"
        code = dept.get("department_code") or dept.name
        if code and code != label:
            label += f" [{code}]"

        dept_details.append({
            "department": label,
            "department_raw_name": dept.department_name,
            "department_code": dept.name,
            "location": dept.get("location") or "",
            "score": perf["score"], "weight": weight,
            "on_track": perf["on_track"], "warning": perf["warning"],
            "critical": perf["critical"], "missing": perf["missing"],
            "total_kpis": perf.get("total_kpis", 0),
        })

    company_score = round(max(0.0, min(100.0, weighted_score / total_weight)), 1) if total_weight > 0 else None

    return {
        "score": company_score,
        "departments": dept_details,
        "total_departments": len(dept_docs),
        "history": company_history,
        "growth": company_growth,
        "trend": company_trend,
        "relative_slope": company_rel_slope,
        "predictions": company_predictions,
        "selected_prediction": company_predictions.get(horizon) or company_predictions.get("next_month") if company_predictions.get("available") else None,
    }
