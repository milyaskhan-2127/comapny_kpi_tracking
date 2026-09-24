import frappe
from frappe import _
from frappe.utils import flt, getdate, today
from productix_kpi.kpi_tracking.security.permissions import (
    is_kpi_admin,
    is_kpi_ceo,
    get_user_authorized_department,
)
from productix_kpi.kpi_tracking.api.dashboard import _check_kpi_access, _get_user_departments
from productix_kpi.kpi_tracking.services.period_engine import (
    calculate_normalized_score,
    get_status_from_score,
)


def get_authorized_departments_for_report(filters=None, user=None):
    """
    Enforces strict security for KPI reports.
    Reports are strictly visible and accessible to KPI Administrators and KPI CEOs (read-only).
    KPI Employees are blocked.
    """
    user = user or (getattr(frappe, "session", None) and getattr(frappe.session, "user", None)) or "Administrator"
    role = _check_kpi_access(user)

    if role not in ("KPI Admin", "KPI CEO") and not is_kpi_admin(user) and not is_kpi_ceo(user):
        frappe.throw(_("Access denied: KPI Reports are restricted to KPI Administrators and Executives."), frappe.PermissionError)

    user_depts = _get_user_departments(user)
    if not user_depts:
        frappe.throw(_("No active department found or assigned to your account."), frappe.PermissionError)

    requested_dept = filters.get("department") if filters else None
    if requested_dept in ("All", "ALL", "All Departments", "", None):
        requested_dept = None

    if requested_dept:
        if requested_dept not in user_depts and not is_kpi_admin(user):
            frappe.throw(_("You are not authorized to view reports for department '{0}'.").format(requested_dept), frappe.PermissionError)
        if not frappe.db.exists("KPI Department", requested_dept):
            frappe.throw(_("Department '{0}' does not exist.").format(requested_dept), frappe.DoesNotExistError)
        return [requested_dept], requested_dept
    else:
        return user_depts, None


def calculate_kpi_variance(actual, target, direction="Higher is Better"):
    """
    Calculate variance and variance percentage according to KPI direction.
    Uses actual vs target values without separate calculation deviations.
    """
    if actual is None or target is None:
        return 0.0, 0.0, "Missing Data"

    act = flt(actual)
    tgt = flt(target)
    direction = direction or "Higher is Better"

    variance = act - tgt
    variance_pct = (variance / abs(tgt) * 100.0) if tgt != 0 else 0.0

    if direction == "Lower is Better":
        # For lower is better, actual <= target is meeting/above target
        if act <= tgt:
            status = "Above Target" if act < tgt else "Meeting Target"
        else:
            status = "Below Target"
    elif direction == "Target Range" or direction == "Exact Target":
        if abs(variance) < 0.001:
            status = "Meeting Target"
        elif act < tgt:
            status = "Below Target"
        else:
            status = "Above Target"
    else:  # Higher is Better
        if act >= tgt:
            status = "Above Target" if act > tgt else "Meeting Target"
        else:
            status = "Below Target"

    return round(variance, 2), round(variance_pct, 2), status


def calculate_kpi_variance_and_score(actual, target, direction="Higher is Better", warning_threshold=80.0, critical_threshold=60.0, target_type="Fixed Target", minimum_acceptable=None):
    """
    Comprehensive variance, normalized score, and achievement status evaluator
    consistent with central Period Engine and calculation engine.
    """
    if actual is None or target is None:
        return {
            "variance": 0.0,
            "variance_pct": 0.0,
            "score": None,
            "status": "Missing Data",
        }

    act = flt(actual)
    tgt = flt(target)
    direction = direction or "Higher is Better"

    variance = act - tgt
    variance_pct = (variance / abs(tgt) * 100.0) if tgt != 0 else 0.0

    norm_score = calculate_normalized_score(
        actual=act,
        target=tgt,
        direction=direction,
        target_type=target_type,
        minimum_acceptable=minimum_acceptable,
    )

    if norm_score is not None:
        norm_score = max(0.0, min(100.0, flt(norm_score)))
        if norm_score >= 100.0 and act != tgt and direction in ("Higher is Better", "Lower is Better"):
            status = "Above Target"
        elif norm_score >= flt(warning_threshold or 80.0):
            status = "Meeting Target"
        else:
            status = "Below Target"
    else:
        status = "Missing Data"

    return {
        "variance": round(variance, 2),
        "variance_pct": round(variance_pct, 2),
        "score": round(norm_score, 1) if norm_score is not None else None,
        "status": status,
    }


def get_kpi_score_badge(score):
    """HTML badge for normalized 0-100 score."""
    if score is None:
        return '<span class="indicator-pill grey">N/A</span>'
    sc = flt(score)
    if sc >= 80.0:
        color = "green"
    elif sc >= 60.0:
        color = "orange"
    else:
        color = "red"
    return f'<span class="indicator-pill {color}">{sc:.1f}/100</span>'


def get_status_badge(status):
    """HTML badge for standard KPI statuses."""
    if not status:
        return '<span class="indicator-pill grey">Pending</span>'
    status_lower = status.lower()
    if any(k in status_lower for k in ["on track", "meeting", "above", "ready", "complete", "growth", "improving"]):
        color = "green"
    elif any(k in status_lower for k in ["warning", "needs review", "stable", "incomplete", "pending", "acknowledged"]):
        color = "orange"
    elif any(k in status_lower for k in ["critical", "below", "invalid", "decline", "missing"]):
        color = "red"
    else:
        color = "blue"
    return f'<span class="indicator-pill {color}">{status}</span>'
