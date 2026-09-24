"""
Tenant and subscription utilities for Productix.
"""
import frappe
from frappe.utils import getdate, today, add_days


def set_user_tenant(doc, method=None):
    """
    After inserting a new User — dynamic tenant assignment, direct password hashing, and role summary update.
    """
    new_pwd = doc.get("new_password") or getattr(doc, "new_password", None)
    if new_pwd:
        try:
            from frappe.utils.password import update_password
            update_password(doc.name, new_pwd)
        except Exception as e:
            frappe.logger().warning(f"Could not auto-set password for {doc.name}: {e}")
    update_user_role_summary(doc)


def handle_user_save(doc, method=None):
    """
    Ensure user creation, password setting, and list view role summary work smoothly.
    """
    new_pwd = doc.get("new_password") or getattr(doc, "new_password", None)
    if new_pwd:
        try:
            from frappe.utils.password import update_password
            update_password(doc.name, new_pwd)
        except Exception as e:
            frappe.logger().warning(f"Could not auto-set password for {doc.name}: {e}")
    update_user_role_summary(doc)


def update_user_role_summary(doc, method=None):
    """
    Dynamically compute user's assigned role summary so it is displayed in the User List View column.
    """
    try:
        roles = [r.role for r in doc.get("roles", []) if getattr(r, "role", None) not in ("All", "Guest", "Desk User")]
        if not roles and doc.name:
            roles = frappe.get_roles(doc.name)
            roles = [r for r in roles if r not in ("All", "Guest", "Desk User")]

        primary_order = [
            "Factory Admin",
            "Assistant System Administrator",
            "Production Manager",
            "Store Keeper",
            "Purchase Manager",
            "General Staff",
            "System Manager",
            "Administrator",
            "Stock Manager",
            "Stock User",
            "Item Manager",
            "Manufacturing Manager",
            "Manufacturing User",
            "Purchase User",
        ]

        assigned = [p for p in primary_order if p in roles]
        other_roles = [r for r in roles if r not in assigned]
        all_ordered = assigned + other_roles

        role_str = ", ".join(all_ordered[:2]) if all_ordered else "General Staff"
        if len(all_ordered) > 2:
            role_str += f" (+{len(all_ordered)-2})"

        doc.custom_user_role = role_str
        if doc.name and not doc.is_new():
            frappe.db.set_value("User", doc.name, "custom_user_role", role_str, update_modified=False)
    except Exception as e:
        frappe.logger().warning(f"Error computing custom_user_role for {doc.name}: {e}")



def _safe_cleanup(label, fn):
    """Run a cleanup statement, warning instead of raising when the target
    table does not exist (module not installed) or when the statement fails."""
    try:
        fn()
    except Exception as e:
        frappe.logger().warning(f"User cleanup '{label}' failed for "
                                f"{getattr(frappe.local, 'form_dict', {}).get('name', '?')}: {e}")


def handle_user_trash(doc, method=None):
    """
    Before a User is deleted:
    Clean up linked assignments, notifications, and ownership references so the user
    can be deleted without any foreign-key / link errors, while preserving historical
    audit logs and data entry records.

    Each cleanup targets a doctype that may belong to a non-installed module, so
    every statement is guarded individually and never aborts the deletion.
    """
    user = doc.name

    def del_kpi_assignments():
        frappe.db.delete("KPI User Assignment", {"user": user})

    def del_message_notifications():
        frappe.db.delete("Message Notification", {"recipient": user})

    def del_notification_logs():
        frappe.db.delete("Notification Log", {"for_user": user})

    def unset_notification_sender():
        frappe.db.sql("""
            UPDATE `tabNotification Log`
            SET from_user = ''
            WHERE from_user = %s
        """, (user,))

    def unset_instruction_sender():
        frappe.db.sql("""
            UPDATE `tabInstruction Message`
            SET sender = 'Administrator'
            WHERE sender = %s
        """, (user,))

    def unset_kpi_owner():
        frappe.db.sql("""
            UPDATE `tabKPI Definition`
            SET kpi_owner = ''
            WHERE kpi_owner = %s
        """, (user,))

    def unset_kpi_resolver():
        frappe.db.sql("""
            UPDATE `tabKPI Alert`
            SET resolved_by = ''
            WHERE resolved_by = %s
        """, (user,))

    _safe_cleanup("KPI User Assignment", del_kpi_assignments)
    _safe_cleanup("Message Notification", del_message_notifications)
    _safe_cleanup("Notification Log", del_notification_logs)
    _safe_cleanup("Notification Log sender", unset_notification_sender)
    _safe_cleanup("Instruction Message sender", unset_instruction_sender)
    _safe_cleanup("KPI Definition owner", unset_kpi_owner)
    _safe_cleanup("KPI Alert resolver", unset_kpi_resolver)




def check_license_on_login(login_manager=None):
    """
    Called on user login to notify of license status.
    """
    if not login_manager:
        return

    user = frappe.session.user if frappe.session else None
    if not user or user in ("Administrator", "Guest"):
        return

    lic = get_active_license()
    if lic and lic.valid_until:
        days_left = (getdate(lic.valid_until) - getdate(today())).days
        if 0 <= days_left <= 7:
            frappe.msgprint(
                f"⚠️ Your Productix license expires in {days_left} day(s) on {lic.valid_until}. "
                f"Please renew to avoid interruption.",
                indicator="orange",
                alert=True,
            )


def get_active_license():
    """Return the active, non-expired Productix License record."""
    licenses = frappe.get_all(
        "Productix License",
        filters={"is_active": 1},
        fields=["name", "valid_until", "max_users", "tenant_name"],
        order_by="valid_until desc",
        limit=1,
    )
    return licenses[0] if licenses else None


def is_license_valid():
    """Check if the active license is valid."""
    lic = get_active_license()
    if not lic:
        return False
    if not lic.valid_until:
        return True
    return getdate(lic.valid_until) >= getdate(today())


def get_user_count_limit():
    """Return max_users from the active license."""
    lic = get_active_license()
    return lic.max_users if lic else 100
