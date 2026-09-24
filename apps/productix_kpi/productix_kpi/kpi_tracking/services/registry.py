"""
Productix KPI Tracking — Authoritative Master Registry.

Single source of truth for KPI Departments, KPI Definitions, Machines and
Machine Types. Every consumer (dashboard APIs, analytics, alert engine,
machine health, CEO access) reads from this registry instead of maintaining
hardcoded lists or ad-hoc queries.

The registry is cached in Redis and invalidated through doc_events wired in
hooks.py whenever the underlying master records change, so newly created
departments / KPIs / machines appear everywhere WITHOUT a restart and without
stale-cache drift.
"""
import frappe


REGISTRY_CACHE_KEY = "productix:kpi:registry:v1"
DEPARTMENT_FIELDS = ["name", "department_name", "department_code", "is_active", "weight", "location"]
KPI_FIELDS = ["name", "kpi_name", "kpi_code", "department", "is_active",
              "frequency", "direction", "target_value", "measurement_type"]
MACHINE_FIELDS = ["name", "machine_name", "machine_code", "machine_type",
                  "department", "operating_status", "health_score", "health_status", "is_active"]
MACHINE_TYPE_FIELDS = ["name", "type_name", "type_code", "is_active"]


def _build_registry():
    departments = frappe.db.get_all("KPI Department", fields=DEPARTMENT_FIELDS,
                                    order_by="department_name asc")
    kpis = frappe.db.get_all("KPI Definition", fields=KPI_FIELDS, order_by="kpi_name asc")
    machines = frappe.db.get_all("Machine", fields=MACHINE_FIELDS, order_by="machine_name asc")
    machine_types = frappe.db.get_all("Machine Type", fields=MACHINE_TYPE_FIELDS,
                                      order_by="type_name asc")
    return {
        "departments": departments,
        "kpis": kpis,
        "machines": machines,
        "machine_types": machine_types,
    }


def _get_registry():
    data = frappe.cache().get_value(REGISTRY_CACHE_KEY)
    if not data:
        data = _build_registry()
        frappe.cache().set_value(REGISTRY_CACHE_KEY, data)
    return data


def invalidate(*doctypes):
    """Drop the registry cache. Wired to doc_events for KPI master doctypes."""
    try:
        frappe.cache().delete_value(REGISTRY_CACHE_KEY)
    except Exception:
        pass


def invalidate_cache(doc, method):
    """doc_events-compatible wrapper: invalidate(doc, method).

    Also clears the per-DocType document cache so callers relying on
    ``frappe.get_cached_doc`` (permissions, machine health) never observe a
    stale master record after a save/rename/trash.
    """
    invalidate()
    try:
        if doc and doc.doctype and doc.name:
            frappe.clear_document_cache(doc.doctype, doc.name)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Departments
# ---------------------------------------------------------------------------
def get_departments(active_only=True, refresh=False):
    if refresh:
        invalidate()
    depts = _get_registry()["departments"]
    if active_only:
        depts = [d for d in depts if d.get("is_active")]
    return depts


def get_active_department_names():
    return [d["name"] for d in get_departments(active_only=True)]


def get_department_map(active_only=True):
    """Map department name -> department record (incl. display labels)."""
    result = {}
    for d in get_departments(active_only=active_only):
        label = d.department_name or d.name
        if d.get("location"):
            label += f" — {d.location}"
        code = d.get("department_code") or d.name
        if code and code != label:
            label += f" [{code}]"
        result[d["name"]] = {**d, "display_name": label}
    return result


# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------
def get_kpis(active_only=True, refresh=False):
    if refresh:
        invalidate()
    kpis = _get_registry()["kpis"]
    if active_only:
        kpis = [k for k in kpis if k.get("is_active")]
    return kpis


def get_kpis_by_department(active_only=True):
    result = {}
    for k in get_kpis(active_only=active_only):
        result.setdefault(k["department"], []).append(k)
    return result


# ---------------------------------------------------------------------------
# Machines
# ---------------------------------------------------------------------------
def get_machines(active_only=True, refresh=False):
    if refresh:
        invalidate()
    machines = _get_registry()["machines"]
    if active_only:
        machines = [m for m in machines if m.get("is_active")]
    return machines


def get_machine_types(active_only=True, refresh=False):
    if refresh:
        invalidate()
    types = _get_registry()["machine_types"]
    if active_only:
        types = [t for t in types if t.get("is_active")]
    return types


# ---------------------------------------------------------------------------
# CEO access helpers (used by permissions & user management)
# ---------------------------------------------------------------------------
def get_ceo_config_for_user(user):
    """Return active KPI CEO Access record for user (or None)."""
    name = frappe.db.get_value("KPI CEO Access", {"user": user, "is_active": 1}, "name",
                               order_by="creation desc")
    if not name:
        return None
    return frappe.get_doc("KPI CEO Access", name)