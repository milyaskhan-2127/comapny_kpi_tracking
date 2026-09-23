import frappe
from frappe.utils import getdate, today, flt, date_diff
import json
import math


def calculate_reading_health(reading_doc):
    machine = frappe.get_cached_doc("Machine", reading_doc.machine)
    machine_type = frappe.get_cached_doc("Machine Type", machine.machine_type)

    param_config = {}
    for p in machine_type.parameters:
        param_config[p.parameter_code] = p

    total_weight = 0
    weighted_score = 0
    required_count = 0
    required_provided = 0
    category_scores = {}

    for row in reading_doc.readings:
        cfg = param_config.get(row.parameter_code)
        if not cfg:
            row.status = "Unknown"
            row.is_anomaly = 0
            continue

        if cfg.is_required:
            required_count += 1

        score, status, is_anomaly = _score_parameter(row.value, cfg)

        row.status = status
        row.is_anomaly = 1 if is_anomaly else 0

        weight = flt(cfg.weight) or 1.0
        weighted_score += score * weight
        total_weight += weight

        if cfg.is_required:
            required_provided += 1

        cat = cfg.parameter_category or "Other"
        if cat not in category_scores:
            category_scores[cat] = {"total_weight": 0, "weighted_score": 0}
        category_scores[cat]["total_weight"] += weight
        category_scores[cat]["weighted_score"] += score * weight

    health_score = (weighted_score / total_weight) if total_weight > 0 else 0
    health_score = max(0, min(100, round(health_score, 2)))
    health_status = _get_health_status(health_score)

    if required_count == 0:
        data_quality = "Complete"
    elif required_provided == required_count:
        data_quality = "Complete"
    elif required_provided >= required_count * 0.5:
        data_quality = "Partial"
    else:
        data_quality = "Insufficient"

    return {
        "health_score": health_score,
        "health_status": health_status,
        "data_quality": data_quality,
        "category_scores": category_scores,
    }


def _score_parameter(value, cfg):
    value = flt(value)

    has_normal = cfg.normal_min is not None or cfg.normal_max is not None
    has_warning = cfg.warning_min is not None or cfg.warning_max is not None
    has_critical = cfg.critical_min is not None or cfg.critical_max is not None

    if not has_normal and not has_warning and not has_critical:
        return 100, "Normal", False

    n_min = flt(cfg.normal_min) if cfg.normal_min is not None else None
    n_max = flt(cfg.normal_max) if cfg.normal_max is not None else None
    w_min = flt(cfg.warning_min) if cfg.warning_min is not None else None
    w_max = flt(cfg.warning_max) if cfg.warning_max is not None else None
    c_min = flt(cfg.critical_min) if cfg.critical_min is not None else None
    c_max = flt(cfg.critical_max) if cfg.critical_max is not None else None

    if _in_range(value, n_min, n_max):
        return 100, "Normal", False

    if _in_range(value, w_min, w_max):
        if has_normal and n_min is not None and n_max is not None:
            mid = (n_min + n_max) / 2
            outer = max(
                abs(flt(w_min) - mid) if w_min is not None else 0,
                abs(flt(w_max) - mid) if w_max is not None else 0,
            )
            dist = abs(value - mid)
            inner = (n_max - n_min) / 2
            if outer > inner and outer > 0:
                ratio = (dist - inner) / (outer - inner)
                score = 100 - (ratio * 40)
                return max(60, min(100, round(score, 2))), "Warning", False
        return 70, "Warning", False

    if has_critical and _in_range(value, c_min, c_max):
        return 30, "Critical", True

    if has_critical:
        return 10, "Critical", True

    return 30, "Critical", True


def _in_range(value, low, high):
    if low is not None and high is not None:
        return low <= value <= high
    if low is not None:
        return value >= low
    if high is not None:
        return value <= high
    return True


def _get_health_status(score):
    if score >= 85:
        return "Healthy"
    elif score >= 70:
        return "Good"
    elif score >= 50:
        return "Warning"
    else:
        return "Critical"


