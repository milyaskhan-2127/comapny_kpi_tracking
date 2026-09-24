# -*- coding: utf-8 -*-
"""
Productix Core — Migration 0001: re-own legacy Module Def rows.

When migrating an existing site from the retired monolithic `productix` app to
the modular apps, the `tabModule Def` rows created by the old app still carry
``app_name = "productix"``. Installing the new apps re-owns the modules that
still exist in their ``modules.txt`` (Recipe Management, KPI Tracking, ...),
but any leftover rows — most notably the legacy empty ``Alerts`` module — would
otherwise dangle. This patch:

1. Re-owns every Module Def row with ``app_name = 'productix'`` to the modular
   app that now ships that module. Owners are discovered by scanning the bench
   for apps shipping ``productix_module.json`` and reading each one's
   ``modules.txt`` — there is **no hard-coded app list**, so a future
   `productix_manufacturing` app is handled without touching this file.
2. Ensures the legacy ``Alerts`` module (which no new app ships in
   ``modules.txt``) keeps a valid Module Def owned by the platform app (the
   manifest flagged ``always_enabled``) when any record still references it.

The apps directory is derived from this module's own package location — never
a hard-coded ``/home/frappe/...`` path (deployment portability).
"""
import json
import os

import frappe

RETIRED_APP = "productix"
LEGACY_EMPTY_MODULES = ("Alerts",)


def _own_app():
    """The app this migration ships in (productix_core) — derived, not assumed."""
    return __package__.split(".", 1)[0]


def _apps_dir():
    """Directory holding all bench apps, derived from this package's location."""
    # frappe.get_app_path(<app>) -> <apps_dir>/<app>/<app>
    return os.path.dirname(os.path.dirname(frappe.get_app_path(_own_app())))


def _manifest_path(app):
    return os.path.join(_apps_dir(), app, app, "productix_module.json")


def _discover_modular_apps():
    """Apps on this bench that ship a productix_module.json (bench-wide scan).

    The retired monolithic `productix` app ships no manifest, so it is
    excluded automatically; future modular apps are included automatically.
    """
    apps = []
    try:
        entries = sorted(os.listdir(_apps_dir()))
    except OSError:
        frappe.logger().warning("Could not list apps directory", exc_info=True)
        return apps
    for entry in entries:
        if entry == RETIRED_APP:
            continue
        if os.path.isfile(_manifest_path(entry)):
            apps.append(entry)
    return apps


def _platform_app(default):
    """App whose manifest is flagged ``always_enabled`` (the platform owner)."""
    for app in _discover_modular_apps():
        try:
            with open(_manifest_path(app), encoding="utf-8") as f:
                if json.load(f).get("always_enabled"):
                    return app
        except (OSError, ValueError):
            continue
    return default


def _module_owner_map():
    """Map module_name -> owning app, derived from each modular app's modules.txt."""
    owners = {}
    for app in _discover_modular_apps():
        modules_file = os.path.join(_apps_dir(), app, app, "modules.txt")
        try:
            with open(modules_file, encoding="utf-8") as f:
                for line in f:
                    module = line.strip()
                    if module and not module.startswith("#"):
                        if module in owners and owners[module] != app:
                            # scripts/validate_modules.py rejects duplicate
                            # module ownership statically; warn at runtime.
                            frappe.logger().warning(
                                f"Module {module!r} declared by both "
                                f"{owners[module]} and {app}"
                            )
                        owners[module] = app
        except OSError:
            frappe.logger().warning(f"Could not read modules.txt for {app}", exc_info=True)
    return owners


def execute():
    reown_legacy_module_defs()


def reown_legacy_module_defs():
    if not frappe.db.table_exists("Module Def"):
        return

    owners = _module_owner_map()
    fallback_owner = _platform_app(_own_app())

    updated = 0
    rows = frappe.db.sql(
        "SELECT name, module_name FROM `tabModule Def` WHERE app_name=%s",
        (RETIRED_APP,),
        as_dict=True,
    )
    for row in rows:
        new_owner = owners.get(row["module_name"], fallback_owner)
        if new_owner != RETIRED_APP:
            frappe.db.set_value("Module Def", row["name"], "app_name", new_owner)
            updated += 1
    if updated:
        frappe.db.commit()

    # Keep legacy empty modules valid if anything still references them.
    for module_name in LEGACY_EMPTY_MODULES:
        if frappe.db.exists("Module Def", module_name):
            frappe.db.set_value("Module Def", module_name, "app_name", fallback_owner)
            frappe.db.commit()
            continue
        if _module_still_referenced(module_name):
            try:
                frappe.get_doc({
                    "doctype": "Module Def",
                    "module_name": module_name,
                    "app_name": fallback_owner,
                }).insert(ignore_permissions=True)
                frappe.db.commit()
            except Exception:
                frappe.logger().warning(f"Could not preserve legacy Module Def {module_name}", exc_info=True)


def _module_still_referenced(module_name):
    for doctype in ("DocType", "Custom Field", "Property Setter", "Workspace", "Report", "Page", "Number Card"):
        try:
            if frappe.db.table_exists(doctype) and frappe.db.exists(doctype, {"module": module_name}):
                return True
        except Exception:
            continue
    return False
