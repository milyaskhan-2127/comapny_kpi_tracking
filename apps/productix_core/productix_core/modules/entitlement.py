"""
Productix module entitlement — server-side enforcement.

Modules are enabled/disabled from Productix Settings → "Productix Module
Entitlement". The platform module (its manifest is flagged ``always_enabled``;
`core` today) is always enabled. Every other module defaults to enabled until
explicitly disabled.

Enforcement surfaces:

1. ``gate_request()`` — hooked into core hooks as ``before_request``. Any call
   to ``/api/method/<productix app>.…`` belonging to a disabled module is
   rejected with HTTP 403. Gating is registry-driven: only apps that resolve to
   a manifest can be gated, so legacy/unknown endpoints pass through.
2. ``require_module()`` — call at the top of scheduled-task entry points and
   other server-side entry points so background jobs for a disabled module
   are no-ops with a clear error.
3. ``is_module_enabled()`` — pure predicate for conditional logic and for the
   frontend boot payload (``frappe.boot.productix_modules``).
"""
import json
import os

import frappe

from productix_core.modules.registry import (
    ENTITLEMENT_CACHE_KEY,
    get_registry,
    module_key_for_app,
    platform_module_keys,
)

# Doctype names involved in entitlement (lazy-read; may not exist yet on first boot).
SETTINGS_DOCTYPE = "Productix Settings"


