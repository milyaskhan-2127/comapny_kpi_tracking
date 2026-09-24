"""
Productix Core boot session — platform portion.

Injects subscription/license status, unread notification count (tolerant when
the Instruction module is not installed) and the enabled productix module keys
into the boot payload. Frappe runs every app's ``boot_session`` hook, so the
recipe/kpi/instruction apps may add their own.
"""
import frappe


def boot_session(bootinfo):
    """Inject Productix platform data into boot session."""
    if frappe.session.user in ("Guest",):
        return

    # Module entitlement map — consumed by per-app frontend code to hide
    # UI for disabled modules (server-side enforcement happens in
    # productix_core.modules.entitlement.gate_request).
    try:
        from productix_core.modules.entitlement import get_enabled_module_keys

        bootinfo["productix_modules"] = get_enabled_module_keys()
    except Exception:
        bootinfo["productix_modules"] = []

    # Subscription / license status
    try:
        from productix_core.api.subscription import get_subscription_status

        bootinfo["productix_subscription"] = get_subscription_status()
    except Exception:
        bootinfo["productix_subscription"] = {"valid": True}

    # Unread in-app notifications (Instruction module — tolerate its absence)
    try:
        if frappe.db.table_exists("Message Notification"):
            unread = frappe.db.count("Message Notification", {
                "recipient": frappe.session.user,
                "is_read": 0,
            })
        else:
            unread = 0
    except Exception:
        unread = 0
    bootinfo["productix_unread_notifications"] = unread