#!/usr/bin/env python3
"""
migration_check.py — health checks for migrating an existing monolithic
`productix` database to the modular productix apps.

Designed to run inside a bench site context (Frappe v15). This frappe
version's `bench execute` evals dotted paths without importing them, so
`scripts.*` targets do not resolve there — run the file directly:

    docker compose exec backend bash -c "cd /home/frappe/frappe-bench && \
      env/bin/python scripts/migration_check.py <site>"

(or from a connected `bench --site <site> console`: `from scripts import
migration_check; migration_check.main()`). Exit code 0 = healthy, 1 = issues.

Checks — everything discovered dynamically, no hard-coded app/module lists:
  * Architecture: legacy `productix` and modular apps must never be
    co-installed on one site (co_install_issue)
  * Module Def rows — ownership by app (legacy 'productix' vs discovered
    modular apps)
  * Retired modules — legacy app's modules.txt (plus any Module Def rows
    still owned by legacy) minus modules still shipped by an installed
    modular app; custom fields on retired modules are flagged
  * Custom Fields / DocType rows — counts per productix module (report)
  * Core readiness — Productix Settings / module registry tables exist
  * Registry vs entitlement — installed modules vs Productix Settings rows

Exit code 0 = healthy, 1 = issues found.
"""
import json
import os
import sys

RETIRED_APP = "productix"
MANIFEST_NAME = "productix_module.json"
APP_PREFIX = "productix_"


# --------------------------------------------------------------------------
# pure helpers (no frappe — unit-testable anywhere)
# --------------------------------------------------------------------------
def co_install_issue(installed_apps, modular_apps):
    """Legacy + any modular app installed on the same site -> issue string.

    The two architectures are mutually exclusive (their hooks collide);
    `modular_apps` may be a bench-wide list — only the installed intersection
    counts. Returns None when the combination is acceptable.
    """
    installed = set(installed_apps or ())
    modular_installed = sorted(set(modular_apps or ()) & installed)
    if RETIRED_APP in installed and modular_installed:
        return (
            f"legacy '{RETIRED_APP}' co-installed with modular app(s) "
            f"{modular_installed} — the architectures are mutually exclusive; "
            f"retire the legacy app (see docs/migration.md)"
        )
    return None


def retired_modules(legacy_modules, owned_modules):
    """Modules retired from the architecture: legacy − still-owned (sorted)."""
    return sorted(set(legacy_modules or ()) - set(owned_modules or ()))


# --------------------------------------------------------------------------
# frappe-side discovery helpers
# --------------------------------------------------------------------------
def _manifest_path(app):
    """Manifest path for an app, resolved from frappe's own app resolution."""
    import frappe
    return os.path.join(frappe.get_app_path(app), MANIFEST_NAME)


def _discovered_modular_apps(installed_only=False):
    """Apps shipping a productix manifest. Defaults to installed apps only.

    Source of truth: `productix_module.json` presence — identical to the
    runtime registry (productix_core.modules.registry).
    """
    import frappe
    apps = []
    for app in frappe.get_installed_apps() if installed_only else _bench_apps():
        if app == RETIRED_APP or not app.startswith(APP_PREFIX):
            continue
        if os.path.isfile(_manifest_path(app)):
            apps.append(app)
        elif installed_only:
            # an installed productix_* app without a manifest = broken tree
            frappe.logger().warning(f"Installed app {app} ships no {MANIFEST_NAME}")
    return sorted(apps)


def _bench_apps():
    """Apps dir entries (bench root derived from this file — portable)."""
    import frappe
    apps_dir = os.path.dirname(os.path.dirname(frappe.get_app_path("frappe")))
    try:
        return sorted(os.listdir(apps_dir))
    except OSError:
        return []


def _modules_of(app):
    """modules.txt of an app (empty set if unreadable)."""
    import frappe
    path = os.path.join(frappe.get_app_path(app), "modules.txt")
    modules = set()
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    modules.add(line)
    except OSError:
        frappe.logger().warning(f"Could not read modules.txt for {app}", exc_info=True)
    return modules


def _legacy_modules():
    """Modules the legacy app shipped — from its modules.txt when readable."""
    import frappe
    if RETIRED_APP not in _bench_apps():
        return set()
    try:
        return _modules_of(RETIRED_APP)
    except Exception:
        return set()


