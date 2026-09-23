import frappe
from frappe.utils import getdate, add_days, add_months, today, flt
import datetime
import calendar
import math
import re


def get_current_period(frequency="Daily", d=None):
    """
    Returns the canonical period string for the given frequency and date.
    - Daily: YYYY-MM-DD (e.g. '2026-09-21')
    - Weekly: YYYY-Www (e.g. '2026-W38')
    - Monthly: YYYY-MM (e.g. '2026-09')
    - Quarterly: YYYY-Qq (e.g. '2026-Q3')
    - Yearly: YYYY (e.g. '2026')
    """
    d = getdate(d) if d else getdate(today())
    freq = (frequency or "Daily").capitalize()

    if freq == "Daily":
        return d.strftime("%Y-%m-%d")
    elif freq == "Weekly":
        iso = d.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    elif freq == "Monthly":
        return d.strftime("%Y-%m")
    elif freq == "Quarterly":
        q = (d.month - 1) // 3 + 1
        return f"{d.year}-Q{q}"
    elif freq == "Yearly":
        return str(d.year)
    else:
        return d.strftime("%Y-%m-%d")


def get_period_dates(frequency, period_str):
    """
    Returns (start_date, end_date) as datetime.date objects for any valid period string.
    """
    if not period_str:
        d = getdate(today())
        return d, d

    period_str = str(period_str).strip()
    freq = (frequency or "").capitalize()

    try:
        # Match by regex pattern first
        if re.match(r"^\d{4}-\d{2}-\d{2}$", period_str):
            d = getdate(period_str)
            return d, d

        elif re.match(r"^\d{4}-W\d{2}$", period_str) or "-W" in period_str:
            parts = period_str.replace("W", "").split("-")
            year = int(parts[0])
            week = int(parts[1])
            start_date = datetime.date.fromisocalendar(year, week, 1)
            end_date = datetime.date.fromisocalendar(year, week, 7)
            return start_date, end_date

        elif re.match(r"^\d{4}-\d{2}$", period_str):
            parts = period_str.split("-")
            year = int(parts[0])
            month = int(parts[1])
            _, last_day = calendar.monthrange(year, month)
            return datetime.date(year, month, 1), datetime.date(year, month, last_day)

        elif re.match(r"^\d{4}-Q\d$", period_str) or "-Q" in period_str:
            parts = period_str.replace("Q", "").split("-")
            year = int(parts[0])
            quarter = int(parts[1])
            start_month = (quarter - 1) * 3 + 1
            end_month = quarter * 3
            _, last_day = calendar.monthrange(year, end_month)
            return datetime.date(year, start_month, 1), datetime.date(year, end_month, last_day)

        elif re.match(r"^\d{4}$", period_str):
            year = int(period_str)
            return datetime.date(year, 1, 1), datetime.date(year, 12, 31)

        # Fall back to frequency if string didn't match patterns
        if freq == "Daily":
            d = getdate(period_str)
            return d, d
        elif freq == "Weekly":
            d = getdate(period_str)
            iso = d.isocalendar()
            start_date = datetime.date.fromisocalendar(iso[0], iso[1], 1)
            end_date = datetime.date.fromisocalendar(iso[0], iso[1], 7)
            return start_date, end_date
        elif freq == "Monthly":
            d = getdate(period_str)
            _, last_day = calendar.monthrange(d.year, d.month)
            return datetime.date(d.year, d.month, 1), datetime.date(d.year, d.month, last_day)
        elif freq == "Quarterly":
            d = getdate(period_str)
            quarter = (d.month - 1) // 3 + 1
            start_month = (quarter - 1) * 3 + 1
            end_month = quarter * 3
            _, last_day = calendar.monthrange(d.year, end_month)
            return datetime.date(d.year, start_month, 1), datetime.date(d.year, end_month, last_day)
        elif freq == "Yearly":
            d = getdate(period_str)
            return datetime.date(d.year, 1, 1), datetime.date(d.year, 12, 31)

    except Exception:
        pass

    d = getdate(today())
    return d, d


# Backward compatible alias
get_period_date_range = get_period_dates


