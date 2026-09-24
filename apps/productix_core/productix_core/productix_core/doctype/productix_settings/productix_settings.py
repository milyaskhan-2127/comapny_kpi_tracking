import frappe
from frappe.model.document import Document


class ProductixSettings(Document):
    """Central Productix platform settings — licensing flags and module entitlements."""

    def validate(self):
        self.sync_module_entitlements()

    def on_update(self):
        # Entitlement map is per-request cached; clear shared/per-request copies
        # so the next request picks up the new configuration immediately.
        from productix_core.modules.entitlement import invalidate_entitlement_cache

        invalidate_entitlement_cache()

    def sync_module_entitlements(self):
        """
        Ensure every installed productix module has an entitlement row.

        New modules are appended enabled; existing rows (including disabled
        ones) are never overwritten, so admins can disable modules and the
        choice survives subsequent saves/installs. Rows for modules that are
        no longer installed (uninstall leftovers) are pruned.
        """
        try:
            from productix_core.modules.registry import get_registry
        except Exception:
            return
        registry = get_registry()

        # Prune ghost rows whose module is no longer installed.
        ghosts = [
            row for row in (self.get("module_entitlements") or [])
            if row.get("module_key") and row.module_key not in registry
        ]
        for ghost in ghosts:
            self.remove(ghost)

        existing = {row.module_key for row in (self.get("module_entitlements") or [])}
        for key in sorted(registry.keys()):
            if key not in existing:
                info = get_registry().get(key) or {}
                self.append("module_entitlements", {
                    "module_key": key,
                    "module_name": info.get("title") or info.get("module_name") or key,
                    "enabled": 1,
                })