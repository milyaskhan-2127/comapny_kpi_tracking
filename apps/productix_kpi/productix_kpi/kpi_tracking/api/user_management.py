import frappe
from frappe.utils import now_datetime
from frappe.utils.password import update_password


def _require_admin():
    from productix_kpi.kpi_tracking.api.dashboard import _check_kpi_access
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

    # Also find any users with KPI roles directly (incl. KPI CEO)
    kpi_role_users = frappe.db.sql("""
        SELECT DISTINCT parent as user FROM `tabHas Role`
        WHERE role IN ('KPI Admin', 'KPI Employee', 'KPI Manager', 'KPI Contributor', 'KPI CEO')
        AND parent NOT IN ('Administrator', 'Guest')
    """, as_dict=True)

    for ru in kpi_role_users:
        if ru.user not in assigned_user_emails:
            assigned_user_emails.add(ru.user)

    # CEO Access records
    ceo_records = frappe.db.get_all(
        "KPI CEO Access",
        fields=["name", "user", "is_active", "access_scope",
                "can_view_company_overview", "can_view_machines"],
        order_by="creation desc",
    )
    for ceo in ceo_records:
        if ceo.user not in assigned_user_emails:
            assigned_user_emails.add(ceo.user)

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
    dept_map = {}
    for d in frappe.db.get_all("KPI Department", fields=["name", "department_name", "department_code", "location"]):
        label = d.department_name or d.name
        if d.get("location"):
            label += f" — {d.location}"
        code = d.get("department_code") or d.name
        if code and code != label:
            label += f" [{code}]"
        dept_map[d.name] = label

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
            "ceo_access_id": None,
            "user": user_email,
            "full_name": u_info.get("full_name") or user_email,
            "email": u_info.get("email") or user_email,
            "role": std_role,
            "department": a.department or "",
            "department_name": dept_map.get(a.department, a.department or "All Departments"),
            "is_active": 1 if (a.is_active and u_info.get("enabled", 1)) else 0,
            "enabled": u_info.get("enabled", 1),
            "last_login": u_info.get("last_login"),
            "ceo_config": None,
        })

    for u_email in assigned_user_emails:
        if u_email not in seen_users and u_email not in ("Administrator", "Guest"):
            u_info = user_details.get(u_email, {})
            roles = frappe.get_roles(u_email)
            is_adm = "KPI Admin" in roles or "System Manager" in roles
            std_role = "Admin" if is_adm else "Employee"
            result.append({
                "assignment_id": None,
                "ceo_access_id": None,
                "user": u_email,
                "full_name": u_info.get("full_name") or u_email,
                "email": u_info.get("email") or u_email,
                "role": std_role,
                "department": "",
                "department_name": "All Departments" if is_adm else "Unassigned",
                "is_active": u_info.get("enabled", 1),
                "enabled": u_info.get("enabled", 1),
                "last_login": u_info.get("last_login"),
                "ceo_config": None,
            })

    # Merge CEO Access records (authoritative for CEOs — replaces any stale row)
    for ceo in ceo_records:
        if ceo.user in ("Administrator", "Guest"):
            continue
        u_info = user_details.get(ceo.user, {})
        enabled = u_info.get("enabled", 1) if u_info else frappe.db.get_value("User", ceo.user, "enabled")
        try:
            ceo_doc = frappe.get_doc("KPI CEO Access", ceo.name)
            ceo_depts = [{"department": row.department, "access_level": row.access_level} for row in ceo_doc.department_access]
            ceo_kpis = [{"department": row.department, "kpi": row.kpi} for row in ceo_doc.kpi_access]
        except Exception:
            ceo_depts = []
            ceo_kpis = []
        result = [r for r in result if r["user"] != ceo.user]
        result.append({
            "assignment_id": None,
            "ceo_access_id": ceo.name,
            "user": ceo.user,
            "full_name": u_info.get("full_name") or ceo.user,
            "email": u_info.get("email") or ceo.user,
            "role": "CEO",
            "department": "",
            "department_name": "All Departments" if ceo.access_scope == "All Departments" else "Selected Departments",
            "is_active": 1 if (ceo.is_active and enabled) else 0,
            "enabled": enabled,
            "last_login": u_info.get("last_login"),
            "ceo_config": {
                "access_scope": ceo.access_scope,
                "can_view_company_overview": ceo.can_view_company_overview,
                "can_view_machines": ceo.can_view_machines,
                "is_active": ceo.is_active,
                "departments": ceo_depts,
                "kpis": ceo_kpis,
            },
        })

    departments = frappe.db.get_all(
        "KPI Department",
        filters={"is_active": 1},
        fields=["name", "department_name", "department_code", "location"],
        order_by="department_name asc",
    )
    for d in departments:
        label = d.department_name or d.name
        if d.get("location"):
            label += f" — {d.location}"
        code = d.get("department_code") or d.name
        if code and code != label:
            label += f" [{code}]"
        d["display_name"] = label

    return {
        "users": result,
        "departments": departments,
        "total_users": len(result),
    }


