#!/usr/bin/env python3
"""Full row-count + ownership fingerprint of a site (pre/post migration proof).

Usage (bench root, direct python):
    env/bin/python tests/_local_data_snapshot.py <site> <outfile.json>

Writes JSON: installed_apps, module_app_map (Module Def -> app), doctype_counts
for EVERY DocType in tabDocType (business data + meta), meta name sets
(roles/reports/number_cards/workspaces/pages/custom_fields/property_setters),
docfield_total, entitlement rows, registry keys.
Compare snapshots with tests/_local_diff.py for the zero-data-loss verdict.
"""
import json
import os
import sys

import frappe

site = sys.argv[1]
outfile = sys.argv[2]

# explicit sites_path: bare frappe.init(site=...) from raw python raises
# IncorrectSitePath on this frappe build — same proven pattern as
# scripts/migration_check.py (run from the bench root).
sites_path = os.path.abspath("sites")
os.makedirs(os.path.join(sites_path, site, "logs"), exist_ok=True)
# raw-python frappe logger writes to bench-root/<site>/logs (not sites/<site>)
os.makedirs(os.path.join(os.getcwd(), site, "logs"), exist_ok=True)
frappe.init(site=site, sites_path=sites_path)
frappe.connect()

snap = {"site": site}
snap["installed_apps"] = frappe.get_installed_apps()

try:
    snap["module_app_map"] = {
        r["name"]: r["app_name"]
        for r in frappe.get_all("Module Def", fields=["name", "app_name"])
    }
except Exception as e:  # pragma: no cover
    snap["module_app_map"] = "ERR:" + str(e)

counts = {}
for dt in frappe.get_all("DocType", pluck="name"):
    # guard with table_exists: frappe.db.count on table-less (single) doctypes
    # logs a full stack trace per miss — avoid the noise.
    if not frappe.db.table_exists(dt):
        counts[dt] = "NO_TABLE"
        continue
    try:
        counts[dt] = frappe.db.count(dt)
    except Exception as e:
        counts[dt] = "NO_TABLE:" + type(e).__name__
snap["doctype_counts"] = counts


def names(doctype):
    try:
        return sorted(frappe.get_all(doctype, pluck="name"))
    except Exception:
        return []


snap["meta_names"] = {
    "Role": names("Role"),
    "Report": names("Report"),
    "Number Card": names("Number Card"),
    "Workspace": names("Workspace"),
    "Page": names("Page"),
    "Custom Field": names("Custom Field"),
    "Property Setter": names("Property Setter"),
}

try:
    snap["docfield_total"] = frappe.db.count("DocField")
except Exception:
    snap["docfield_total"] = None

try:
    snap["entitlement_rows"] = [
        {"module_key": r["module_key"], "enabled": r["enabled"]}
        for r in frappe.get_all(
            "Productix Module Entitlement", fields=["module_key", "enabled"]
        )
    ]
except Exception as e:
    snap["entitlement_rows"] = "UNAVAILABLE:" + type(e).__name__

try:
    from productix_core.modules.registry import get_registry

    snap["reg_keys"] = sorted(get_registry())
except Exception as e:
    snap["reg_keys"] = "ERR:" + str(e)

frappe.destroy()
with open(outfile, "w", encoding="utf-8") as f:
    json.dump(snap, f, indent=1, sort_keys=True, default=str)
print("SNAPSHOT_OK", outfile, "doctypes=", len(snap["doctype_counts"]))