# --------------------------------------------------------------------------
# checks
# --------------------------------------------------------------------------
def _table_exists(name):
    """frappe.db.table_exists(doctype) checks `tab<doctype>` — pass the DOCTYPE."""
    import frappe
    return frappe.db.table_exists(name)


def check_architecture(issues, report, installed, modular):
    report["installed_apps"] = list(installed)
    report["modular_apps_on_bench"] = list(modular)
    issue = co_install_issue(installed, modular)
    if issue:
        issues.append(issue)
    productix_like = [a for a in installed if a == RETIRED_APP or a.startswith(APP_PREFIX)]
    report["productix_architecture"] = "legacy" if productix_like == [RETIRED_APP] else (
        "modular" if RETIRED_APP not in productix_like else "MIXED"
    )


def check_module_defs(issues, report, installed, modular, owned, retired):
    import frappe
    if not _table_exists("Module Def"):
        report["module_def"] = "tabModule Def table missing"
        issues.append("tabModule Def table missing")
        return
    watched = sorted({RETIRED_APP} | set(modular))
    rows = frappe.db.sql(
        "SELECT name, app_name AS app FROM `tabModule Def` "
        "WHERE app_name IN %s ORDER BY name",
        (watched,),
        as_dict=True,
    )
    by_app = {}
    for r in rows:
        by_app.setdefault(r["app"], []).append(r["name"])
    report["module_def_by_app"] = by_app
    legacy = by_app.get(RETIRED_APP, [])
    if legacy:
        report["legacy_productix_modules"] = legacy
        issues.append(
            f"{len(legacy)} Module Def row(s) still owned by legacy "
            f"'{RETIRED_APP}' — run repoint_module_defs"
        )


def check_custom_fields(issues, report, owned, retired):
    import frappe
    if not _table_exists("Custom Field"):
        report["custom_fields"] = "tabCustom Field missing"
        return
    modules = sorted(set(owned) | set(retired))
    if not modules:
        report["custom_fields_by_module"] = {}
        return
    rows = frappe.db.sql(
        "SELECT module, COUNT(*) AS cnt FROM `tabCustom Field` "
        "WHERE module IN %s GROUP BY module ORDER BY module",
        (modules,),
        as_dict=True,
    )
    report["custom_fields_by_module"] = {r["module"]: r["cnt"] for r in rows}
    unexpected = {
        r["module"]: r["cnt"] for r in rows if r["module"] in set(retired)
    }
    if unexpected:
        issues.append(
            f"custom fields still reference retired module(s) {unexpected} "
            f"(expected re-mapped to a current module)"
        )


def check_doctype_ownership(issues, report, owned, retired):
    import frappe
    if not _table_exists("DocType"):
        return
    modules = sorted(set(owned) | set(retired))
    if not modules:
        report["doctype_count_by_module"] = {}
        return
    rows = frappe.db.sql(
        "SELECT module, COUNT(*) AS cnt FROM `tabDocType` "
        "WHERE module IN %s GROUP BY module ORDER BY module",
        (modules,),
        as_dict=True,
    )
    report["doctype_count_by_module"] = {r["module"]: r["cnt"] for r in rows}


def check_core_readiness(issues, report, installed):
    import frappe
    # Productix Settings is a Single doctype: its record lives in `tabSingles`
    # (frappe v15 does not create a dedicated table), so readiness = the DocType
    # row exists + the seeded single record exists + the child table is present.
    has_core = "productix_core" in installed
    report["core_installed"] = has_core
    if not has_core:
        return
    settings_doctype = bool(
        _table_exists("DocType")
        and frappe.db.exists("DocType", {"name": "Productix Settings", "custom": 0})
    )
    settings_record = bool(
        settings_doctype and frappe.db.exists("Productix Settings", "Productix Settings")
    )
    ready = {
        "Productix Settings doctype": settings_doctype,
        "Productix Settings record": settings_record,
        "tabProductix Module Entitlement": _table_exists("Productix Module Entitlement"),
        "tabAI Agent Log": _table_exists("AI Agent Log"),
    }
    report["core_tables"] = ready
    if not settings_doctype:
        issues.append("Productix Settings doctype not installed — install productix_core first")
    elif not settings_record:
        issues.append("Productix Settings single record missing — run bench migrate / save settings")


