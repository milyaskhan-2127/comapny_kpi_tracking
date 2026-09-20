import frappe
from frappe.utils import now_datetime
from frappe.utils.password import update_password


def _require_admin():
    from productix.kpi_tracking.api.dashboard import _check_kpi_access
    role = _check_kpi_access()
    if role != "KPI Admin":
        frappe.throw("Access denied: Administrator privileges required.", frappe.PermissionError)


@frappe.whitelist()
def get_users():
    _require_admin()

    assignments = frappe.db.get_all(
        "KPI User Assignment",
        fields=["name", "user", "department", "role", "is_active", "creation", "modified"],
        order_by="creation desc",
    )

    assigned_user_emails = {a.user for a in assignments}

    # Also find any users with KPI roles directly
    kpi_role_users = frappe.db.sql("""
        SELECT DISTINCT parent as user FROM `tabHas Role`
        WHERE role IN ('KPI Admin', 'KPI Employee', 'KPI Manager', 'KPI Contributor')
        AND parent NOT IN ('Administrator', 'Guest')
    """, as_dict=True)

    for ru in kpi_role_users:
        if ru.user not in assigned_user_emails:
            assigned_user_emails.add(ru.user)

    user_details = {}
    if assigned_user_emails:
        users = frappe.db.get_all(
            "User",
            filters={"name": ["in", list(assigned_user_emails)]},
            fields=["name", "full_name", "email", "enabled", "last_login", "user_image"],
        )
        for u in users:
            user_details[u.name] = u

    # Map department display names
    dept_map = {
        d.name: d.department_name
        for d in frappe.db.get_all("KPI Department", fields=["name", "department_name"])
    }

    result = []
    seen_users = set()

    for a in assignments:
        u_info = user_details.get(a.user, {})
        user_email = a.user
        if user_email in ("Administrator", "Guest"):
            continue

        seen_users.add(user_email)
        std_role = "Admin" if a.role in ("Admin", "KPI Admin") else "Employee"
        result.append({
            "assignment_id": a.name,
            "user": user_email,
            "full_name": u_info.get("full_name") or user_email,
            "email": u_info.get("email") or user_email,
            "role": std_role,
            "department": a.department or "",
            "department_name": dept_map.get(a.department, a.department or "All Departments"),
            "is_active": 1 if (a.is_active and u_info.get("enabled", 1)) else 0,
            "enabled": u_info.get("enabled", 1),
            "last_login": u_info.get("last_login"),
        })

    for u_email in assigned_user_emails:
        if u_email not in seen_users and u_email not in ("Administrator", "Guest"):
            u_info = user_details.get(u_email, {})
            roles = frappe.get_roles(u_email)
            is_adm = "KPI Admin" in roles or "System Manager" in roles
            std_role = "Admin" if is_adm else "Employee"
            result.append({
                "assignment_id": None,
                "user": u_email,
                "full_name": u_info.get("full_name") or u_email,
                "email": u_info.get("email") or u_email,
                "role": std_role,
                "department": "",
                "department_name": "All Departments" if is_adm else "Unassigned",
                "is_active": u_info.get("enabled", 1),
                "enabled": u_info.get("enabled", 1),
                "last_login": u_info.get("last_login"),
            })

    departments = frappe.db.get_all(
        "KPI Department",
        filters={"is_active": 1},
        fields=["name", "department_name", "department_code"],
        order_by="department_name asc",
    )

    return {
        "users": result,
        "departments": departments,
        "total_users": len(result),
    }


