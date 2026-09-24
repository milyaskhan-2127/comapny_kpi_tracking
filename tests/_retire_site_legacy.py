#!/usr/bin/env python3
"""Retire the legacy monolithic `productix` app from a site's installed_apps.

bench --site <site> uninstall-app productix is blocked by frappe's substring
dependency guard ("productix" is a substring of required_apps "productix_core",
so frappe thinks the app is still required). The legacy app owns no Module Defs
after the repoint migration (productix_core install repoints them) and defines
no uninstall hooks, so remove_app's net effect equals remove_from_installed_apps
+ Installed Application versions update + cache clear. We invoke those same
primitives directly. This is the exact procedure proven on productix-mig.local.

Usage (bench root, direct python):
    env/bin/python tests/_retire_site_legacy.py <site>

Exit 0 = legacy removed from installed_apps (or already retired).
"""
import json
import os
import sys

import frappe

site = sys.argv[1]
out = []


def _connect():
    # explicit sites_path (same proven pattern as scripts/migration_check.py):
    # bare frappe.init(site=...) from raw python raises IncorrectSitePath.
    sites_path = os.path.abspath("sites")
    os.makedirs(os.path.join(sites_path, site, "logs"), exist_ok=True)
    # raw-python frappe logger writes to bench-root/<site>/logs (not sites/<site>)
    os.makedirs(os.path.join(os.getcwd(), site, "logs"), exist_ok=True)
    frappe.init(site=site, sites_path=sites_path)
    frappe.connect()


_connect()
before = frappe.get_installed_apps()
out.append("installed_apps BEFORE: " + json.dumps(before))
if "productix" not in before:
    out.append("ALREADY_RETIRED: legacy app not in installed_apps — nothing to do")
    frappe.destroy()
    print("\n".join(out))
    print("RETIRE_OK_ALREADY", site)
    sys.exit(0)

from frappe.installer import remove_from_installed_apps

remove_from_installed_apps("productix")
out.append("installed_apps AFTER remove: " + json.dumps(frappe.get_installed_apps()))

# mirror bench uninstall-app epilogue
frappe.get_single("Installed Applications").update_versions()
frappe.db.commit()
frappe.clear_cache()
frappe.destroy()

# verification pass (fresh connection)
_connect()
out.append(
    "Installed Application rows: "
    + json.dumps(
        frappe.get_all(
            "Installed Application",
            fields=["app_name", "app_version"],
            order_by="app_name",
        ),
        default=str,
    )
)
leftover = frappe.get_all(
    "Module Def", filters={"app_name": "productix"}, pluck="name"
)
out.append("Module Defs still owned by legacy app: " + json.dumps(leftover))
frappe.destroy()

print("\n".join(out))
if leftover:
    print("RETIRE_FAIL leftover module ownership", site)
    sys.exit(1)
print("RETIRE_OK", site)