def _platform_module_keys():
    """Platform module keys, derived from each manifest's ``always_enabled`` flag.

    Resilience fallback: when the registry is unavailable (first-install window
    or an unreadable cache) read *this app's own* manifest directly so the
    platform can never lock itself out. The key still comes from the manifest —
    nothing is hard-coded.
    """
    try:
        keys = platform_module_keys()
    except Exception:
        keys = set()
    if keys:
        return keys
    try:
        own_app = __package__.split(".", 1)[0]  # "productix_core"
        manifest_path = os.path.join(frappe.get_app_path(own_app), "productix_module.json")
        with open(manifest_path, "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
        if manifest.get("always_enabled") and manifest.get("module_key"):
            return {manifest["module_key"]}
    except Exception:
        frappe.logger().debug("Could not read own productix_module.json", exc_info=True)
    return set()


def _settings_available():
    """Single doctypes have no `tab<doctype>` table (data lives in tabSingles),
    so `frappe.db.table_exists` is the wrong probe — check the DocType record."""
    try:
        return bool(frappe.db.exists("DocType", SETTINGS_DOCTYPE))
    except Exception:
        return False


def _default_entitlement_map():
    """Every installed module enabled; platform modules always on."""
    registry = get_registry()
    enabled = {key: True for key in registry}
    for key in _platform_module_keys():
        enabled[key] = True
    return enabled


def get_entitlement_map():
    """Return {module_key: enabled} from Productix Settings (per-request cached)."""
    if hasattr(frappe.local, "productix_entitlement_map"):
        return frappe.local.productix_entitlement_map

    enabled = _default_entitlement_map()
    try:
        if _settings_available():
            settings = frappe.get_cached_doc(SETTINGS_DOCTYPE)
            for row in settings.get("module_entitlements") or []:
                row_key = row.get("module_key")
                # Ignore rows for modules no longer installed (ghost rows left
                # behind by an uninstall) — only registry keys are meaningful.
                if row_key and row_key in enabled:
                    enabled[row_key] = bool(row.get("enabled", 1))
        for key in _platform_module_keys():
            enabled[key] = True
    except Exception:
        # Settings not created yet (first boot / migration) — keep all-enabled.
        frappe.logger().debug("Productix entitlement defaulted to all-enabled", exc_info=True)

    frappe.local.productix_entitlement_map = enabled
    return enabled


def is_module_enabled(module_key):
    """True when the module is enabled/active on this site.

    - Platform modules (manifest ``always_enabled``) are always enabled.
    - An installed module is enabled unless explicitly disabled in settings.
    - A key with no registry entry (module not installed, or not a
      productix module) is **not enabled** here — ``gate_request()`` never
      reaches this branch for such apps because it only gates apps resolved
      from the registry, so this never 403s non-installed endpoints.
    """
    if module_key in _platform_module_keys():
        return True
    if module_key not in get_registry():
        # Not an installed productix module — not enabled on this site.
        return False
    return bool(get_entitlement_map().get(module_key, True))


def require_module(module_key):
    """
    Raise PermissionError when a module is disabled.

    Usage (documented standard pattern for scheduled tasks & entry points)::

        from productix_core.modules.entitlement import require_module
        require_module("recipe")
    """
    if not is_module_enabled(module_key):
        raise frappe.PermissionError(
            frappe._("Productix module '{0}' is disabled on this site.").format(module_key)
        )


def get_enabled_module_keys():
    """Sorted list of enabled productix module keys (for the boot payload)."""
    return sorted(
        key for key, enabled in get_entitlement_map().items() if enabled
    )


def invalidate_entitlement_cache():
    """Drop per-request and shared entitlement caches (used on settings save)."""
    if hasattr(frappe.local, "productix_entitlement_map"):
        del frappe.local.productix_entitlement_map
    try:
        from productix_core.modules.registry import _site_scoped

        # shared=True matches how get_entitlement_map reads/writes the key
        # (verbatim, no db| prefix) — see registry.invalidate_registry_cache.
        frappe.cache.delete_value(_site_scoped(ENTITLEMENT_CACHE_KEY), shared=True)
    except Exception:
        pass


@frappe.whitelist()
def set_entitlement(module_key, enabled):
    """Enable/disable a module entitlement row (used by ops/acceptance tests)."""
    if module_key in _platform_module_keys():
        frappe.throw(
            frappe._("The platform module '{0}' can never be disabled.").format(module_key),
            frappe.ValidationError,
        )
    if module_key not in get_registry():
        frappe.throw(
            frappe._("Module '{0}' is not installed on this site.").format(module_key),
            frappe.ValidationError,
        )
    if not _settings_available():
        return {"module_key": module_key, "enabled": bool(enabled)}

    settings = frappe.get_doc(SETTINGS_DOCTYPE)
    found = False
    for row in settings.get("module_entitlements") or []:
        if row.module_key == module_key:
            row.enabled = 1 if enabled else 0
            found = True
    if not found:
        info = get_registry().get(module_key) or {}
        settings.append(
            "module_entitlements",
            {
                "module_key": module_key,
                "module_name": info.get("title") or info.get("module_name") or module_key,
                "enabled": 1 if enabled else 0,
            },
        )
    settings.save(ignore_permissions=True)
    frappe.db.commit()
    return {"module_key": module_key, "enabled": bool(enabled)}


@frappe.whitelist()
def reload_registry():
    """Drop registry + entitlement caches and re-sync settings rows (admin action)."""
    from productix_core.modules.registry import get_registry, invalidate_registry_cache

    invalidate_registry_cache()
    get_registry()
    try:
        if _settings_available() and frappe.db.exists(
            SETTINGS_DOCTYPE, SETTINGS_DOCTYPE
        ):
            settings = frappe.get_doc(SETTINGS_DOCTYPE)
            settings.sync_module_entitlements()
            settings.save(ignore_permissions=True)
    except Exception:
        frappe.logger().debug("reload_registry: settings sync skipped", exc_info=True)
    return {"status": "ok", "modules": sorted(get_registry().keys())}


def gate_request():
    """
    before_request hook — reject API calls into disabled productix modules.

    Matches /api/method/<app>.<rest>, resolves <app> to its module key via the
    registry (manifest-driven — no app list), and returns HTTP 403 when that
    module is disabled. Apps the registry does not resolve (frappe, erpnext,
    the retired monolithic `productix`, third-party apps) pass untouched, and
    platform modules are always enabled — so only genuinely disabled productix
    modules are ever blocked.
    """
    try:
        request = frappe.local.request
        if request is None:
            return
        path = frappe.utils.cstr(request.path).split("?", 1)[0]
    except Exception:
        return  # CLI / scheduler / no request context

    prefix = "/api/method/"
    if not path.startswith(prefix):
        return

    dotted = path[len(prefix):]
    if not dotted:
        return

    app = dotted.split(".", 1)[0]
    module_key = module_key_for_app(app)
    if not module_key:
        return  # not a registry-resolved productix app — never gated

    if not is_module_enabled(module_key):
        frappe.local.response["http_status_code"] = 403
        frappe.throw(
            frappe._("Productix module '{0}' is disabled on this site.").format(module_key),
            frappe.PermissionError,
        )
