# Future-module E2E state proof (raw python, site-scoped).
# env/bin/python tests/_future_module_state.py [site]
import json
import os
import sys

import frappe

site = sys.argv[1] if len(sys.argv) > 1 else "productix-c.local"
os.makedirs(os.path.join(os.path.expanduser("~"), "logs"), exist_ok=True)
for d in (
    os.path.join(os.path.abspath("sites"), site, "logs"),
    os.path.join(os.path.dirname(os.path.abspath("sites")), site, "logs"),
):
    os.makedirs(d, exist_ok=True)
frappe.init(site=site, sites_path=os.path.abspath("sites"))
frappe.connect()
frappe.set_user("Administrator")

from productix_core.modules.registry import get_registry  # noqa: E402
from productix_core.modules.entitlement import is_module_enabled  # noqa: E402

print("REGISTRY =", json.dumps(sorted(get_registry().keys())))
print("ENTITLEMENT =", json.dumps(sorted(
    (r["module_key"], r["enabled"])
    for r in frappe.get_all(
        "Productix Module Entitlement",
        fields=["module_key", "enabled"],
    )
)))
print("MFG_ENABLED =", is_module_enabled("manufacturing"))
print("MODULE_DEF =", json.dumps([
    {"name": r["module_name"], "app": r["app_name"]}
    for r in frappe.get_all(
        "Module Def",
        filters={"module_name": "Manufacturing Line"},
        fields=["module_name", "app_name"],
    )
]))
print("INSTALLED =", json.dumps(frappe.get_installed_apps()))
