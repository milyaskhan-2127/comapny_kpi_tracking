import frappe
from frappe import _


@frappe.whitelist()
def get_machines(department=None, machine_type=None, status=None, limit=50, offset=0):
    from productix.kpi_tracking.security.permissions import (
        is_kpi_admin,
        is_kpi_ceo,
        get_ceo_authorized_departments,
        get_user_authorized_department,
        get_ceo_access,
    )

    filters = {"is_active": 1}
    if department:
        _check_machine_access(department)
        filters["department"] = department
    else:
        if is_kpi_admin():
            pass
        elif is_kpi_ceo():
            ceo = get_ceo_access()
            if not ceo or not ceo.can_view_machines:
                frappe.throw(_("You do not have permission to view machines"), frappe.PermissionError)
            depts = get_ceo_authorized_departments()
            filters["department"] = ["in", depts] if depts else ["in", ["__none__"]]
        else:
            user_dept = get_user_authorized_department()
            if not user_dept:
                return {"machines": [], "total": 0}
            filters["department"] = user_dept

    if machine_type:
        filters["machine_type"] = machine_type
    if status:
        filters["operating_status"] = status

    machines = frappe.db.get_all(
        "Machine",
        filters=filters,
        fields=[
            "name", "machine_name", "machine_code", "machine_type",
            "department", "operating_status", "health_score", "health_status",
            "last_reading_date", "location", "manufacturer", "model_name",
        ],
        order_by="machine_name asc",
        limit_page_length=int(limit),
        limit_start=int(offset),
    )

    total = frappe.db.count("Machine", filters=filters)

    return {"machines": machines, "total": total}


@frappe.whitelist()
def get_machine_detail(machine_name):
    _check_machine_access_by_machine(machine_name)

    from productix.kpi_tracking.services.machine_health import get_machine_health_summary
    detail = get_machine_health_summary(machine_name) or {}

    machine = frappe.get_cached_doc("Machine", machine_name)

    # 1. Machine type parameters (for data-entry form + detail panel)
    if machine.machine_type:
        mt = frappe.get_cached_doc("Machine Type", machine.machine_type)
        detail["parameters"] = [p.as_dict() for p in mt.parameters]
        detail["machine_type_name"] = mt.type_name or mt.name
    else:
        detail["parameters"] = []

    # 2. Linked KPIs (resolved with names + latest performance)
    linked_kpis = []
    for link in (machine.linked_kpis or []):
        kpi_name = link.kpi
        kpi_doc_name = frappe.db.get_value("KPI Definition", kpi_name, "kpi_name") if kpi_name else None
        linked_kpis.append({
            "kpi": kpi_name,
            "kpi_name": link.kpi_name or kpi_doc_name or kpi_name,
        })
    detail["linked_kpis"] = linked_kpis

    # 3. Recent machine alerts
    detail["alerts"] = get_machine_alerts_internal(machine_name, limit=8)

    # 4. Access context
    from productix.kpi_tracking.security.permissions import is_kpi_admin
    detail["can_write"] = bool(is_kpi_admin())

    return detail


@frappe.whitelist()
def get_machine_alerts(machine, limit=10):
    _check_machine_access_by_machine(machine)
    return {"alerts": get_machine_alerts_internal(machine, limit=int(limit))}


def get_machine_alerts_internal(machine, limit=10):
    """Alerts referencing this machine (machine field or message text)."""
    dept = frappe.db.get_value("Machine", machine, "department")
    alerts = frappe.db.get_all(
        "KPI Alert",
        filters={"status": ["in", ["Active", "Acknowledged"]]},
        fields=["name", "alert_type", "severity", "subject", "message", "trigger_period", "creation", "status"],
        order_by="creation desc",
        limit_page_length=int(limit),
    )
    filtered = []
    for a in alerts:
        msg = (a.message or "") + " " + (a.subject or "")
        if machine in msg or (a.get("machine") and a.machine == machine):
            filtered.append(a)
            continue
        # fall back: alerts in the same department mentioning machine by name/code
        m_name = frappe.db.get_value("Machine", machine, "machine_name")
        if m_name and m_name in msg:
            filtered.append(a)
        elif dept and a.alert_type in ("Machine Health Critical", "Machine Data Stale", "Machine Maintenance Overdue") and a.get("department") == dept:
            filtered.append(a)
    return filtered[:int(limit)]


