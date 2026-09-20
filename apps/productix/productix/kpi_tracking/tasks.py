import frappe


def run_scheduled_predictions():
    """Hourly job: generate predictions for KPIs that have prediction enabled."""
    settings = frappe.get_cached_doc("KPI Settings")
    if not settings.enable_predictions:
        return

    from productix.kpi_tracking.services.analytics import generate_prediction

    kpis = frappe.db.get_all(
        "KPI Definition",
        filters={"is_active": 1, "prediction_enabled": 1},
        fields=["name", "department"],
    )
    for kpi in kpis:
        try:
            generate_prediction(kpi.name, kpi.department)
        except Exception:
            frappe.log_error(f"Prediction failed for KPI {kpi.name}")
