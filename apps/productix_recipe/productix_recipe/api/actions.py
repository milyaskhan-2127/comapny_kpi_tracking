import frappe


@frappe.whitelist()
def trigger_manual_scan():
    """
    Manual trigger for the inventory scan from dashboard / UI.
    Runs the full inventory scan and returns summary.
    """
    from productix_core.modules.entitlement import require_module

    require_module("recipe")
    from productix_recipe.tasks import run_daily_inventory_scan

    res = run_daily_inventory_scan()

    if res.get("error"):
        frappe.msgprint(f"Inventory scan encountered an error: {res['error']}", indicator="red")
    else:
        low = res.get("low_stock_count", 0)
        exp = res.get("expiring_count", 0)
        email_note = f" (Email: {res.get('note')})" if res.get("note") else ""
        frappe.msgprint(
            f"✅ Inventory scan completed. Found <b>{low}</b> low stock item(s) and <b>{exp}</b> expiring batch(es).{email_note}",
            indicator="green" if low == 0 and exp == 0 else "orange"
        )


@frappe.whitelist()
def get_actions():
    """
    Return available actions for the Recipe module.

    Used by Core's generic extension dispatcher to advertise capabilities.
    """
    return {
        "trigger_manual_scan": "Run a manual inventory scan (low-stock + expiring batches)",
    }