def resolve_canonical_period(frequency, reference_period=None, reference_date=None):
    """
    Resolves the canonical period string for a specific frequency given an optional
    reference period (which may be in a different frequency format) or reference date.
    Eliminates cross-frequency mismatch where a monthly period filter breaks daily/weekly KPIs.
    """
    freq = (frequency or "Daily").capitalize()
    today_date = getdate(reference_date) if reference_date else getdate(today())

    if not reference_period:
        return get_current_period(freq, today_date)

    ref_str = str(reference_period).strip()

    # If reference_period already matches the target frequency format:
    if freq == "Daily" and re.match(r"^\d{4}-\d{2}-\d{2}$", ref_str):
        return ref_str
    if freq == "Weekly" and (re.match(r"^\d{4}-W\d{2}$", ref_str) or "-W" in ref_str):
        return ref_str
    if freq == "Monthly" and re.match(r"^\d{4}-\d{2}$", ref_str):
        return ref_str
    if freq == "Quarterly" and (re.match(r"^\d{4}-Q\d$", ref_str) or "-Q" in ref_str):
        return ref_str
    if freq == "Yearly" and re.match(r"^\d{4}$", ref_str):
        return ref_str

    # Otherwise, extract date range of reference_period
    start_date, end_date = get_period_dates(None, ref_str)

    if start_date <= today_date <= end_date:
        rep_date = today_date
    elif today_date > end_date:
        rep_date = end_date
    else:
        rep_date = start_date

    return get_current_period(freq, rep_date)


def get_previous_period(frequency, period_str):
    """
    Returns the preceding period string chronologically for any frequency.
    """
    if not period_str:
        return get_current_period(frequency)

    freq = (frequency or "Daily").capitalize()
    start_date, _ = get_period_dates(freq, period_str)

    if freq == "Daily":
        prev_date = add_days(start_date, -1)
        return get_current_period("Daily", prev_date)
    elif freq == "Weekly":
        prev_date = add_days(start_date, -7)
        return get_current_period("Weekly", prev_date)
    elif freq == "Monthly":
        prev_date = add_months(start_date, -1)
        return get_current_period("Monthly", prev_date)
    elif freq == "Quarterly":
        prev_date = add_months(start_date, -3)
        return get_current_period("Quarterly", prev_date)
    elif freq == "Yearly":
        prev_date = add_months(start_date, -12)
        return get_current_period("Yearly", prev_date)
    else:
        return get_current_period(freq, add_days(start_date, -1))


def get_next_period(frequency, period_str):
    """
    Returns the subsequent period string chronologically for any frequency.
    """
    if not period_str:
        return get_current_period(frequency)

    freq = (frequency or "Daily").capitalize()
    _, end_date = get_period_dates(freq, period_str)

    if freq == "Daily":
        next_date = add_days(end_date, 1)
        return get_current_period("Daily", next_date)
    elif freq == "Weekly":
        next_date = add_days(end_date, 1)
        return get_current_period("Weekly", next_date)
    elif freq == "Monthly":
        next_date = add_days(end_date, 1)
        return get_current_period("Monthly", next_date)
    elif freq == "Quarterly":
        next_date = add_days(end_date, 1)
        return get_current_period("Quarterly", next_date)
    elif freq == "Yearly":
        next_date = add_days(end_date, 1)
        return get_current_period("Yearly", next_date)
    else:
        return get_current_period(freq, add_days(end_date, 1))


def get_past_periods(frequency="Daily", count=6, end_date=None):
    """
    Returns a list of N period strings ending at end_date in chronological order (oldest to newest).
    """
    d = getdate(end_date) if end_date else getdate(today())
    current = get_current_period(frequency, d)
    periods = [current]

    for _ in range(count - 1):
        prev = get_previous_period(frequency, periods[0])
        periods.insert(0, prev)

    return periods


