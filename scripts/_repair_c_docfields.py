"""Repair site C tabDocField from shipped JSON via frappe's own sync_for(force=1).

Root cause (see ACCEPTANCE_EVIDENCE.md): site C was re-seeded with the legacy
baseline dump via productix_kpi.api.backup.restore_backup_file (fast path pipes
the raw dump into mariadb; fallback swallows statement errors). The dump's
tabDocField snapshot replaced install-written children for dump-covered
doctypes and wiped children for doctypes not in the dump, while dying before
tabDocType — leaving parents (rows + migration_hash) intact and children
missing/inconsistent. Wave-2 imports also left row-without-children for
Machine*/KPI CEO* (stale site-scoped meta cache family).

Fix = force frappe's standard doctype re-import for the four modular apps
(the same code path bench install-app --force uses), then clear caches.
Reads nothing from customer data; touches only tabDocType/tabDocField
(and DocPerm per frappe's "perms only synced if none exist" rule).

Usage: standalone (bench execute cannot run scripts.* targets):
  env/bin/python scripts/_repair_c_docfields.py   (inside backend container)
"""
import os
import sys

SITE = "productix-c.local"
SITES_PATH = "/home/frappe/frappe-bench/sites"
APPS = ("productix_core", "productix_recipe", "productix_kpi", "productix_instruction")

PRODUCTIX_DOCTYPES = (
    "Productix Settings",
    "Productix Module Entitlement",
    "Productix Tenant",
    "Productix License",
    "AI Agent Log",
    "Recipe",
    "Production Batch",
    "Consumption Log",
    "KPI Alert",
    "KPI Definition",
    "KPI CEO Access",
    "Machine",
    "Machine Type",
    "Machine Type Parameter",
    "Machine Reading",
    "Instruction Message",
    "Message Notification",
)


def field_counts():
    placeholders = ",".join(["%s"] * len(PRODUCTIX_DOCTYPES))
    rows = frappe.db.sql(
        "SELECT parent, COUNT(*) AS c FROM `tabDocField` WHERE parent IN (%s) "
        "GROUP BY parent ORDER BY parent" % placeholders,
        PRODUCTIX_DOCTYPES,
        as_dict=True,
    )
    return {r.parent: r.c for r in rows}


def perm_counts():
    placeholders = ",".join(["%s"] * len(PRODUCTIX_DOCTYPES))
    rows = frappe.db.sql(
        "SELECT parent, COUNT(*) AS c FROM `tabDocPerm` WHERE parent IN (%s) "
        "GROUP BY parent" % placeholders,
        PRODUCTIX_DOCTYPES,
        as_dict=True,
    )
    return {r.parent: r.c for r in rows}


# --- standalone bootstrap (same pattern as scripts/_repair_c_installed_apps.py) ---
sys.path.insert(0, "/home/frappe/frappe-bench/apps")
sys.path.insert(0, "/home/frappe/frappe-bench/env/lib/python3.11/site-packages")

import frappe  # noqa: E402

log_dir = os.path.join(SITES_PATH, SITE, "logs")
os.makedirs(log_dir, exist_ok=True)
frappe.init(site=SITE, sites_path=SITES_PATH)
frappe.connect()
frappe.set_user("Administrator")

print("=== BEFORE ===")
before_fields = field_counts()
before_perms = perm_counts()
for dt in PRODUCTIX_DOCTYPES:
    print(f"  {dt}: fields={before_fields.get(dt, 0)} perms={before_perms.get(dt, 0)}")

from frappe.model.sync import sync_for  # noqa: E402

errors = []
for app in APPS:
    try:
        sync_for(app, force=1)
        print(f"sync_for({app!r}, force=1) OK")
    except Exception:
        import traceback

        errors.append(app)
        print(f"sync_for({app!r}) FAILED:")
        print(traceback.format_exc())

frappe.clear_cache()
frappe.db.commit()

print("=== AFTER ===")
after_fields = field_counts()
after_perms = perm_counts()
meta = frappe.get_meta("Productix Settings")
print(f"META Productix Settings fields={len(meta.fields)} "
      f"names={[f.fieldname for f in meta.fields]}")
changed = False
for dt in PRODUCTIX_DOCTYPES:
    b, a = before_fields.get(dt, 0), after_fields.get(dt, 0)
    pb, pa = before_perms.get(dt, 0), after_perms.get(dt, 0)
    marker = " <-- FIXED" if (b == 0 and a > 0) else ""
    if a != b or pa != pb:
        changed = True
    print(f"  {dt}: fields {b}->{a} perms {pb}->{pa}{marker}")

ent = frappe.db.sql(
    "SELECT module_key, enabled FROM `tabProductix Module Entitlement` ORDER BY module_key",
    as_dict=True,
)
print("ENTITLEMENTS:", [(r.module_key, r.enabled) for r in ent])

print("REPAIR_ERRORS:", errors)
print("REPAIR_DONE_OK" if not errors and after_fields.get("Productix Settings") else "REPAIR_DONE_WITH_ISSUES")
frappe.db.commit()
frappe.destroy()
