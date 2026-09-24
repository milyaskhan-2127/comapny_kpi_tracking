from __future__ import unicode_literals
from frappe import _

app_name = "productix_core"
app_title = "Productix Core"
app_publisher = "TechoHub"
app_description = "Productix Core platform — settings, licensing/tenancy, module registry & entitlement enforcement, shared audit log, shared utilities (modularized from the monolithic productix app)"
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
app_include_js = [
    "/assets/productix_core/js/productix_core.js",
]

# -----------------------------------------------------------------
# DocType events
# -----------------------------------------------------------------
doc_events = {
    "User": {
        "after_insert": "productix_core.subscription_management.utils.tenant_utils.set_user_tenant",
        "on_update": "productix_core.subscription_management.utils.tenant_utils.handle_user_save",
        "on_trash": "productix_core.subscription_management.utils.tenant_utils.handle_user_trash",
    },
}

# -----------------------------------------------------------------
# Ignore links on delete (ERPNext-native doctypes touched during
# user cleanup — owned at the platform level, always installed)
# -----------------------------------------------------------------
ignore_links_on_delete = [
    "Notification Log",
    "Activity Log",
]

# -----------------------------------------------------------------
# Fixtures — export these on bench export-fixtures
# -----------------------------------------------------------------
fixtures = [
    {"dt": "Custom Field", "filters": [["name", "=", "User-custom_user_role"]]},
]

# -----------------------------------------------------------------
# Whitelisted API Methods (accessible via /api/method/...)
# -----------------------------------------------------------------
# These are auto-discovered from @frappe.whitelist() decorators.
# Listed here for documentation:
#   productix_core.api.subscription.get_subscription_status
#   productix_core.api.subscription.process_renewal_webhook
#   productix_core.productix_core.doctype.ai_agent_log.ai_agent_log.log_event
#   productix_core.utils.email_utils.test_send_email

# -----------------------------------------------------------------
# Boot session (core portion — license + unread notifications + module registry).
# Every installed productix app may register its own boot_session hook;
# Frappe executes all of them (see frappe/boot.py: get_bootinfo).
# -----------------------------------------------------------------
boot_session = "productix_core.utils.boot.boot_session"

# -----------------------------------------------------------------
# On login
# -----------------------------------------------------------------
on_login = "productix_core.subscription_management.utils.tenant_utils.check_license_on_login"

# -----------------------------------------------------------------
# Request gate — server-side module entitlement enforcement.
# Parses /api/method/<app>.… calls and rejects disabled modules with 403.
# -----------------------------------------------------------------
before_request = "productix_core.modules.entitlement.gate_request"

# -----------------------------------------------------------------
# After install — first-run platform provisioning
# -----------------------------------------------------------------
after_install = "productix_core.install.after_install"