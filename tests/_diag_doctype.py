# Diagnostic: stale bench-wide module map + raw-context DB read.
# env/bin/python tests/_diag_doctype.py <site>
import os
import sys
import warnings

import frappe

site = sys.argv[1] if len(sys.argv) > 1 else "productix-c.local"
os.makedirs(os.path.join(os.path.expanduser("~"), "logs"), exist_ok=True)
os.makedirs(os.path.join(os.path.abspath("sites"), site, "logs"), exist_ok=True)
frappe.init(site=site, sites_path=os.path.abspath("sites"))
frappe.connect()
print("SITE =", site)
rows = frappe.db.sql("SELECT name FROM `tabDocType`")
print("DOCTYPE_COUNT =", len(rows), "| sample:", [r[0] for r in rows[:3]])

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    frappe.setup_module_map(include_all_apps=True)
    print("MODULE_MAP_KEYS =", sorted((frappe.local.app_modules or {}).keys()))
    print("DUP_WARNINGS =", [str(w.message) for w in caught])

c1 = frappe.cache.get_value("app_modules")
c2 = frappe.cache.get_value("app_modules", shared=True)
print("SITE_CACHED_KEYS =", sorted((c1 or {}).keys()) if c1 else None)
print("SHARED_CACHED_KEYS =", sorted((c2 or {}).keys()) if c2 else None)
