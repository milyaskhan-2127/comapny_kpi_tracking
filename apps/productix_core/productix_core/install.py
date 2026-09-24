"""
Productix Core after_install provisioning.
"""
import frappe


def after_install():
    """Provision platform singletons and re-own legacy module metadata."""
    # Invalidate stale registry/entitlement caches FIRST: the registry cache is
    # shared redis (site-scoped key), so an entry populated before this app was
    # installed would otherwise make sync_module_entitlements miss it.
    _invalidate_module_caches()
    _ensure_productix_settings()
    _repoint_legacy_module_defs()
    _invalidate_module_caches()


def after_uninstall():
    """Post-uninstall cleanup: drop stale caches and ghost entitlement rows."""
    _invalidate_module_caches()
    _prune_entitlement_rows()


def _prune_entitlement_rows():
    """Save Productix Settings so validate() -> sync_module_entitlements drops
    rows whose module is no longer installed."""
    try:
        if not frappe.db.exists("DocType", "Productix Settings"):
            return
        if not frappe.db.exists("Productix Settings", "Productix Settings"):
            return
        settings = frappe.get_doc("Productix Settings")
        settings.save(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        frappe.logger().warning("Could not prune Productix Settings entitlement rows", exc_info=True)


def _ensure_productix_settings():
    """Create the Productix Settings single (and seed entitlement rows)."""
    try:
        if not frappe.db.exists("DocType", "Productix Settings"):
            return
        if frappe.db.exists("Productix Settings", "Productix Settings"):
            # Sync any entitlement rows added by later-installed apps.
            settings = frappe.get_doc("Productix Settings")
            settings.save(ignore_permissions=True)
            frappe.db.commit()
            return
        settings = frappe.get_doc({"doctype": "Productix Settings"})
        settings.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        frappe.logger().warning("Could not provision Productix Settings", exc_info=True)


def _repoint_legacy_module_defs():
    """
    Re-own Module Def rows left behind by the retired monolithic `productix`
    app so no orphan Module Defs remain after migration.
    """
    from productix_core.migrations.productix.repoint_module_defs import (
        reown_legacy_module_defs,
    )

    try:
        reown_legacy_module_defs()
    except Exception:
        frappe.logger().warning("Could not reown legacy Module Def rows", exc_info=True)


def _invalidate_module_caches():
    from productix_core.modules.registry import invalidate_registry_cache

    invalidate_registry_cache()