@frappe.whitelist()
def add_machine_kpi(machine, kpi):
    """Link an existing KPI Definition to a machine (admin only)."""
    from productix.kpi_tracking.security.permissions import is_kpi_admin
    if not is_kpi_admin():
        frappe.throw(_("Only KPI Admin can manage machine KPIs"), frappe.PermissionError)

    if not frappe.db.exists("Machine", machine):
        frappe.throw(_("Machine not found"), frappe.DoesNotExistError)
    if not frappe.db.exists("KPI Definition", kpi):
        frappe.throw(_("KPI Definition not found"), frappe.DoesNotExistError)

    doc = frappe.get_doc("Machine", machine)
    existing = [lk.kpi for lk in (doc.linked_kpis or [])]
    if kpi in existing:
        frappe.throw(_("This KPI is already linked to the machine"))

    doc.append("linked_kpis", {
        "kpi": kpi,
        "kpi_name": frappe.db.get_value("KPI Definition", kpi, "kpi_name"),
    })
    doc.save(ignore_permissions=True)

    return {
        "success": True,
        "message": _("KPI linked to machine"),
        "linked_kpis": [lk.as_dict() for lk in doc.linked_kpis],
    }


@frappe.whitelist()
def remove_machine_kpi(machine, kpi):
    """Unlink a KPI from a machine (admin only)."""
    from productix.kpi_tracking.security.permissions import is_kpi_admin
    if not is_kpi_admin():
        frappe.throw(_("Only KPI Admin can manage machine KPIs"), frappe.PermissionError)

    doc = frappe.get_doc("Machine", machine)
    remaining = [lk for lk in (doc.linked_kpis or []) if lk.kpi != kpi]
    doc.linked_kpis = remaining
    doc.save(ignore_permissions=True)

    return {
        "success": True,
        "message": _("KPI unlinked from machine"),
        "linked_kpis": [lk.as_dict() for lk in doc.linked_kpis],
    }


@frappe.whitelist()
def create_machine(machine_name, machine_code, machine_type, department,
                   operating_status="Operational", location=None, manufacturer=None,
                   model_name=None, serial_number=None, installation_date=None,
                   description=None, maintenance_frequency_days=90, is_active=1):
    """Create a new Machine record (admin only)."""
    from productix.kpi_tracking.security.permissions import is_kpi_admin
    if not is_kpi_admin():
        frappe.throw(_("Only KPI Admin can create machines"), frappe.PermissionError)

    if not machine_name or not machine_code:
        frappe.throw(_("Machine Name and Machine Code are required"))
    if not frappe.db.exists("Machine Type", machine_type):
        frappe.throw(_("Machine Type not found"), frappe.DoesNotExistError)
    if not frappe.db.exists("KPI Department", department):
        frappe.throw(_("Department not found"), frappe.DoesNotExistError)
    if frappe.db.exists("Machine", {"machine_code": machine_code}):
        frappe.throw(_("A machine with code '%s' already exists") % machine_code)

    doc = frappe.get_doc({
        "doctype": "Machine",
        "machine_name": machine_name,
        "machine_code": machine_code,
        "machine_type": machine_type,
        "department": department,
        "operating_status": operating_status,
        "location": location,
        "manufacturer": manufacturer,
        "model_name": model_name,
        "serial_number": serial_number,
        "installation_date": installation_date,
        "description": description,
        "maintenance_frequency_days": int(maintenance_frequency_days or 90),
        "is_active": 1 if int(is_active) else 0,
    })
    doc.insert(ignore_permissions=True)

    return {
        "success": True,
        "message": _("Machine '%s' created") % machine_name,
        "machine": doc.name,
    }


@frappe.whitelist()
def get_machine_types():
    return frappe.db.get_all(
        "Machine Type",
        filters={"is_active": 1},
        fields=["name", "type_name", "type_code"],
        order_by="type_name asc",
    )


@frappe.whitelist()
def get_machine_type_parameters(machine_type):
    doc = frappe.get_cached_doc("Machine Type", machine_type)
    return [p.as_dict() for p in doc.parameters]


