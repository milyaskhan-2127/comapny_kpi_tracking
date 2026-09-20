from __future__ import unicode_literals
from frappe import _

app_name = "productix"
app_title = "Productix"
app_publisher = "TechoHub"
app_description = "Recipe & Production ERP — built on ERPNext"
app_email = "support@techohub.net"
app_license = "MIT"
app_version = "1.0.0"

# -----------------------------------------------------------------
# Apps (installed alongside this app)
# -----------------------------------------------------------------
required_apps = ["erpnext"]

# -----------------------------------------------------------------
# Modules
# -----------------------------------------------------------------
app_include_css = [
    "/assets/productix/css/productix.css",
    "/assets/productix/css/kpi_tracking.css",
]
app_include_js = [
    "/assets/productix/js/productix.js",
    "/assets/productix/js/backup_manager.js",
    "/assets/productix/js/custom_scripts/native_doctype_scripts.js",
]

# -----------------------------------------------------------------
# DocType JS overrides (client scripts bundled per doctype)
# -----------------------------------------------------------------
doctype_js = {
    "Item": "public/js/custom_scripts/native_doctype_scripts.js",
    "Supplier": "public/js/custom_scripts/native_doctype_scripts.js",
    "Batch": "public/js/custom_scripts/native_doctype_scripts.js",
    "Purchase Receipt": "public/js/custom_scripts/native_doctype_scripts.js",
    "User": "public/js/custom_scripts/native_doctype_scripts.js",
}

# -----------------------------------------------------------------
# DocType-level overrides
# -----------------------------------------------------------------
override_doctype_class = {
    "Purchase Receipt": "productix.overrides.purchase_receipt.ProductixPurchaseReceipt",
    "Work Order": "productix.overrides.work_order.ProductixWorkOrder",
    "Batch": "productix.overrides.batch.ProductixBatch",
}

# -----------------------------------------------------------------
# DocType events
# -----------------------------------------------------------------
doc_events = {
    "Purchase Receipt": {
        "before_validate": "productix.recipe_management.utils.grn_utils.before_purchase_receipt_validate",
        "on_submit": "productix.recipe_management.utils.grn_utils.on_purchase_receipt_submit",
        "on_cancel": "productix.recipe_management.utils.grn_utils.on_purchase_receipt_cancel",
    },
    "Work Order": {
        "on_submit": "productix.recipe_management.utils.production_utils.on_work_order_submit",
        "on_cancel": "productix.recipe_management.utils.production_utils.on_work_order_cancel",
    },
    "Stock Entry": {
        "before_save": "productix.recipe_management.utils.fefo_utils.apply_fefo_on_stock_entry",
    },
    "User": {
        "after_insert": "productix.subscription_management.utils.tenant_utils.set_user_tenant",
        "on_update": "productix.subscription_management.utils.tenant_utils.handle_user_save",
        "on_trash": "productix.subscription_management.utils.tenant_utils.handle_user_trash",
    },
}

# -----------------------------------------------------------------
# Ignore links on delete (allow deleting users without foreign key locks on notifications)
# -----------------------------------------------------------------
ignore_links_on_delete = [
    "Message Notification",
    "Instruction Message",
    "Notification Log",
    "KPI User Assignment",
    "KPI Data Entry",
    "KPI Alert",
    "KPI Definition",
    "KPI Prediction",
    "KPI Operational Data",
    "KPI Settings",
    "Activity Log",
]

# -----------------------------------------------------------------
# Scheduled jobs
# -----------------------------------------------------------------
scheduler_events = {
    "daily": [
        "productix.alerts.tasks.run_daily_inventory_scan",
        "productix.alerts.tasks.mark_expired_batches",
        "productix.kpi_tracking.services.alert_engine.run_scheduled_alert_check",
    ],
    "hourly": [
        "productix.kpi_tracking.tasks.run_scheduled_predictions",
    ],
    "all": [],
}

# -----------------------------------------------------------------
# Permissions
# -----------------------------------------------------------------
has_permission = {
    "Recipe": "productix.recipe_management.doctype.recipe.recipe.has_permission",
    "Production Order": "productix.recipe_management.doctype.production_order.production_order.has_permission",
    "KPI Alert": "productix.kpi_tracking.security.permissions.kpi_has_permission",
    "KPI Data Entry": "productix.kpi_tracking.security.permissions.kpi_has_permission",
    "KPI Definition": "productix.kpi_tracking.security.permissions.kpi_has_permission",
    "KPI Prediction": "productix.kpi_tracking.security.permissions.kpi_has_permission",
    "KPI Department": "productix.kpi_tracking.security.permissions.kpi_has_permission",
    "KPI Formula": "productix.kpi_tracking.security.permissions.kpi_has_permission",
    "KPI Template": "productix.kpi_tracking.security.permissions.kpi_has_permission",
    "KPI Variable": "productix.kpi_tracking.security.permissions.kpi_has_permission",
    "KPI Operational Table": "productix.kpi_tracking.security.permissions.kpi_has_permission",
    "KPI Operational Data": "productix.kpi_tracking.security.permissions.kpi_has_permission",
    "KPI Settings": "productix.kpi_tracking.security.permissions.kpi_has_permission",
    "KPI User Assignment": "productix.kpi_tracking.security.permissions.kpi_has_permission",
    "KPI Business Unit": "productix.kpi_tracking.security.permissions.kpi_has_permission",
}