@frappe.whitelist()
def save_user(email, full_name, role, department=None, user_id=None, new_password=None, is_active=1):
    _require_admin()

    email = (email or "").strip().lower()
    full_name = (full_name or "").strip()

    if not email:
        frappe.throw("Email address is required")
    if not full_name:
        frappe.throw("Full name is required")

    is_admin = role in ("Admin", "KPI Admin")
    role_val = "KPI Admin" if is_admin else "KPI Contributor"

    if not is_admin:
        if not department:
            frappe.throw("Department assignment is required for Employee role")
        if not frappe.db.exists("KPI Department", {"name": department, "is_active": 1}):
            frappe.throw(f"Active department '{department}' was not found")

    is_active_int = 1 if int(is_active) else 0
    target_user = user_id or email

    if frappe.db.exists("User", target_user):
        user_doc = frappe.get_doc("User", target_user)
        user_doc.first_name = full_name
        user_doc.email = email
        user_doc.enabled = is_active_int
        user_doc.save(ignore_permissions=True)
    else:
        if not new_password:
            frappe.throw("Password is required when creating a new user")

        user_doc = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": full_name,
            "enabled": is_active_int,
            "send_welcome_email": 0,
            "user_type": "System User",
        })
        user_doc.insert(ignore_permissions=True)

    if new_password:
        update_password(user_doc.name, new_password)

    # Upsert KPI User Assignment
    existing_assignment = frappe.db.get_value(
        "KPI User Assignment",
        {"user": user_doc.name},
        "name"
    )

    if existing_assignment:
        assignment_doc = frappe.get_doc("KPI User Assignment", existing_assignment)
        assignment_doc.role = role_val
        assignment_doc.department = department if not is_admin else ""
        assignment_doc.is_active = is_active_int
        assignment_doc.save(ignore_permissions=True)
    else:
        assignment_doc = frappe.get_doc({
            "doctype": "KPI User Assignment",
            "user": user_doc.name,
            "role": role_val,
            "department": department if not is_admin else "",
            "is_active": is_active_int,
        })
        assignment_doc.insert(ignore_permissions=True)

    return {
        "status": "success",
        "user": user_doc.name,
        "full_name": user_doc.full_name,
        "role": "Admin" if is_admin else "Employee",
        "department": assignment_doc.department,
        "is_active": is_active_int,
    }


@frappe.whitelist()
def toggle_user_status(user, is_active):
    _require_admin()

    if user in ("Administrator", frappe.session.user):
        frappe.throw("Cannot modify your own administrator account")

    # If is_active is -1 or "delete", execute complete clean deletion
    if str(is_active) in ("-1", "delete"):
        return delete_kpi_user(user)

    is_active_int = 1 if int(is_active) else 0

    if frappe.db.exists("User", user):
        frappe.db.set_value("User", user, "enabled", is_active_int)

    assignments = frappe.db.get_all("KPI User Assignment", filters={"user": user}, pluck="name")
    for a_name in assignments:
        frappe.db.set_value("KPI User Assignment", a_name, "is_active", is_active_int)
        doc = frappe.get_doc("KPI User Assignment", a_name)
        doc._sync_user_roles()

    return {"status": "success", "user": user, "is_active": is_active_int}


@frappe.whitelist()
def delete_kpi_user(user_id):
    _require_admin()
    if user_id in ("Administrator", frappe.session.user):
        frappe.throw("Cannot delete your own administrator account")

    # 1. Clean up assignments, notifications, ownership references
    try:
        frappe.db.delete("KPI User Assignment", {"user": user_id})
        frappe.db.delete("Message Notification", {"recipient": user_id})
        frappe.db.delete("Notification Log", {"for_user": user_id})
        frappe.db.sql("UPDATE `tabKPI Definition` SET kpi_owner = '' WHERE kpi_owner = %s", (user_id,))
        frappe.db.sql("UPDATE `tabKPI Alert` SET resolved_by = '' WHERE resolved_by = %s", (user_id,))
        frappe.db.sql("DELETE FROM `tabHas Role` WHERE parent = %s", (user_id,))
    except Exception:
        pass

    # 2. Forcibly remove user from tabUser
    if frappe.db.exists("User", user_id):
        try:
            frappe.delete_doc("User", user_id, ignore_permissions=True, force=1)
        except Exception:
            try:
                frappe.db.sql("DELETE FROM `tabUser` WHERE name = %s", (user_id,))
            except Exception:
                pass

    frappe.db.commit()
    return {"status": "success", "user": user_id, "deleted": 1}


@frappe.whitelist()
def purge_all_non_admin_users():
    """Purge all users created for tracking testing except Administrator."""
    _require_admin()

    assignments = frappe.db.get_all(
        "KPI User Assignment",
        filters={"user": ["not in", ["Administrator", "Guest"]]},
        pluck="user"
    )

    deleted_users = []
    for u in assignments:
        try:
            delete_kpi_user(u)
            deleted_users.append(u)
        except Exception:
            pass

    return {"status": "success", "purged": deleted_users, "count": len(deleted_users)}