def check_registry_vs_entitlement(issues, report, modular_installed):
    import frappe
    registry = {}
    for app in modular_installed:
        p = _manifest_path(app)
        try:
            with open(p, encoding="utf-8") as f:
                registry[app] = json.load(f)
        except (OSError, ValueError) as exc:
            issues.append(f"unreadable manifest for {app}: {exc}")
    report["registry"] = {k: v.get("module_key") for k, v in registry.items()}
    if not _table_exists("Productix Module Entitlement"):
        issues.append("Productix Module Entitlement missing — Productix Settings not synced")
        return
    rows = frappe.get_all(
        "Productix Module Entitlement", fields=["module_key", "module_name", "enabled"]
    )
    report["entitlement_rows"] = rows
    reg_keys = {v.get("module_key") for v in registry.values()}
    ent_keys = {r["module_key"] for r in rows}
    if reg_keys - ent_keys:
        issues.append(
            f"registry modules missing from entitlement: {sorted(reg_keys - ent_keys)} — save Productix Settings to auto-sync"
        )
    stale = ent_keys - reg_keys
    if stale:
        report["stale_entitlement_rows"] = sorted(stale)


def main(site=None):
    import frappe

    target = site or (frappe.local.site if hasattr(frappe, "local") and frappe.local.site else None)
    already = getattr(frappe.local, "db", None) and getattr(frappe.local, "site", None)
    if target and not (already and frappe.local.site == target):
        # Standalone invocation (this frappe version's `bench execute` evals
        # dotted paths without importing them, so scripts.* targets do not
        # resolve there — run this file directly instead):
        #   cd <bench-root> && env/bin/python scripts/migration_check.py <site>
        # sites_path must be explicit: a bare frappe.init(site=...) from an
        # arbitrary cwd raises IncorrectSitePath.
        sites_path = None
        cwd_sites = os.path.abspath("sites")
        if os.path.isdir(cwd_sites):
            sites_path = cwd_sites
        else:
            try:
                from frappe.utils import get_bench_path

                sites_path = os.path.join(get_bench_path(), "sites")
            except Exception:
                sites_path = None
        # raw python lacks the per-site log dirs frappe's file handlers need
        if sites_path:
            os.makedirs(os.path.join(sites_path, target, "logs"), exist_ok=True)
        if sites_path:
            frappe.init(site=target, sites_path=sites_path)
        else:
            frappe.init(site=target)
        frappe.connect()
        frappe.set_user("Administrator")
    elif not target:
        # assume already connected via bench console / execute
        raise SystemExit(
            "migration_check: no site context — pass the site as argv[1]"
        )

    issues = []
    report = {"site": getattr(frappe.local, "site", None) or "current"}

    installed = list(frappe.get_installed_apps())
    modular_bench = _discovered_modular_apps(installed_only=False)
    modular_installed = _discovered_modular_apps(installed_only=True)

    # ownership universe: every module still shipped + every retired module
    owned = set()
    for app in modular_installed:
        owned |= _modules_of(app)
    legacy = _legacy_modules()
    legacy_rows = set()
    if _table_exists("Module Def"):
        legacy_rows = {
            r["module_name"]
            for r in frappe.db.sql(
                "SELECT module_name FROM `tabModule Def` WHERE app_name=%s",
                (RETIRED_APP,),
                as_dict=True,
            )
        }
    retired = retired_modules(legacy | legacy_rows, owned)
    report["owned_modules"] = sorted(owned)
    report["retired_modules"] = retired

    check_architecture(issues, report, installed, modular_bench)
    check_module_defs(issues, report, installed, modular_bench, owned, retired)
    check_custom_fields(issues, report, owned, retired)
    check_doctype_ownership(issues, report, owned, retired)
    check_core_readiness(issues, report, installed)
    check_registry_vs_entitlement(issues, report, modular_installed)

    print(json.dumps(report, indent=2, default=str))
    if issues:
        print("ISSUES:")
        for i in issues:
            print("  - " + i)
        print(f"MIGRATION_CHECK = {len(issues)} issue(s)")
        return 1
    print("MIGRATION_CHECK_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(site=sys.argv[1] if len(sys.argv) > 1 else None))
