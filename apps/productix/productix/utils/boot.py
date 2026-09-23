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

        # Ensure KPI Tracking reports execute instantly as standard synchronous reports (prepared_report = 0)
        try:
            frappe.db.sql("""
                UPDATE `tabReport`
                SET prepared_report = 0, timeout = 0
                WHERE module = 'KPI Tracking' AND (prepared_report = 1 OR timeout != 0)
            """)
        except Exception:
            pass

        # Write-once: ensure the Backup & Restore Manager Page exists with the
        # standard roles. (Page metadata comes from the standard Page DocType;
        # this only fills gaps on first boot. No per-login UPDATE hacks.)
        try:
            page_name = "backups"
            if not frappe.db.exists("Page", page_name):
                p_doc = frappe.get_doc({
                    "doctype": "Page",
                    "name": page_name,
                    "page_name": page_name,
                    "title": "Enterprise Backup & Restore Manager",
                    "module": "KPI Tracking",
                    "standard": "Yes",
                    "system_page": 0,
                    "roles": [
                        {"role": "System Manager"},
                        {"role": "Administrator"},
                        {"role": "KPI Admin"},
                        {"role": "Factory Admin"},
                        {"role": "Productix Admin"},
                        {"role": "Desk User"},
                        {"role": "All"},
                    ]
                })
                p_doc.insert(ignore_permissions=True)
            else:
                # Make sure standard roles are attached to tabHas Role for this page
                for r_name in ["System Manager", "Administrator", "KPI Admin", "Factory Admin", "Productix Admin", "Desk User", "All"]:
                    if not frappe.db.exists("Has Role", {"parent": page_name, "role": r_name, "parenttype": "Page"}):
                        try:
                            hr = frappe.get_doc({
                                "doctype": "Has Role",
                                "parent": page_name,
                                "parentfield": "roles",
                                "parenttype": "Page",
                                "role": r_name
                            })
                            hr.insert(ignore_permissions=True)
                        except Exception:
                            pass
        except Exception:
            pass