def calculate_raw_achievement_percentage(actual, target, direction="Higher is Better",
                                         target_type="Fixed Target", minimum_acceptable=None):
    """
    Calculates the unclamped raw achievement percentage (e.g. 105.8% when exceeding target).
    Reflects genuine business performance variance without artificial 100% clamping.
    """
    if target_type == "No Target":
        return 100.0

    try:
        act = flt(actual) if actual is not None else None
        tgt = flt(target) if target is not None else 0.0
    except (ValueError, TypeError):
        return 0.0

    if act is None:
        return 0.0

    direction = direction or "Higher is Better"

    if direction == "Lower is Better":
        if act <= 0 and tgt <= 0:
            return 100.0
        elif tgt <= 0:
            return round(max(0.0, 100.0 - (act * 25.0)), 2)
        elif act <= 0:
            return round((tgt / 0.0001) * 100.0, 2)
        else:
            return round((tgt / act) * 100.0, 2)

    elif direction == "Target Range":
        min_val = flt(minimum_acceptable if minimum_acceptable is not None else 0.0)
        max_val = flt(tgt if tgt != 0 else min_val)
        if min_val <= act <= max_val:
            return 100.0
        elif act < min_val:
            return round((act / min_val * 100.0) if min_val != 0 else 0.0, 2)
        else:
            return round((max_val / act * 100.0) if act != 0 else 0.0, 2)

    elif direction == "Exact Target":
        if tgt == 0:
            return 100.0 if act == 0 else 0.0
        variance = abs(act - tgt)
        variance_pct = (variance / abs(tgt)) * 100.0
        return round(100.0 - variance_pct, 2)

    else:  # Higher is Better
        if tgt <= 0:
            return 100.0 if act >= 0 else 0.0
        return round((act / tgt) * 100.0, 2)


def calculate_normalized_score(actual, target, direction="Higher is Better",
                               target_type="Fixed Target", minimum_acceptable=None):
    """
    One Central Calculation for KPI Normalized Achievement Score:
    Strictly clamped to [0.0, 100.0].
    Handles Higher is Better, Lower is Better, Target Range, Exact Target, No Target.
    """
    if target_type == "No Target":
        return 100.0

    try:
        act = flt(actual) if actual is not None else None
        tgt = flt(target) if target is not None else 0.0
    except (ValueError, TypeError):
        return 0.0

    if act is None:
        return None

    direction = direction or "Higher is Better"

    if direction == "Lower is Better":
        if act <= 0:
            return 100.0
        elif tgt <= 0:
            # Target is zero (e.g. 0 accidents). Each unit over 0 reduces score by 25 points
            return round(max(0.0, min(100.0, 100.0 - (act * 25.0))), 2)
        else:
            if act <= tgt:
                return 100.0
            else:
                return round(max(0.0, min(100.0, (tgt / act) * 100.0)), 2)

    elif direction == "Target Range":
        min_val = flt(minimum_acceptable if minimum_acceptable is not None else 0.0)
        max_val = flt(tgt if tgt != 0 else min_val)
        if min_val <= act <= max_val:
            return 100.0
        elif act < min_val:
            return round(max(0.0, min(100.0, (act / min_val * 100.0) if min_val != 0 else 0.0)), 2)
        else:
            return round(max(0.0, min(100.0, (max_val / act * 100.0) if act != 0 else 0.0)), 2)

    elif direction == "Exact Target":
        if tgt == 0:
            return 100.0 if act == 0 else 0.0
        else:
            variance = abs(act - tgt)
            variance_pct = (variance / abs(tgt)) * 100.0
            return round(max(0.0, min(100.0, 100.0 - variance_pct)), 2)

    else:  # Higher is Better
        if tgt <= 0:
            return 100.0 if act >= 0 else 0.0
        else:
            return round(max(0.0, min(100.0, (act / tgt) * 100.0)), 2)


def get_status_from_score(score, warning_threshold=80.0, critical_threshold=60.0):
    """
    Authoritative Status determination from normalized score.
    On Track >= warning_threshold
    Warning >= critical_threshold
    Critical < critical_threshold
    """
    if score is None:
        return "Pending / No Data"

    sc = flt(score)
    warn = flt(warning_threshold if warning_threshold is not None else 80.0)
    crit = flt(critical_threshold if critical_threshold is not None else 60.0)

    if sc >= warn:
        return "On Track"
    elif sc >= crit:
        return "Warning"
    else:
        return "Critical"


