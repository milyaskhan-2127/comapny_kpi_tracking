import frappe
from frappe import _


def is_kpi_admin(user=None):
    if not user:
        user = frappe.session.user

    if user == "Administrator":
        return True

    roles = frappe.get_roles(user)
    if "System Manager" in roles or "KPI Admin" in roles:
        return True

    return False


def get_user_authorized_department(user=None):
    if not user:
        user = frappe.session.user

    if not user or user == "Guest":
        return None

    assigned_dept = frappe.db.get_value(
        "KPI User Assignment",
        {"user": user, "is_active": 1},
        "department"
    )
    if assigned_dept:
        return assigned_dept

    employee = frappe.db.get_value(
        "Employee",
        {"user_id": user, "status": "Active"},
        ["name", "department"],
        as_dict=True
    )
    if employee and employee.department:
        if frappe.db.exists("KPI Department", employee.department):
            return employee.department

        dept_by_name = frappe.db.get_value(
            "KPI Department",
            {"department_name": employee.department},
            "name"
        )
        if dept_by_name:
            return dept_by_name

        matching = frappe.db.sql(
            """
            SELECT name FROM `tabKPI Department`
            WHERE LOWER(TRIM(name)) = LOWER(TRIM(%s))
               OR LOWER(TRIM(department_name)) = LOWER(TRIM(%s))
            LIMIT 1
            """,
            (employee.department, employee.department),
            as_dict=True
        )
        if matching:
            return matching[0].name

    return None


def get_kpi_alert_query_conditions(user=None):
    if is_kpi_admin(user):
        return None

    user_dept = get_user_authorized_department(user)
    if not user_dept:
        return "1=0"

    dept_escaped = frappe.db.escape(user_dept)
    return f"(`tabKPI Alert`.department IS NULL OR `tabKPI Alert`.department = '' OR `tabKPI Alert`.department = {dept_escaped})"


def get_kpi_data_entry_query_conditions(user=None):
    if is_kpi_admin(user):
        return None

    user_dept = get_user_authorized_department(user)
    if not user_dept:
        return "1=0"

    dept_escaped = frappe.db.escape(user_dept)
    return f"`tabKPI Data Entry`.department = {dept_escaped}"


def get_kpi_definition_query_conditions(user=None):
    if is_kpi_admin(user):
        return None
    return "1=0"


def get_kpi_prediction_query_conditions(user=None):
    if is_kpi_admin(user):
        return None
    return "1=0"


def get_kpi_admin_doctype_query_conditions(user=None):
    if is_kpi_admin(user):
        return None
    return "1=0"


def kpi_has_permission(doc, ptype="read", user=None):
    if not user:
        user = frappe.session.user

    if is_kpi_admin(user):
        return True

    doctype = doc.doctype if hasattr(doc, "doctype") else str(doc)
    user_dept = get_user_authorized_department(user)

    if doctype not in ("KPI Data Entry", "KPI Alert"):
        return False

    if not user_dept:
        return False

    if doctype == "KPI Alert":
        if ptype in ("delete", "create"):
            return False
        if hasattr(doc, "department"):
            alert_dept = doc.department
            if alert_dept and alert_dept != user_dept:
                return False
        return True

    if doctype == "KPI Data Entry":
        if ptype == "delete":
            return False
        if hasattr(doc, "department"):
            entry_dept = doc.department
            if entry_dept and entry_dept != user_dept:
                return False
        return True

    return False
