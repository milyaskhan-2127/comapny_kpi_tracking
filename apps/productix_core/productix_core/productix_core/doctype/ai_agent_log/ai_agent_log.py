import frappe
from frappe.model.document import Document


class AIAgentLog(Document):
    """Shared Productix audit log — records scheduled scans, expiry alerts,
    low-stock alerts, webhook events and system actions."""
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