# -----------------------------------------------------------------
# Permission Query Conditions
# -----------------------------------------------------------------
permission_query_conditions = {
    "KPI Alert": "productix.kpi_tracking.security.permissions.get_kpi_alert_query_conditions",
    "KPI Data Entry": "productix.kpi_tracking.security.permissions.get_kpi_data_entry_query_conditions",
    "KPI Definition": "productix.kpi_tracking.security.permissions.get_kpi_definition_query_conditions",
    "KPI Prediction": "productix.kpi_tracking.security.permissions.get_kpi_prediction_query_conditions",
    "KPI Formula": "productix.kpi_tracking.security.permissions.get_kpi_admin_doctype_query_conditions",
    "KPI Template": "productix.kpi_tracking.security.permissions.get_kpi_admin_doctype_query_conditions",
    "KPI Variable": "productix.kpi_tracking.security.permissions.get_kpi_admin_doctype_query_conditions",
    "KPI Operational Table": "productix.kpi_tracking.security.permissions.get_kpi_admin_doctype_query_conditions",
    "KPI Operational Data": "productix.kpi_tracking.security.permissions.get_kpi_admin_doctype_query_conditions",
    "KPI Settings": "productix.kpi_tracking.security.permissions.get_kpi_admin_doctype_query_conditions",
    "KPI User Assignment": "productix.kpi_tracking.security.permissions.get_kpi_admin_doctype_query_conditions",
    "KPI Department": "productix.kpi_tracking.security.permissions.get_kpi_admin_doctype_query_conditions",
    "KPI Business Unit": "productix.kpi_tracking.security.permissions.get_kpi_admin_doctype_query_conditions",
}

# -----------------------------------------------------------------
# Role defaults
# -----------------------------------------------------------------
role_defaults = {}

# -----------------------------------------------------------------
# Fixtures — export these on bench export-fixtures
# -----------------------------------------------------------------
fixtures = [
    {"dt": "Role", "filters": [["name", "in", [
        "Factory Admin",
        "Assistant System Administrator",
        "Production Manager",
        "Store Keeper",
        "Purchase Manager",
        "General Staff",
        "KPI Admin",
        "KPI Employee",
        "KPI Manager",
        "KPI Contributor",
    ]]]},
    {
        "dt": "Custom Field",
        "filters": [["module", "in", [
            "Recipe Management",
            "Subscription Management",
            "Instruction Room",
            "Alerts",
            "KPI Tracking",
        ]]],
    },
    {
        "dt": "Property Setter",
        "filters": [["module", "in", [
            "Recipe Management",
            "Subscription Management",
            "Instruction Room",
            "Alerts",
            "KPI Tracking",
        ]]],
    },
    {"dt": "Workspace", "filters": [["module", "in", ["Recipe Management", "KPI Tracking"]]]},
    {"dt": "Number Card", "filters": [["module", "in", ["Recipe Management", "KPI Tracking"]]]},
    {"dt": "Report", "filters": [["module", "in", ["Recipe Management", "KPI Tracking"]]]},
]

# -----------------------------------------------------------------
# Whitelisted API Methods (accessible via /api/method/...)
# -----------------------------------------------------------------
# These are auto-discovered from @frappe.whitelist() decorators.
# Listed here for documentation:
#   productix.api.subscription.get_subscription_status
#   productix.api.subscription.process_renewal_webhook
#   productix.api.inventory.get_item_stock_info
#   productix.api.inventory.get_dashboard_kpis
#   productix.alerts.doctype.ai_agent_log.ai_agent_log.trigger_manual_scan
#   productix.alerts.doctype.ai_agent_log.ai_agent_log.log_event
#   productix.instruction_room.doctype.instruction_message.instruction_message.clear_all_messages
#   productix.instruction_room.doctype.instruction_message.instruction_message.get_unread_count
#   productix.instruction_room.doctype.instruction_message.instruction_message.mark_all_read

# -----------------------------------------------------------------
# Website
# -----------------------------------------------------------------
website_route_rules = [
    {"from_route": "/productix/<path:app_path>", "to_route": "productix"},
]

# -----------------------------------------------------------------
# Jinja globals
# -----------------------------------------------------------------
jinja = {
    "methods": [
        "productix.utils.helpers.get_usable_stock",
        "productix.utils.helpers.get_batch_status_label",
    ]
}

# -----------------------------------------------------------------
# Boot session
# -----------------------------------------------------------------
boot_session = "productix.utils.boot.boot_session"

# -----------------------------------------------------------------
# On login
# -----------------------------------------------------------------
on_login = "productix.subscription_management.utils.tenant_utils.check_license_on_login"