def update_machine_health(machine_name):
    latest = frappe.db.get_all(
        "Machine Reading",
        filters={"machine": machine_name, "docstatus": 1},
        fields=["name", "health_score", "health_status", "reading_date"],
        order_by="reading_date desc",
        limit_page_length=1,
    )

    if latest:
        reading = latest[0]
        frappe.db.set_value("Machine", machine_name, {
            "health_score": reading.health_score,
            "health_status": reading.health_status,
            "last_reading_date": reading.reading_date,
        }, update_modified=False)

        _create_health_log(machine_name, reading)
        _sync_linked_kpis(machine_name, reading)
    else:
        frappe.db.set_value("Machine", machine_name, {
            "health_score": 0,
            "health_status": "",
            "last_reading_date": None,
        }, update_modified=False)


def _sync_linked_kpis(machine_name, reading):
    try:
        machine = frappe.get_cached_doc("Machine", machine_name)
        if not hasattr(machine, "linked_kpis") or not machine.linked_kpis:
            return

        from productix.kpi_tracking.services.period_engine import get_current_period

        for link in machine.linked_kpis:
            kpi_code = link.kpi
            if not kpi_code or not frappe.db.exists("KPI Definition", kpi_code):
                continue

            kpi_doc = frappe.get_cached_doc("KPI Definition", kpi_code)
            target_period = get_current_period(kpi_doc.frequency or "Daily", reading.reading_date)

            existing = frappe.db.get_value(
                "KPI Data Entry",
                {"kpi": kpi_code, "department": machine.department, "period": target_period, "docstatus": ["<", 2]},
                "name"
            )

            if not existing:
                entry = frappe.get_doc({
                    "doctype": "KPI Data Entry",
                    "kpi": kpi_code,
                    "department": machine.department,
                    "actual_value": reading.health_score,
                    "entry_date": reading.reading_date,
                    "period": target_period,
                    "entered_by": frappe.session.user if frappe.session.user != "Guest" else "Administrator",
                })
                entry.insert(ignore_permissions=True)
                entry.submit()
    except Exception:
        pass


def _create_health_log(machine_name, reading):
    existing = frappe.db.exists("Machine Health Log", {
        "machine": machine_name,
        "log_date": reading.reading_date,
    })
    if existing:
        frappe.db.set_value("Machine Health Log", existing, {
            "health_score": reading.health_score,
            "health_status": reading.health_status,
        })
        return

    reading_doc = frappe.get_doc("Machine Reading", reading.name)
    category_scores = {}
    machine_type_name = frappe.db.get_value("Machine", machine_name, "machine_type")
    if machine_type_name:
        machine_type = frappe.get_cached_doc("Machine Type", machine_type_name)
        param_config = {p.parameter_code: p for p in machine_type.parameters}
        for row in reading_doc.readings:
            cfg = param_config.get(row.parameter_code)
            if not cfg:
                continue
            cat = cfg.parameter_category or "Other"
            weight = flt(cfg.weight) or 1.0
            score, _, _ = _score_parameter(row.value, cfg)
            if cat not in category_scores:
                category_scores[cat] = {"score": 0, "weight": 0}
            category_scores[cat]["score"] += score * weight
            category_scores[cat]["weight"] += weight

    for cat in category_scores:
        w = category_scores[cat]["weight"]
        category_scores[cat] = round(category_scores[cat]["score"] / w, 2) if w else 0

    log = frappe.new_doc("Machine Health Log")
    log.machine = machine_name
    log.log_date = reading.reading_date
    log.health_score = reading.health_score
    log.health_status = reading.health_status
    log.component_scores = json.dumps(category_scores)
    log.insert(ignore_permissions=True)


