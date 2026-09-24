#!/usr/bin/env python3
"""Print definitive site state: installed_apps, module ownership, registry.

Usage (bench root): env/bin/python tests/_site_status.py <site>
"""
import json
import os
import sys

import frappe

site = sys.argv[1]
sites_path = os.path.abspath("sites")
os.makedirs(os.path.join(sites_path, site, "logs"), exist_ok=True)
os.makedirs(os.path.join(os.getcwd(), site, "logs"), exist_ok=True)
frappe.init(site=site, sites_path=sites_path)
frappe.connect()

print("SITE:", site)
print("INSTALLED:", json.dumps(frappe.get_installed_apps()))
owned = frappe.get_all(
    "Module Def", fields=["name", "app_name"], order_by="app_name"
)
by_app = {}
for r in owned:
    by_app.setdefault(r["app_name"], []).append(r["name"])
print("MODULE_OWNERSHIP:")
for app in sorted(by_app):
    print("  ", app, "->", sorted(by_app[app]))
try:
    from productix_core.modules.registry import get_registry

    print("REGISTRY_KEYS:", sorted(get_registry()))
except Exception as e:
    print("REGISTRY_KEYS: ERR", str(e)[:120])
try:
    print(
        "ENTITLEMENT_ROWS:",
        frappe.get_all(
            "Productix Module Entitlement", fields=["module_key", "module_name", "enabled"]
        ),
    )
except Exception as e:
    print("ENTITLEMENT_ROWS: UNAVAILABLE", type(e).__name__, str(e)[:300])
try:
    from frappe.get_installed_apps import _  # noqa: F401  (placeholder guard)
except Exception:
    pass
print(
    "INSTALLED_APP_VERSIONS:",
    json.dumps(
        frappe.get_all(
            "Installed Application",
            fields=["app_name", "app_version"],
            order_by="app_name",
        ),
        default=str,
    ),
)
frappe.destroy()
print("STATUS_OK")
