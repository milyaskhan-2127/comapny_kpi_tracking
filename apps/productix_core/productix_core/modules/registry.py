"""
Productix module registry.

Each productix app ships a `productix_module.json` describing the module(s) it
provides (app, module_key, module_name, title, description, requires, version,
always_enabled). This module discovers those manifests across the installed
apps and exposes:

- ``get_registry()``              — {module_key: manifest} for installed apps
- ``module_key_for_app(app)``     — module key owning a Python package prefix
- ``module_key_for_module_name()``— reverse-lookup from Frappe module name
- ``platform_module_keys()``      — module keys flagged ``always_enabled``
- ``invalidate_registry_cache()`` — drop cached copies (call on install/uninstall)

Discovery is fully manifest-driven: any installed app that ships
``productix_module.json`` joins the registry. There is **no hard-coded app
list**, so a new productix app is recognised the moment it is installed — no
Core change required (see docs/module-development.md).

The platform app (its manifest is flagged ``always_enabled``; productix_core
today) is always implicitly enabled; every other module's enabled state is
governed by Productix Settings (see entitlement.py).
"""
import json
import os

import frappe

# Registry is per-site (depends on the site's installed apps), so the shared
# redis cache key must be site-scoped — a global key would let one combo's
# registry leak into another combo's site on the same bench.
REGISTRY_CACHE_KEY = "productix_module_registry"
ENTITLEMENT_CACHE_KEY = "productix_module_entitlement_map"


def _site_scoped(key):
    return f"{frappe.local.site}:{key}" if getattr(frappe.local, "site", None) else key


def _load_registry():
    """Read productix_module.json from every installed app that ships one.

    Manifest presence — not a hard-coded app list — is the only criterion for
    participating in the registry. Apps without a manifest (frappe, erpnext,
    the retired monolithic `productix`, third-party apps) are ignored, which is
    also why the request gate never touches them.
    """
    registry = {}
    for app in frappe.get_installed_apps():
        try:
            manifest_path = os.path.join(frappe.get_app_path(app), "productix_module.json")
        except Exception:
            # App not importable / no package path — cannot be a productix app.
            continue
        if not os.path.exists(manifest_path):
            continue
        try:
            with open(manifest_path, "r", encoding="utf-8") as fh:
                manifest = json.load(fh)
        except Exception:
            frappe.logger().debug(f"Could not load productix_module.json for {app}", exc_info=True)
            continue
        module_key = manifest.get("module_key")
        if not module_key:
            frappe.logger().warning(
                f"productix_module.json for {app} declares no module_key — skipped"
            )
            continue
        if manifest.get("app") != app:
            # Statically rejected by scripts/validate_modules.py; skip at runtime
            # so module_key_for_app() never resolves a mismatched app.
            frappe.logger().warning(
                f"productix_module.json for {app} declares app={manifest.get('app')!r} — skipped"
            )
            continue
        if module_key in registry:
            frappe.logger().warning(
                f"Duplicate productix module_key {module_key!r} "
                f"({registry[module_key].get('app')} vs {app}) — keeping the first"
            )
            continue
        registry[module_key] = manifest
    return registry


def get_registry():
    """Return {module_key: manifest} for installed productix apps (cached, per-site)."""
    if not hasattr(frappe.local, "productix_module_registry"):
        try:
            frappe.local.productix_module_registry = frappe.cache.get_value(
                _site_scoped(REGISTRY_CACHE_KEY), _load_registry, shared=True
            )
        except Exception:
            frappe.local.productix_module_registry = _load_registry()
    return frappe.local.productix_module_registry or {}


def get_module_info(module_key):
    """Return the manifest dict for a module key, or None."""
    return get_registry().get(module_key)


def module_key_for_app(app):
    """Return the module key whose app is `app`, or None."""
    registry = get_registry()
    for key, info in registry.items():
        if info.get("app") == app:
            return key
    return None


def module_key_for_module_name(module_name):
    """Reverse-lookup: map a Frappe Module Def name to a productix module key."""
    registry = get_registry()
    for key, info in registry.items():
        if info.get("module_name") == module_name:
            return key
    return None


def app_for_module_key(module_key):
    """Return the app name that owns the given module_key, or None."""
    info = get_module_info(module_key)
    return info.get("app") if info else None


def platform_module_keys():
    """Module keys whose manifest is flagged ``always_enabled`` (the platform).

    Derived from the manifests — there is no hard-coded platform key. Exactly
    one manifest may carry the flag (productix_core today); that invariant is
    enforced statically by ``scripts/validate_modules.py``.
    """
    return {key for key, info in get_registry().items() if info.get("always_enabled")}


def invalidate_registry_cache():
    """Drop cached registry + entitlement data so the next request re-reads them."""
    for key in (_site_scoped(REGISTRY_CACHE_KEY), _site_scoped(ENTITLEMENT_CACHE_KEY)):
        try:
            # Cache reads/writes use shared=True (verbatim key, no db| prefix), so
            # deletes must too — a site-prefixed delete would miss the real key.
            frappe.cache.delete_value(key, shared=True)
        except Exception:
            pass
    for attr in ("productix_module_registry", "productix_entitlement_map"):
        if hasattr(frappe.local, attr):
            delattr(frappe.local, attr)
