from __future__ import unicode_literals
from frappe import _

app_name = "productix_kpi"
app_title = "Productix KPI Tracking"
app_publisher = "TechoHub"
app_description = "Productix KPI Tracking module — department KPIs, machine health, AI assistant, backups (modularized from the monolithic productix app)"
app_email = "support@techohub.net"
app_license = "MIT"
app_version = "1.0.0"

# -----------------------------------------------------------------
# Apps (installed alongside this app)
# -----------------------------------------------------------------
required_apps = ["erpnext", "productix_core"]

# -----------------------------------------------------------------
# Modules
# -----------------------------------------------------------------
app_include_css = [
    "/assets/productix_kpi/css/kpi_tracking.css",
]
app_include_js = [
    "/assets/productix_kpi/js/productix.js",
]

# -----------------------------------------------------------------
# DocType JS overrides (client scripts bundled per doctype)
# -----------------------------------------------------------------
doctype_js = {
    "User": "public/js/custom_scripts/kpi_user_scripts.js",
}

# -----------------------------------------------------------------
# Ignore links on delete (allow deleting users without foreign key locks on notifications)
# -----------------------------------------------------------------
ignore_links_on_delete = [
    "KPI User Assignment",
    "KPI Data Entry",
    "KPI Alert",
    "KPI Definition",
    "KPI Prediction",
    "KPI Operational Data",
    "KPI Settings",
    "Machine Reading",
    "Machine Health Log",
]

# -----------------------------------------------------------------
# After install / uninstall — keep the productix module registry in sync.
# -----------------------------------------------------------------
after_install = "productix_kpi.install.after_install"
after_uninstall = "productix_kpi.install.after_uninstall"

# -----------------------------------------------------------------
# Scheduled jobs
# -----------------------------------------------------------------
scheduler_events = {
    "daily": [
        "productix_kpi.kpi_tracking.services.alert_engine.run_scheduled_alert_check",
        "productix_kpi.kpi_tracking.services.machine_health.run_scheduled_health_check",
    ],
    "hourly": [
        "productix_kpi.kpi_tracking.tasks.run_scheduled_predictions",
    ],
    "all": [],
}

# -----------------------------------------------------------------
# DocType events — master registry cache invalidation.
# Any change to these records flows everywhere (Overview, Department
# dashboards, Machine Health, Users, CEO access, Alerts, Reports, AI,
# Backup) without a restart, because consumers read the registry cache.
# -----------------------------------------------------------------
doc_events = {
    "KPI Department": {
        "after_insert": "productix_kpi.kpi_tracking.services.registry.invalidate_cache",
        "on_update": "productix_kpi.kpi_tracking.services.registry.invalidate_cache",
        "on_trash": "productix_kpi.kpi_tracking.services.registry.invalidate_cache",
    },
    "KPI Definition": {
        "after_insert": "productix_kpi.kpi_tracking.services.registry.invalidate_cache",
        "on_update": "productix_kpi.kpi_tracking.services.registry.invalidate_cache",
        "on_trash": "productix_kpi.kpi_tracking.services.registry.invalidate_cache",
    },
    "Machine": {
        "after_insert": "productix_kpi.kpi_tracking.services.registry.invalidate_cache",
        "on_update": "productix_kpi.kpi_tracking.services.registry.invalidate_cache",
        "on_trash": "productix_kpi.kpi_tracking.services.registry.invalidate_cache",
    },
    "Machine Type": {
        "after_insert": "productix_kpi.kpi_tracking.services.registry.invalidate_cache",
        "on_update": "productix_kpi.kpi_tracking.services.registry.invalidate_cache",
        "on_trash": "productix_kpi.kpi_tracking.services.registry.invalidate_cache",
    },
    "KPI CEO Access": {
        "after_insert": "productix_kpi.kpi_tracking.services.registry.invalidate_cache",
        "on_update": "productix_kpi.kpi_tracking.services.registry.invalidate_cache",
        "on_trash": "productix_kpi.kpi_tracking.services.registry.invalidate_cache",
    },
    "KPI Settings": {
        "on_update": "productix_kpi.kpi_tracking.services.registry.invalidate_cache",
    },
}

