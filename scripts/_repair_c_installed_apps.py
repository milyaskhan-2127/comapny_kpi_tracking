#!/usr/bin/env python3
"""
scripts/_repair_c_installed_apps.py — environment repair for productix-c.local.

Background (see tests/ACCEPTANCE_EVIDENCE.md): site C was re-seeded from the
legacy baseline dump (Sep 23 23:32) but its site-scoped Redis `defaults` hash
survived the restore holding the PRE-restore modular `installed_apps` value.
Subsequent `install-app --force` runs therefore read the stale cached list and
`add_to_installed_apps`' conditional write (`if app_name not in installed_apps`)
was silently skipped, while every unconditional write (Module Def sync, Patch
Log, entitlements) landed. Net result: modular metadata installed, but
`tabDefaultValue.installed_apps` still showed the legacy snapshot.

Repair = clear the stale cache, then run frappe's OWN install bookkeeping
APIs in order (remove legacy -> add the four modular apps), verifying the
final row. No data is touched; only the installed-apps bookkeeping row
(and the Installed Applications single) is updated.

Run:
    cd /home/frappe/frappe-bench && \
      env/bin/python scripts/_repair_c_installed_apps.py productix-c.local
"""
import json

import frappe

MODULAR = [
    "productix_core",
    "productix_recipe",
    "productix_kpi",
    "productix_instruction",
]
LEGACY_APP = "productix"
TARGET = ["frappe", "erpnext"] + MODULAR


def _row():
    return frappe.db.get_value(
        "DefaultValue",
        {"defkey": "installed_apps"},
        ["defvalue", "modified"],
        as_dict=True,
    )


def main():
    from frappe.installer import (
        add_to_installed_apps,
        remove_from_installed_apps,
    )

    # 1. Flush the stale site-scoped `defaults` cache FIRST — otherwise the
    #    official APIs below would read the stale list and no-op.
    frappe.clear_cache()
    print("BEFORE row   :", _row())
    print("BEFORE api   :", frappe.get_installed_apps())

    # 2. Remove the legacy app via frappe's own API (unconditional set_value
    #    path; bench uninstall-app must NOT be used on the legacy app here
    #    because its uninstall hooks are not part of the migration contract).
    if LEGACY_APP in frappe.get_installed_apps():
        remove_from_installed_apps(LEGACY_APP)
        print("removed      :", LEGACY_APP)

    # 3. Add the four modular apps via frappe's own API. With the cache cold
    #    each call now reads the DB, sees the app missing, and performs the
    #    delete+reinsert of the installed_apps row.
    for app in MODULAR:
        add_to_installed_apps(app)
        print("added        :", app, "->", frappe.get_installed_apps())

    # 4. Belt & braces: if any API call no-op'd for an unforeseen reason,
    #    write the row directly through the same mechanism remove_from uses.
    final = frappe.get_installed_apps()
    if final != TARGET:
        print("FALLBACK direct set_value; api saw:", final)
        frappe.db.set_value(
            "DefaultValue",
            {"defkey": "installed_apps"},
            "defvalue",
            json.dumps(TARGET),
        )
        frappe.get_single("Installed Applications").update_versions()
        frappe.db.commit()
        frappe.clear_cache()
        final = frappe.get_installed_apps()

    print("AFTER row    :", _row())
    print("AFTER api    :", final)
    assert final == TARGET, f"repair failed: {final} != {TARGET}"

    # 5. Flush the productix shared-namespace caches (frappe.clear_cache()
    #    does not touch them) so the registry/entitlement re-read the new
    #    installed-apps state on the next request.
    try:
        from productix_core.modules.entitlement import invalidate_entitlement_cache
        from productix_core.modules.registry import invalidate_registry_cache

        invalidate_registry_cache()
        invalidate_entitlement_cache()
        print("invalidated  : registry + entitlement caches")
    except Exception as exc:  # pragma: no cover - diagnostic output
        print("cache invalidation failed:", exc)
        raise

    from productix_core.modules.registry import get_registry

    print("REGISTRY     :", sorted(get_registry().keys()))
    print("REPAIR_OK")


if __name__ == "__main__":
    import sys

    # Standalone bootstrap (this frappe version's `bench execute` evals the
    # dotted path without importing it, so scripts.* targets don't resolve):
    #   cd /home/frappe/frappe-bench && env/bin/python \
    #       scripts/_repair_c_installed_apps.py productix-c.local
    site = sys.argv[1]
    frappe.init(site=site, sites_path="/home/frappe/frappe-bench/sites")
    frappe.connect()
    frappe.set_user("Administrator")
    try:
        main()
    finally:
        frappe.destroy()
