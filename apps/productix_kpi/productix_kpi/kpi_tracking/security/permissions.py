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


def is_kpi_ceo(user=None):
    if not user:
        user = frappe.session.user

    if user == "Administrator":
        return False

    roles = frappe.get_roles(user)
    if "KPI CEO" in roles:
        return True

    return bool(frappe.db.exists("KPI CEO Access", {"user": user, "is_active": 1}))


def get_ceo_access(user=None):
    if not user:
        user = frappe.session.user

    from productix_kpi.kpi_tracking.services.registry import get_ceo_config_for_user
    return get_ceo_config_for_user(user)


def get_ceo_authorized_departments(user=None):
    ceo = get_ceo_access(user)
    if not ceo or ceo.access_scope == "All Departments":
        return [d.name for d in frappe.db.get_all(
            "KPI Department", filters={"is_active": 1}, fields=["name"]
        )]

    return [d.department for d in ceo.department_access]


def get_ceo_authorized_kpis(user=None, department=None):
    ceo = get_ceo_access(user)
    if not ceo or ceo.access_scope == "All Departments":
        return None

    dept_map = {d.department: d.access_level for d in ceo.department_access}

    if department:
        level = dept_map.get(department)
        if not level:
            return []
        if level in ("View All KPIs", "View Summary Only"):
            return None
        return [k.kpi for k in ceo.kpi_access if k.department == department]

    result = []
    for dept, level in dept_map.items():
        if level == "View Specific KPIs":
            result.extend([k.kpi for k in ceo.kpi_access if k.department == dept])
    return result if result else None


def get_user_role(user=None):
    if is_kpi_admin(user):
        return "KPI Admin"
    if is_kpi_ceo(user):
        return "KPI CEO"
    return "KPI Employee"


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


def _get_user_departments_for_query(user=None):
    if is_kpi_admin(user):
        return None

    if is_kpi_ceo(user):
        ceo = get_ceo_access(user)
        if not ceo or ceo.access_scope == "All Departments":
            return None
        return get_ceo_authorized_departments(user)

    dept = get_user_authorized_department(user)
    return [dept] if dept else []


def get_kpi_alert_query_conditions(user=None):
    if is_kpi_admin(user):
        return None

    depts = _get_user_departments_for_query(user)
    if depts is None:
        return None
    if not depts:
        return "1=0"

    if len(depts) == 1:
        d = frappe.db.escape(depts[0])
        return f"(`tabKPI Alert`.department IS NULL OR `tabKPI Alert`.department = '' OR `tabKPI Alert`.department = {d})"

    escaped = ", ".join(frappe.db.escape(d) for d in depts)
    return f"(`tabKPI Alert`.department IS NULL OR `tabKPI Alert`.department = '' OR `tabKPI Alert`.department IN ({escaped}))"


def get_kpi_data_entry_query_conditions(user=None):
    if is_kpi_admin(user):
        return None

    depts = _get_user_departments_for_query(user)
    if depts is None:
        return None
    if not depts:
        return "1=0"

    if len(depts) == 1:
        return f"`tabKPI Data Entry`.department = {frappe.db.escape(depts[0])}"

    escaped = ", ".join(frappe.db.escape(d) for d in depts)
    return f"`tabKPI Data Entry`.department IN ({escaped})"


def get_kpi_definition_query_conditions(user=None):
    if is_kpi_admin(user):
        return None

    depts = _get_user_departments_for_query(user)
    if depts is None:
        return None
    if not depts:
        return "1=0"

    if len(depts) == 1:
        return f"(`tabKPI Definition`.department = {frappe.db.escape(depts[0])} AND `tabKPI Definition`.is_active = 1)"

    escaped = ", ".join(frappe.db.escape(d) for d in depts)
    return f"(`tabKPI Definition`.department IN ({escaped}) AND `tabKPI Definition`.is_active = 1)"


def get_kpi_prediction_query_conditions(user=None):
    if is_kpi_admin(user):
        return None

    depts = _get_user_departments_for_query(user)
    if depts is None:
        return None
    if not depts:
        return "1=0"

    if len(depts) == 1:
        return f"`tabKPI Prediction`.department = {frappe.db.escape(depts[0])}"

    escaped = ", ".join(frappe.db.escape(d) for d in depts)
    return f"`tabKPI Prediction`.department IN ({escaped})"


def get_kpi_department_query_conditions(user=None):
    if is_kpi_admin(user):
        return None

    depts = _get_user_departments_for_query(user)
    if depts is None:
        return None
    if not depts:
        return "1=0"

    if len(depts) == 1:
        return f"`tabKPI Department`.name = {frappe.db.escape(depts[0])}"

    escaped = ", ".join(frappe.db.escape(d) for d in depts)
    return f"`tabKPI Department`.name IN ({escaped})"


def get_kpi_machine_type_query_conditions(user=None):
    if is_kpi_admin(user):
        return None
    return "`tabMachine Type`.is_active = 1"


def get_kpi_admin_doctype_query_conditions(user=None):
    if is_kpi_admin(user):
        return None
    return "1=0"