# -----------------------------------------------------------------
# Permissions
# -----------------------------------------------------------------
has_permission = {
    "KPI Alert": "productix_kpi.kpi_tracking.security.permissions.kpi_has_permission",
    "KPI Data Entry": "productix_kpi.kpi_tracking.security.permissions.kpi_has_permission",
    "KPI Definition": "productix_kpi.kpi_tracking.security.permissions.kpi_has_permission",
    "KPI Prediction": "productix_kpi.kpi_tracking.security.permissions.kpi_has_permission",
    "KPI Department": "productix_kpi.kpi_tracking.security.permissions.kpi_has_permission",
    "KPI Formula": "productix_kpi.kpi_tracking.security.permissions.kpi_has_permission",
    "KPI Template": "productix_kpi.kpi_tracking.security.permissions.kpi_has_permission",
    "KPI Variable": "productix_kpi.kpi_tracking.security.permissions.kpi_has_permission",
    "KPI Operational Table": "productix_kpi.kpi_tracking.security.permissions.kpi_has_permission",
    "KPI Operational Data": "productix_kpi.kpi_tracking.security.permissions.kpi_has_permission",
    "KPI Settings": "productix_kpi.kpi_tracking.security.permissions.kpi_has_permission",
    "KPI User Assignment": "productix_kpi.kpi_tracking.security.permissions.kpi_has_permission",
    "KPI Business Unit": "productix_kpi.kpi_tracking.security.permissions.kpi_has_permission",
    "Machine": "productix_kpi.kpi_tracking.security.permissions.kpi_has_permission",
    "Machine Type": "productix_kpi.kpi_tracking.security.permissions.kpi_has_permission",
    "Machine Reading": "productix_kpi.kpi_tracking.security.permissions.kpi_has_permission",
    "Machine Health Log": "productix_kpi.kpi_tracking.security.permissions.kpi_has_permission",
}

# -----------------------------------------------------------------
# Permission Query Conditions
# -----------------------------------------------------------------
permission_query_conditions = {
    "KPI Alert": "productix_kpi.kpi_tracking.security.permissions.get_kpi_alert_query_conditions",
    "KPI Data Entry": "productix_kpi.kpi_tracking.security.permissions.get_kpi_data_entry_query_conditions",
    "KPI Definition": "productix_kpi.kpi_tracking.security.permissions.get_kpi_definition_query_conditions",
    "KPI Prediction": "productix_kpi.kpi_tracking.security.permissions.get_kpi_prediction_query_conditions",
    "KPI Formula": "productix_kpi.kpi_tracking.security.permissions.get_kpi_admin_doctype_query_conditions",
    "KPI Template": "productix_kpi.kpi_tracking.security.permissions.get_kpi_admin_doctype_query_conditions",
    "KPI Variable": "productix_kpi.kpi_tracking.security.permissions.get_kpi_admin_doctype_query_conditions",
    "KPI Operational Table": "productix_kpi.kpi_tracking.security.permissions.get_kpi_admin_doctype_query_conditions",
    "KPI Operational Data": "productix_kpi.kpi_tracking.security.permissions.get_kpi_admin_doctype_query_conditions",
    "KPI Settings": "productix_kpi.kpi_tracking.security.permissions.get_kpi_admin_doctype_query_conditions",
    "KPI User Assignment": "productix_kpi.kpi_tracking.security.permissions.get_kpi_admin_doctype_query_conditions",
    "KPI Department": "productix_kpi.kpi_tracking.security.permissions.get_kpi_department_query_conditions",
    "KPI Business Unit": "productix_kpi.kpi_tracking.security.permissions.get_kpi_admin_doctype_query_conditions",
    "Machine": "productix_kpi.kpi_tracking.security.permissions.get_machine_query_conditions",
    "Machine Type": "productix_kpi.kpi_tracking.security.permissions.get_kpi_machine_type_query_conditions",
    "Machine Reading": "productix_kpi.kpi_tracking.security.permissions.get_machine_reading_query_conditions",
    "Machine Health Log": "productix_kpi.kpi_tracking.security.permissions.get_machine_reading_query_conditions",
}

# -----------------------------------------------------------------
# Fixtures — export these on bench export-fixtures
# -----------------------------------------------------------------
fixtures = [
    {"dt": "Role", "filters": [["name", "in", [
        "KPI Admin",
        "KPI Employee",
        "KPI Manager",
        "KPI Contributor",
        "KPI CEO",
    ]]]},
    {"dt": "Workspace", "filters": [["module", "in", ["KPI Tracking"]]]},
    {"dt": "Report", "filters": [["module", "in", ["KPI Tracking"]]]},
]

# -----------------------------------------------------------------
# Boot session (KPI portion — reports sync + backups page provisioning)
# -----------------------------------------------------------------
boot_session = "productix_kpi.utils.boot.boot_session"