def get_submission_monitoring(frequency=None, period=None, department=None, departments=None):
    """
    ONE SOURCE OF TRUTH for KPI Submissions & Missing Monitoring.
    Used identically across:
    - Data Entry Page
    - Department Dashboard
    - Company Overview
    - Action Center
    - Alert Engine
    - Data Quality & Completeness Report
    - AI Assistant
    """
    d = getdate(today())
    dept_filters = {"is_active": 1}
    if departments:
        dept_filters["name"] = ["in", list(departments)]
    elif department and department not in ("All", "ALL", "All Departments", "", None):
        dept_filters["name"] = department

    departments = frappe.db.get_all(
        "KPI Department",
        filters=dept_filters,
        fields=["name", "department_name", "department_code", "weight"],
        order_by="department_name asc",
    )

    overview = []
    total_required = 0
    total_completed = 0
    total_missing = 0

    for dept in departments:
        kpi_filters = {"department": dept.name, "is_active": 1}
        if frequency and frequency != "All":
            kpi_filters["frequency"] = frequency

        dept_kpis = frappe.db.get_all(
            "KPI Definition",
            filters=kpi_filters,
            fields=["name", "kpi_name", "frequency", "target_value", "unit"]
        )
        required_count = len(dept_kpis)
        if required_count == 0:
            continue

        completed_count = 0
        last_entry_info = None
        missing_kpis = []
        completed_kpis = []

        for k in dept_kpis:
            freq = k.frequency or "Monthly"
            target_period = resolve_canonical_period(freq, period, d)
            entry = frappe.db.get_value(
                "KPI Data Entry",
                {"kpi": k.name, "department": dept.name, "period": target_period, "docstatus": 1},
                ["name", "actual_value", "achievement_percentage", "status", "entry_date", "entered_by", "creation"],
                as_dict=True,
                order_by="creation desc"
            )
            if entry:
                completed_count += 1
                completed_kpis.append({
                    "kpi_code": k.name,
                    "kpi_name": k.kpi_name,
                    "actual_value": entry.actual_value,
                    "achievement": entry.achievement_percentage,
                    "status": entry.status,
                    "period": target_period,
                    "entered_by": entry.entered_by,
                })
                if not last_entry_info or (entry.creation and str(entry.creation) > str(last_entry_info.get("creation", ""))):
                    last_entry_info = entry
            else:
                missing_kpis.append({
                    "kpi_code": k.name,
                    "kpi_name": k.kpi_name,
                    "frequency": freq,
                    "period": target_period,
                    "target_value": k.target_value,
                    "unit": k.unit or "",
                })

        missing_count = max(0, required_count - completed_count)
        completion_pct = round((completed_count / required_count * 100.0), 1) if required_count > 0 else 0.0

        last_entry_date = last_entry_info.entry_date if last_entry_info else None
        last_entered_by = last_entry_info.entered_by if last_entry_info else None
        last_entered_by_name = None
        if last_entered_by:
            last_entered_by_name = frappe.db.get_value("User", last_entered_by, "full_name") or last_entered_by

        # Find active employees assigned to this department
        employees = frappe.db.get_all(
            "KPI User Assignment",
            filters={"department": dept.name, "is_active": 1},
            fields=["user"],
        )
        employee_emails = [emp.user for emp in employees]
        employee_names = []
        if employee_emails:
            for u in frappe.db.get_all("User", filters={"name": ["in", employee_emails]}, fields=["name", "full_name"]):
                employee_names.append(u.full_name or u.name)

        total_required += required_count
        total_completed += completed_count
        total_missing += missing_count

        dept_target_period = resolve_canonical_period(frequency if (frequency and frequency != "All") else "Monthly", period, d)

        overview.append({
            "department": dept.department_name or dept.name,
            "department_code": dept.name,
            "required_entries": required_count,
            "completed_entries": completed_count,
            "missing_entries": missing_count,
            "completion_percentage": completion_pct,
            "last_entry_date": last_entry_date,
            "last_entered_by": last_entered_by_name or ("None" if required_count > 0 and completed_count == 0 else "--"),
            "assigned_employees": employee_names,
            "assigned_count": len(employee_names),
            "period": dept_target_period,
            "frequency": frequency or "All",
            "is_complete": missing_count == 0 and required_count > 0,
            "missing_kpis": missing_kpis,
            "completed_kpis": completed_kpis,
        })

    overall_pct = round((total_completed / total_required * 100.0), 1) if total_required > 0 else 0.0

    return {
        "departments": overview,
        "summary": {
            "total_departments": len(overview),
            "total_required": total_required,
            "total_completed": total_completed,
            "total_missing": total_missing,
            "overall_completion_percentage": overall_pct,
            "period": resolve_canonical_period(frequency if (frequency and frequency != "All") else "Monthly", period, d),
            "frequency": frequency or "All",
        }
    }