def get_machine_query_conditions(user=None):
    if is_kpi_admin(user):
        return None

    depts = _get_user_departments_for_query(user)
    if depts is None:
        return None
    if not depts:
        return "1=0"

    if len(depts) == 1:
        return f"`tabMachine`.department = {frappe.db.escape(depts[0])}"

    escaped = ", ".join(frappe.db.escape(d) for d in depts)
    return f"`tabMachine`.department IN ({escaped})"


def get_machine_reading_query_conditions(user=None):
    if is_kpi_admin(user):
        return None

    depts = _get_user_departments_for_query(user)
    if depts is None:
        return None
    if not depts:
        return "1=0"

    if len(depts) == 1:
        return f"`tabMachine Reading`.machine IN (SELECT name FROM `tabMachine` WHERE department = {frappe.db.escape(depts[0])})"

    escaped = ", ".join(frappe.db.escape(d) for d in depts)
    return f"`tabMachine Reading`.machine IN (SELECT name FROM `tabMachine` WHERE department IN ({escaped}))"


def kpi_has_permission(doc, ptype="read", user=None):
    if not user:
        user = frappe.session.user

    if is_kpi_admin(user):
        return True

    doctype = doc.doctype if hasattr(doc, "doctype") else str(doc)

    ceo_allowed = (
        "KPI Data Entry", "KPI Alert", "KPI Definition", "KPI Prediction",
        "Machine", "Machine Reading", "Machine Health Log", "Machine Type",
        "KPI Department",
    )
    employee_allowed = (
        "KPI Data Entry", "KPI Alert", "KPI Definition", "KPI Prediction",
        "Machine", "Machine Reading", "Machine Health Log", "Machine Type",
        "KPI Department",
    )

    if is_kpi_ceo(user):
        if doctype not in ceo_allowed:
            return False
        if ptype in ("create", "write", "delete"):
            return False
        return _check_ceo_department_access(doc, doctype, user)

    if doctype not in employee_allowed:
        return False

    user_dept = get_user_authorized_department(user)
    if not user_dept:
        return False

    return _check_employee_permission(doc, doctype, ptype, user_dept)


def _check_ceo_department_access(doc, doctype, user):
    if doctype == "Machine Type":
        return True
    if doctype == "KPI Department":
        ceo_depts = get_ceo_authorized_departments(user)
        dept_name = doc.name if hasattr(doc, "name") else str(doc)
        return bool(ceo_depts and dept_name in ceo_depts)

    ceo_depts = get_ceo_authorized_departments(user)
    if not ceo_depts:
        return False

    dept = _get_doc_department(doc, doctype)
    if dept and dept not in ceo_depts:
        return False

    return True


def _get_doc_department(doc, doctype):
    if doctype in ("Machine", "Machine Reading", "Machine Health Log"):
        if doctype == "Machine" and hasattr(doc, "department"):
            return doc.department
        machine_field = "machine" if hasattr(doc, "machine") else None
        if machine_field and getattr(doc, machine_field, None):
            return frappe.db.get_value("Machine", doc.machine, "department")
        return None

    if hasattr(doc, "department"):
        return doc.department
    return None


def _check_employee_permission(doc, doctype, ptype, user_dept):
    if doctype == "KPI Department":
        if ptype in ("create", "write", "delete"):
            return False
        dept_name = doc.name if hasattr(doc, "name") else str(doc)
        return dept_name == user_dept

    if doctype == "Machine Type":
        if ptype in ("create", "write", "delete"):
            return False
        return True

    if doctype == "KPI Definition":
        if ptype in ("create", "write", "delete"):
            return False
        if hasattr(doc, "department") and doc.department and doc.department != user_dept:
            return False
        return True

    if doctype == "KPI Prediction":
        if ptype in ("create", "write", "delete"):
            return False
        if hasattr(doc, "department") and doc.department and doc.department != user_dept:
            return False
        return True

    if doctype == "KPI Alert":
        if ptype == "delete":
            return False
        if hasattr(doc, "department"):
            if doc.department and doc.department != user_dept:
                return False
        return True

    if doctype == "KPI Data Entry":
        if ptype == "delete":
            return False
        if hasattr(doc, "department"):
            if doc.department and doc.department != user_dept:
                return False
        return True

    if doctype == "Machine":
        if ptype in ("create", "write", "delete"):
            return False
        if hasattr(doc, "department") and doc.department and doc.department != user_dept:
            return False
        return True

    if doctype == "Machine Reading":
        if ptype == "delete":
            return False
        if hasattr(doc, "machine") and doc.machine:
            machine_dept = frappe.db.get_value("Machine", doc.machine, "department")
            if machine_dept and machine_dept != user_dept:
                return False
        return True

    if doctype == "Machine Health Log":
        if ptype in ("create", "write", "delete"):
            return False
        if hasattr(doc, "machine") and doc.machine:
            machine_dept = frappe.db.get_value("Machine", doc.machine, "department")
            if machine_dept and machine_dept != user_dept:
                return False
        return True

    return False
