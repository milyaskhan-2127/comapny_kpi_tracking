# Site-level legacy/reference diagnostics — raw python.
# env/bin/python tests/_site_legacy_diag.py <site>
# Prints installed_apps + any tabModule Def rows still owned by the retired
# legacy `productix` app. Import-time module warnings print above this line.
import json
import os
import sys

import frappe

site = sys.argv[1]
os.makedirs(os.path.join(os.path.expanduser("~"), "logs"), exist_ok=True)
for d in (
    os.path.join(os.path.abspath("sites"), site, "logs"),
    os.path.join(os.path.dirname(os.path.abspath("sites")), site, "logs"),
):
    os.makedirs(d, exist_ok=True)
frappe.init(site=site, sites_path=os.path.abspath("sites"))
frappe.connect()
frappe.set_user("Administrator")

inst = list(frappe.get_installed_apps())
legacy_exact = frappe.db.sql(
    "select name, app_name from `tabModule Def` where app_name = 'productix'",
    as_dict=True,
)
print(
    "LEGACY_DIAG",
    json.dumps(
        {
            "site": site,
            "installed_apps": inst,
            "legacy_installed": "productix" in inst,
            "module_defs_app_productix": [
                {"name": r.name, "app": r.app} for r in legacy_exact
            ],
        }
    ),
)
