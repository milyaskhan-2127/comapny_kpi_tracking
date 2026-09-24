from __future__ import unicode_literals
from frappe import _

app_name = "productix_recipe"
app_title = "Productix Recipe & Production"
app_publisher = "TechoHub"
app_description = "Productix Recipe & Production module — built on ERPNext (modularized from the monolithic productix app)"
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
    "/assets/productix_recipe/css/productix.css",
]
app_include_js = [
    "/assets/productix_recipe/js/productix.js",
]

# -----------------------------------------------------------------
# DocType JS overrides (client scripts bundled per doctype)
# -----------------------------------------------------------------
doctype_js = {
    "Item": "public/js/custom_scripts/recipe_doctype_scripts.js",
    "Supplier": "public/js/custom_scripts/recipe_doctype_scripts.js",
    "Batch": "public/js/custom_scripts/recipe_doctype_scripts.js",
    "Purchase Receipt": "public/js/custom_scripts/recipe_doctype_scripts.js",
}

# -----------------------------------------------------------------
# DocType-level overrides
# -----------------------------------------------------------------
override_doctype_class = {
    "Purchase Receipt": "productix_recipe.overrides.purchase_receipt.ProductixPurchaseReceipt",
    "Work Order": "productix_recipe.overrides.work_order.ProductixWorkOrder",
    "Batch": "productix_recipe.overrides.batch.ProductixBatch",
}

# -----------------------------------------------------------------
# DocType events
# -----------------------------------------------------------------
doc_events = {
    "Purchase Receipt": {
        "before_validate": "productix_recipe.recipe_management.utils.grn_utils.before_purchase_receipt_validate",
        "on_submit": "productix_recipe.recipe_management.utils.grn_utils.on_purchase_receipt_submit",
        "on_cancel": "productix_recipe.recipe_management.utils.grn_utils.on_purchase_receipt_cancel",
    },
    "Work Order": {
        "on_submit": "productix_recipe.recipe_management.utils.production_utils.on_work_order_submit",
        "on_cancel": "productix_recipe.recipe_management.utils.production_utils.on_work_order_cancel",
    },
    "Stock Entry": {
        "before_save": "productix_recipe.recipe_management.utils.fefo_utils.apply_fefo_on_stock_entry",
    },
}

# -----------------------------------------------------------------
# Ignore links on delete (allow deleting records without foreign key locks)
# -----------------------------------------------------------------
ignore_links_on_delete = []

# -----------------------------------------------------------------
# After install / uninstall — keep the productix module registry in sync.
# -----------------------------------------------------------------
after_install = "productix_recipe.install.after_install"
after_uninstall = "productix_recipe.install.after_uninstall"

# -----------------------------------------------------------------
# Scheduled jobs
# -----------------------------------------------------------------
scheduler_events = {
    "daily": [
        "productix_recipe.tasks.run_daily_inventory_scan",
        "productix_recipe.tasks.mark_expired_batches",
    ],
    "all": [],
}

# -----------------------------------------------------------------
# Permissions
# -----------------------------------------------------------------
has_permission = {
    "Recipe": "productix_recipe.recipe_management.doctype.recipe.recipe.has_permission",
    "Production Order": "productix_recipe.recipe_management.doctype.production_order.production_order.has_permission",
}

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
    ]]]},
    {
        "dt": "Custom Field",
        "filters": [["module", "in", ["Recipe Management"]]],
    },
    {
        "dt": "Property Setter",
        "filters": [["module", "in", ["Recipe Management"]]],
    },
    {"dt": "Workspace", "filters": [["module", "in", ["Recipe Management"]]]},
    {"dt": "Number Card", "filters": [["module", "in", ["Recipe Management"]]]},
    {"dt": "Report", "filters": [["module", "in", ["Recipe Management"]]]},
]

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
        "productix_recipe.utils.helpers.get_usable_stock",
        "productix_recipe.utils.helpers.get_batch_status_label",
    ]
}