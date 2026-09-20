import frappe
from frappe.model.document import Document


class AIAgentLog(Document):
    pass


@frappe.whitelist()
def log_event(action_type, status, details="", items_affected="", emails_sent=0):
    """Helper to create an AI Agent Log entry."""
    doc = frappe.get_doc({
        "doctype": "AI Agent Log",
        "action_type": action_type,
        "status": status,
        "details": details,
        "items_affected": items_affected,
        "emails_sent": int(emails_sent),
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.name


@frappe.whitelist()
def trigger_manual_scan():
    """
    Manual trigger for the inventory scan from dashboard / UI.
    Runs the full inventory scan and returns summary.
    """
    from productix.alerts.tasks import run_daily_inventory_scan
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
