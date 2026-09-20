import frappe


def boot_session(bootinfo):
    """Inject Productix subscription and notification status into boot session."""
    if frappe.session.user not in ("Guest",):
        try:
            from productix.api.subscription import get_subscription_status
            bootinfo["productix_subscription"] = get_subscription_status()
        except Exception:
            bootinfo["productix_subscription"] = {"valid": True}

        # Unread notification count
        try:
            unread = frappe.db.count("Message Notification", {
                "recipient": frappe.session.user,
                "is_read": 0,
            })
            bootinfo["productix_unread_notifications"] = unread
        except Exception:
            bootinfo["productix_unread_notifications"] = 0