def get_machine_health_summary(machine_name):
    machine = frappe.get_cached_doc("Machine", machine_name)

    history = frappe.db.get_all(
        "Machine Health Log",
        filters={"machine": machine_name},
        fields=["log_date", "health_score", "health_status", "component_scores"],
        order_by="log_date desc",
        limit_page_length=90,
    )

    trend = _calculate_machine_trend(history)
    prediction = _predict_machine_health(history)

    return {
        "machine": machine.as_dict(),
        "history": history,
        "trend": trend,
        "prediction": prediction,
    }


def _calculate_machine_trend(history):
    if len(history) < 2:
        return {"direction": "Stable", "slope": 0, "data_points": len(history)}

    scores = [h.health_score for h in reversed(history)]
    n = len(scores)
    x_vals = list(range(n))

    x_mean = sum(x_vals) / n
    y_mean = sum(scores) / n

    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, scores))
    denominator = sum((x - x_mean) ** 2 for x in x_vals)

    slope = numerator / denominator if denominator else 0

    if slope > 0.5:
        direction = "Improving"
    elif slope < -0.5:
        direction = "Declining"
    else:
        direction = "Stable"

    return {"direction": direction, "slope": round(slope, 4), "data_points": n}


def _predict_machine_health(history):
    if len(history) < 5:
        return None

    scores = [h.health_score for h in reversed(history)]
    n = len(scores)
    x_vals = list(range(n))

    x_mean = sum(x_vals) / n
    y_mean = sum(scores) / n

    ss_xy = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, scores))
    ss_xx = sum((x - x_mean) ** 2 for x in x_vals)

    if ss_xx == 0:
        return None

    slope = ss_xy / ss_xx
    intercept = y_mean - slope * x_mean

    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(x_vals, scores))
    ss_tot = sum((y - y_mean) ** 2 for y in scores)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

    predicted_next = slope * n + intercept
    predicted_next = max(0, min(100, round(predicted_next, 2)))
    predicted_week = slope * (n + 7) + intercept
    predicted_week = max(0, min(100, round(predicted_week, 2)))

    confidence = max(0, min(100, round(r_squared * 100, 1)))

    return {
        "next_day": predicted_next,
        "next_week": predicted_week,
        "confidence": confidence,
        "slope": round(slope, 4),
    }


def get_department_machines_health(department):
    machines = frappe.db.get_all(
        "Machine",
        filters={"department": department, "is_active": 1},
        fields=[
            "name", "machine_name", "machine_code", "machine_type",
            "operating_status", "health_score", "health_status",
            "last_reading_date", "location",
        ],
        order_by="health_score asc",
    )

    if not machines:
        return {"machines": [], "summary": _empty_summary()}

    total = len(machines)
    healthy = sum(1 for m in machines if m.health_status == "Healthy")
    good = sum(1 for m in machines if m.health_status == "Good")
    warning = sum(1 for m in machines if m.health_status == "Warning")
    critical = sum(1 for m in machines if m.health_status == "Critical")
    no_data = sum(1 for m in machines if not m.health_status)
    avg_score = sum(m.health_score or 0 for m in machines) / total if total else 0

    return {
        "machines": machines,
        "summary": {
            "total": total,
            "healthy": healthy,
            "good": good,
            "warning": warning,
            "critical": critical,
            "no_data": no_data,
            "avg_score": round(avg_score, 2),
        },
    }


def _empty_summary():
    return {
        "total": 0, "healthy": 0, "good": 0,
        "warning": 0, "critical": 0, "no_data": 0, "avg_score": 0,
    }