@frappe.whitelist()
def get_departments_with_kpis():
    """Active departments with their active KPIs — for the CEO configuration UI."""
    _require_admin()
    return {"departments": _departments_with_kpis_internal()}


def _departments_with_kpis_internal():
    departments = frappe.db.get_all(
        "KPI Department",
        filters={"is_active": 1},
        fields=["name", "department_name", "department_code", "location"],
        order_by="department_name asc",
    )
    for d in departments:
        label = d.department_name or d.name
        if d.get("location"):
            label += f" — {d.location}"
        code = d.get("department_code") or d.name
        if code and code != label:
            label += f" [{code}]"
        d["display_name"] = label

    kpis = frappe.db.get_all(
        "KPI Definition",
        filters={"is_active": 1},
        fields=["name", "kpi_name", "kpi_code", "department"],
        order_by="kpi_name asc",
    )
    kpis_by_dept = {}
    for k in kpis:
        kpis_by_dept.setdefault(k.department, []).append(k)

    for d in departments:
        d["kpis"] = kpis_by_dept.get(d.name, [])

    return departments


@frappe.whitelist()
def get_user_kpi_context(user):
    """
    Light-weight per-user KPI role context for the native User form:
    current role, assignment, CEO config and departments+KPIs in one call.
    """
    _require_admin()
    if not user:
        frappe.throw("User is required")

    roles = frappe.get_roles(user)

    assignment = frappe.db.get_value(
        "KPI User Assignment", {"user": user},
        ["name", "role", "department", "is_active"], as_dict=True
    )
    ceo = frappe.db.get_value(
        "KPI CEO Access", {"user": user},
        ["name", "is_active", "access_scope", "can_view_company_overview", "can_view_machines"],
        as_dict=True
    )

    ceo_depts = []
    ceo_kpis = []
    if ceo:
        ceo_depts = [
            {"department": r.department, "access_level": r.access_level}
            for r in frappe.get_all(
                "KPI CEO Department Access",
                filters={"parent": ceo.name, "parenttype": "KPI CEO Access"},
                fields=["department", "access_level"],
            )
        ]
        ceo_kpis = [
            {"department": r.department, "kpi": r.kpi}
            for r in frappe.get_all(
                "KPI CEO KPI Access",
                filters={"parent": ceo.name, "parenttype": "KPI CEO Access"},
                fields=["department", "kpi"],
            )
        ]

    if "KPI CEO" in roles and ceo:
        current_role = "CEO"
    elif "KPI Admin" in roles or "System Manager" in roles:
        current_role = "Administrator"
    else:
        current_role = "Employee"

    return {
        "user": user,
        "current_role": current_role,
        "department": assignment.department if assignment else "",
        "is_active": assignment.is_active if assignment else 1,
        "departments": _departments_with_kpis_internal(),
        "ceo_config": {
            "access_scope": ceo.access_scope if ceo else "All Departments",
            "can_view_company_overview": ceo.can_view_company_overview if ceo else 1,
            "can_view_machines": ceo.can_view_machines if ceo else 1,
            "is_active": ceo.is_active if ceo else 1,
            "departments": ceo_depts,
            "kpis": ceo_kpis,
        } if ceo else None,
    }