@frappe.whitelist()
def submit_machine_reading(machine, reading_date, readings, notes=None):
    _check_machine_access_by_machine(machine)

    import json as json_mod
    if isinstance(readings, str):
        readings = json_mod.loads(readings)

    doc = frappe.new_doc("Machine Reading")
    doc.machine = machine
    doc.reading_date = reading_date

    for r in readings:
        doc.append("readings", {
            "parameter_code": r.get("parameter_code"),
            "parameter_name": r.get("parameter_name", ""),
            "parameter_category": r.get("parameter_category", ""),
            "value": r.get("value"),
            "unit": r.get("unit", ""),
        })

    if notes:
        doc.notes = notes

    doc.insert()
    doc.submit()

    return {"name": doc.name, "health_score": doc.health_score, "health_status": doc.health_status}


@frappe.whitelist()
def get_machine_readings(machine, limit=30, offset=0):
    _check_machine_access_by_machine(machine)

    readings = frappe.db.get_all(
        "Machine Reading",
        filters={"machine": machine, "docstatus": 1},
        fields=["name", "reading_date", "period", "health_score", "health_status",
                "data_quality", "entered_by", "notes"],
        order_by="reading_date desc",
        limit_page_length=int(limit),
        limit_start=int(offset),
    )

    total = frappe.db.count("Machine Reading", {"machine": machine, "docstatus": 1})
    return {"readings": readings, "total": total}


@frappe.whitelist()
def get_reading_detail(reading_name):
    doc = frappe.get_doc("Machine Reading", reading_name)
    _check_machine_access_by_machine(doc.machine)
    return doc.as_dict()


@frappe.whitelist()
def get_department_machines_overview(department):
    _check_machine_access(department)

    from productix.kpi_tracking.services.machine_health import get_department_machines_health
    return get_department_machines_health(department)


@frappe.whitelist()
def get_company_machines_overview():
    from productix.kpi_tracking.security.permissions import is_kpi_admin, is_kpi_ceo, get_ceo_access
    if is_kpi_admin():
        pass
    elif is_kpi_ceo():
        ceo = get_ceo_access()
        if not ceo or not ceo.can_view_machines or not ceo.can_view_company_overview:
            frappe.throw(_("You do not have permission to view company-wide machine health"), frappe.PermissionError)
    else:
        frappe.throw(_("Only KPI Admin or authorized CEO can view company-wide machine health"), frappe.PermissionError)

    from productix.kpi_tracking.services.machine_health import get_company_machines_health
    return get_company_machines_health()


@frappe.whitelist()
def update_machine_maintenance(machine, maintenance_date=None):
    from productix.kpi_tracking.security.permissions import is_kpi_admin
    if not is_kpi_admin():
        frappe.throw(_("Only KPI Admin can update maintenance records"), frappe.PermissionError)

    from frappe.utils import today as frappe_today
    doc = frappe.get_doc("Machine", machine)
    doc.last_maintenance_date = maintenance_date or frappe_today()
    doc.operating_status = "Operational"
    doc.save()

    return {"success": True, "last_maintenance_date": doc.last_maintenance_date}


def _check_machine_access(department=None):
    from productix.kpi_tracking.security.permissions import (
        is_kpi_admin,
        is_kpi_ceo,
        get_ceo_access,
        get_ceo_authorized_departments,
        get_user_authorized_department,
    )

    if is_kpi_admin():
        return

    if is_kpi_ceo():
        ceo = get_ceo_access()
        if not ceo or not ceo.can_view_machines:
            frappe.throw(_("You do not have permission to view Machine Health"), frappe.PermissionError)
        authorized_depts = get_ceo_authorized_departments()
        if department and department not in authorized_depts:
            frappe.throw(_("You do not have access to machines in this department"), frappe.PermissionError)
        return

    user_dept = get_user_authorized_department()
    if not user_dept:
        frappe.throw(_("You do not have access to any department"), frappe.PermissionError)
    if department and department != user_dept:
        frappe.throw(_("You do not have access to this department"), frappe.PermissionError)


def _check_machine_access_by_machine(machine_name):
    dept = frappe.db.get_value("Machine", machine_name, "department")
    if not dept:
        frappe.throw(_("Machine not found"), frappe.DoesNotExistError)
    _check_machine_access(dept)