def get_company_machines_health(departments=None):
    dept_filters = {"is_active": 1}
    if departments:
        dept_filters["name"] = ["in", departments]

    depts = frappe.db.get_all(
        "KPI Department", filters=dept_filters,
        fields=["name", "department_name", "department_code", "location"],
        order_by="department_name asc",
    )

    result = []
    for dept in depts:
        dept_health = get_department_machines_health(dept.name)
        d_name = dept.department_name or dept.name
        if dept.get("location"):
            d_name += f" — {dept.location}"
        code = dept.get("department_code") or dept.name
        if code and code != d_name:
            d_name += f" [{code}]"
        result.append({
            "department": dept.name,
            "department_name": d_name,
            "department_code": dept.get("department_code") or dept.name,
            **dept_health["summary"],
        })

    machine_filters = {"is_active": 1}
    if departments:
        machine_filters["department"] = ["in", departments]

    all_machines = frappe.db.get_all(
        "Machine", filters=machine_filters,
        fields=["health_score", "health_status"],
    )
    total = len(all_machines)
    avg = sum(m.health_score or 0 for m in all_machines) / total if total else 0

    return {
        "departments": result,
        "company_summary": {
            "total_machines": total,
            "avg_score": round(avg, 2),
            "healthy": sum(1 for m in all_machines if m.health_status == "Healthy"),
            "good": sum(1 for m in all_machines if m.health_status == "Good"),
            "warning": sum(1 for m in all_machines if m.health_status == "Warning"),
            "critical": sum(1 for m in all_machines if m.health_status == "Critical"),
            "no_data": sum(1 for m in all_machines if not m.health_status),
        },
    }


def run_scheduled_health_check():
    machines = frappe.db.get_all(
        "Machine",
        filters={"is_active": 1, "operating_status": "Operational"},
        fields=["name", "machine_name", "health_score", "health_status",
                "last_reading_date", "maintenance_frequency_days", "last_maintenance_date"],
    )

    from productix.kpi_tracking.services.alert_engine import _create_alert

    settings = frappe.get_cached_doc("KPI Settings")
    if not settings.enable_alerts:
        return

    for machine in machines:
        dept = frappe.db.get_value("Machine", machine.name, "department")
        if machine.last_reading_date:
            days_stale = date_diff(today(), machine.last_reading_date)
            if days_stale > 3:
                _create_alert(
                    kpi=None,
                    department=dept,
                    alert_type="Machine Data Stale",
                    severity="Warning",
                    message=f"Machine '{machine.machine_name}' has no readings for {days_stale} days.",
                    period=today(),
                    trigger_val=days_stale,
                    threshold_val=3,
                    settings=settings,
                    subject=f"Machine Data Stale: {machine.machine_name}"
                )

        if machine.health_status == "Critical":
            _create_alert(
                kpi=None,
                department=dept,
                alert_type="Machine Health Critical",
                severity="Critical",
                message=f"Machine '{machine.machine_name}' health is Critical (Score: {machine.health_score}/100).",
                period=today(),
                trigger_val=machine.health_score,
                threshold_val=50,
                settings=settings,
                subject=f"Machine Health Critical: {machine.machine_name}"
            )

        if machine.maintenance_frequency_days and machine.last_maintenance_date:
            days_since = date_diff(today(), machine.last_maintenance_date)
            if days_since >= machine.maintenance_frequency_days:
                _create_alert(
                    kpi=None,
                    department=dept,
                    alert_type="Machine Maintenance Overdue",
                    severity="Warning",
                    message=f"Machine '{machine.machine_name}' maintenance is overdue by {days_since - machine.maintenance_frequency_days} days.",
                    period=today(),
                    trigger_val=days_since,
                    threshold_val=machine.maintenance_frequency_days,
                    settings=settings,
                    subject=f"Maintenance Overdue: {machine.machine_name}"
                )


def get_fleet_health_summary(departments=None):
    res = get_company_machines_health(departments)
    summary = res.get("company_summary", {})
    return {
        "total_machines": summary.get("total_machines", 0),
        "avg_score": summary.get("avg_score", 0),
        "healthy_count": summary.get("healthy", 0),
        "good_count": summary.get("good", 0),
        "warning_count": summary.get("warning", 0),
        "critical_count": summary.get("critical", 0),
        "departments": res.get("departments", []),
    }


def predict_machine_failure(machine_name):
    summary = get_machine_health_summary(machine_name)
    return {
        "machine": machine_name,
        "prediction": summary.get("prediction"),
        "trend": summary.get("trend"),
    }