@frappe.whitelist()
def save_user(email, full_name, role, department=None, user_id=None, new_password=None, is_active=1, ceo_access=None):
    _require_admin()

    email = (email or "").strip().lower()
    full_name = (full_name or "").strip()

    if not email:
        frappe.throw("Email address is required")
    if not full_name:
        frappe.throw("Full name is required")

    is_admin = role in ("Admin", "KPI Admin")
    is_ceo = role in ("CEO", "KPI CEO")

    if not is_admin and not is_ceo:
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

    # ---- CEO flow: build KPI CEO Access + KPI CEO role, no employee assignment
    if is_ceo:
        _upsert_ceo_access(user_doc, ceo_access, is_active_int)

        # Normalize roles: CEO gets KPI CEO + Desk User; never admin/employee KPI roles
        user_doc = frappe.get_doc("User", user_doc.name)
        kpi_strip = {"KPI Admin", "KPI Employee", "KPI Manager", "KPI Contributor", "System Manager"}
        user_doc.roles = [r for r in user_doc.roles if r.role not in kpi_strip]
        current_roles = [r.role for r in user_doc.roles]
        if "KPI CEO" not in current_roles:
            user_doc.append("roles", {"role": "KPI CEO"})
        if "Desk User" not in current_roles:
            user_doc.append("roles", {"role": "Desk User"})
        user_doc.save(ignore_permissions=True)

        # Remove any stale employee assignment (CEOs are not employees)
        frappe.db.delete("KPI User Assignment", {"user": user_doc.name})

        return {
            "status": "success",
            "user": user_doc.name,
            "full_name": user_doc.full_name,
            "role": "CEO",
            "department": "",
            "is_active": is_active_int,
        }

    # ---- Admin / Employee flow
    role_val = "KPI Admin" if is_admin else "KPI Contributor"

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

    # If a CEO record exists for this user, remove the CEO role + config
    _clear_ceo_role(user_doc.name)

    return {
        "status": "success",
        "user": user_doc.name,
        "full_name": user_doc.full_name,
        "role": "Admin" if is_admin else "Employee",
        "department": assignment_doc.department,
        "is_active": is_active_int,
    }


def _upsert_ceo_access(user_doc, ceo_access, is_active_int):
    """Create or update the KPI CEO Access record + role configuration."""
    import json as json_mod

    config = {}
    if isinstance(ceo_access, str):
        try:
            config = json_mod.loads(ceo_access) or {}
        except Exception:
            config = {}
    elif isinstance(ceo_access, dict):
        config = ceo_access

    access_scope = config.get("access_scope") or "All Departments"
    if access_scope not in ("All Departments", "Selected Departments Only"):
        access_scope = "All Departments"

    dept_rows = config.get("departments") or []
    kpi_rows = config.get("kpis") or []

    existing = frappe.db.get_value("KPI CEO Access", {"user": user_doc.name}, "name")
    if existing:
        doc = frappe.get_doc("KPI CEO Access", existing)
    else:
        doc = frappe.new_doc("KPI CEO Access")
        doc.user = user_doc.name

    doc.is_active = is_active_int
    doc.access_scope = access_scope
    doc.can_view_company_overview = 1 if config.get("can_view_company_overview", True) else 0
    doc.can_view_machines = 1 if config.get("can_view_machines", True) else 0

    # Rebuild department access rows
    doc.department_access = []
    if access_scope == "Selected Departments Only":
        for r in dept_rows:
            dept = (r.get("department") if isinstance(r, dict) else r)
            if not dept or not frappe.db.exists("KPI Department", dept):
                continue
            doc.append("department_access", {
                "department": dept,
                "access_level": (r.get("access_level") if isinstance(r, dict) else "View All KPIs") or "View All KPIs",
            })

    # Rebuild KPI access rows
    doc.kpi_access = []
    for r in kpi_rows:
        if not isinstance(r, dict):
            continue
        dept = r.get("department")
        kpi = r.get("kpi")
        if not dept or not kpi:
            continue
        if not frappe.db.exists("KPI Department", dept) or not frappe.db.exists("KPI Definition", kpi):
            continue
        doc.append("kpi_access", {
            "department": dept,
            "kpi": kpi,
        })

    doc.save(ignore_permissions=True)
    return doc


def _clear_ceo_role(user):
    """Remove KPI CEO role and deactivate the CEO Access record for a user."""
    try:
        if frappe.db.exists("User", user):
            u = frappe.get_doc("User", user)
            u.roles = [r for r in u.roles if r.role != "KPI CEO"]
            u.save(ignore_permissions=True)
    except Exception:
        pass
    try:
        names = frappe.db.get_all("KPI CEO Access", filters={"user": user}, pluck="name")
        for n in names:
            if names and n:
                ceo_doc = frappe.get_doc("KPI CEO Access", n)
                ceo_doc.is_active = 0
                ceo_doc.save(ignore_permissions=True)
    except Exception:
        pass


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

    # CEO access records follow the same enable/disable state
    ceo_access_records = frappe.db.get_all("KPI CEO Access", filters={"user": user}, pluck="name")
    for ca_name in ceo_access_records:
        frappe.db.set_value("KPI CEO Access", ca_name, "is_active", is_active_int)

    return {"status": "success", "user": user, "is_active": is_active_int}


@frappe.whitelist()
def delete_kpi_user(user_id):
    _require_admin()
    if user_id in ("Administrator", frappe.session.user):
        frappe.throw("Cannot delete your own administrator account")

    # 1. Clean up assignments, notifications, ownership references
    try:
        frappe.db.delete("KPI User Assignment", {"user": user_id})
        frappe.db.delete("KPI CEO Access", {"user": user_id})
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
