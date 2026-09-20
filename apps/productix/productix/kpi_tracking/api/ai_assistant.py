import frappe
import json
import os


def _require_admin():
    from productix.kpi_tracking.api.dashboard import _check_kpi_access
    role = _check_kpi_access()
    if role != "KPI Admin" and "System Manager" not in frappe.get_roles():
        frappe.throw("Access denied: AI Assistant is restricted to administrators only.", frappe.PermissionError)


@frappe.whitelist()
def ask_ai(specialist_type, question, department=None, business_unit=None,
           customer=None, from_date=None, to_date=None, kpi=None, history=None):
    _require_admin()

    if history and isinstance(history, str):
        try:
            history = json.loads(history)
        except Exception:
            history = []

    from productix.kpi_tracking.services.groq_ai import get_ai_response, build_context_data

    context = build_context_data(
        department=department, business_unit=business_unit,
        customer=customer, from_date=from_date, to_date=to_date, kpi=kpi,
    )

    filters = {
        "department": department, "business_unit": business_unit,
        "customer": customer, "from_date": from_date, "to_date": to_date,
    }

    return get_ai_response(specialist_type, question, context, filters, history=history)


@frappe.whitelist()
def get_suggestions(specialist_type, department=None):
    _require_admin()
    from productix.kpi_tracking.services.groq_ai import get_suggested_questions
    return get_suggested_questions(specialist_type, department)


@frappe.whitelist()
def send_ai_alert(department, message, severity="Warning"):
    _require_admin()
    from productix.kpi_tracking.services.alert_engine import dispatch_ai_department_alert
    return dispatch_ai_department_alert(department, message, severity=severity)


@frappe.whitelist()
def get_groq_status():
    _require_admin()
    settings = frappe.get_cached_doc("KPI Settings")
    has_key = False
    try:
        key = settings.get_password("groq_api_key", raise_exception=False)
        if key:
            has_key = True
    except Exception:
        has_key = False

    if not has_key:
        if frappe.conf.get("groq_api_key") or os.environ.get("GROQ_API_KEY"):
            has_key = True

    VALID_MODELS = [
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "qwen/qwen3.8-27b",
        "groq/compound",
        "groq/compound-mini",
    ]
    model = (settings.groq_model or "").strip()
    if not model or model not in VALID_MODELS:
        model = "openai/gpt-oss-120b"

    return {
        "has_key": has_key,
        "enabled": bool(settings.enable_ai_assistants),
        "model": model,
    }


@frappe.whitelist()
def save_groq_settings(api_key=None, model="openai/gpt-oss-120b", enabled=1):
    _require_admin()
    from frappe.utils.password import set_encrypted_password
    settings = frappe.get_doc("KPI Settings")
    if api_key and api_key.strip():
        set_encrypted_password("KPI Settings", "KPI Settings", api_key.strip(), "groq_api_key")
    if model:
        settings.groq_model = model.strip()
    settings.enable_ai_assistants = int(enabled)
    settings.save(ignore_permissions=True)
    frappe.db.commit()
    frappe.clear_cache()
    return {"status": "ok", "message": "Groq AI settings saved successfully."}


@frappe.whitelist()
def get_top_inefficiencies(department=None, limit=5):
    _require_admin()

    from productix.kpi_tracking.services.analytics import calculate_growth

    inefficiencies = []
    filters = {"is_active": 1}
    if department:
        filters["department"] = department

    kpis = frappe.db.get_all(
        "KPI Definition",
        filters=filters,
        fields=["name", "kpi_name", "department", "direction"],
    )

    for kpi in kpis:
        growth = calculate_growth(kpi.name, kpi.department)
        if growth.get("growth_percentage") is None:
            continue
        impact = growth["growth_percentage"]
        if kpi.direction == "Higher is Better" and impact < 0:
            inefficiencies.append({
                "kpi": kpi.kpi_name, "department": kpi.department,
                "impact": abs(impact), "direction": "declined", "details": growth,
            })
        elif kpi.direction == "Lower is Better" and impact > 0:
            inefficiencies.append({
                "kpi": kpi.kpi_name, "department": kpi.department,
                "impact": abs(impact), "direction": "increased", "details": growth,
            })

    inefficiencies.sort(key=lambda x: x["impact"], reverse=True)
    return inefficiencies[:int(limit)]
