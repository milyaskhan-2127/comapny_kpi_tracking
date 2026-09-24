# Module Lifecycle

This document describes how a productix module moves through its life and what
automatic behavior the platform provides at each stage.

## 1. Lifecycle stages

```
created ──► installed ──► enabled ──► disabled ──► uninstalled
                  ▲            │  ▲        │
                  └────────────┴──┴────────┘   (re-install / re-enable anytime)
```

### created (development)

A new app ships `productix_module.json` + `modules.txt` + owned doctypes. The
static validators (`scripts/validate_modules.py`, `validate_dependencies.py`)
must pass. No runtime effect yet.

### installed

`bench --site <site> install-app <app>`:

1. Frappe syncs the app's doctypes (module from the app's owned Module Defs).
2. `hooks.py → after_install` runs → delegates to
   `productix_core.install.after_install` (idempotent): ensures **Productix
   Settings** exists and re-owns legacy Module Def rows (migration-aware).
3. The app's `after_uninstall` → `invalidate_registry_cache()` so the shared
   Redis registry + entitlement caches refresh on next request.

Effect on the registry: `get_registry()` (shared-Redis cached) now includes
the new `module_key`; on the next Productix Settings save
(`validate → sync_module_entitlements`) an entitlement row is auto-appended
**enabled**. `frappe.boot.productix_modules` grows accordingly.

### enabled (default)

All installed modules are enabled by default. Enforcement:

- API gate: `before_request → gate_request` returns **403** for disabled apps.
- Scheduled tasks / entry points call `require_module("<key>")`.
- Boot payload lists enabled keys for the UI.

### disabled (runtime)

Productix Settings → *Productix Module Entitlement* → untick the module:

- Immediately effective: `on_update` invalidates the per-request cache.
- Server-side API calls into the app return 403.
- Scheduled-task entry points raise a clear `PermissionError` (logged, no
  data corruption).
- UI: the app's JS keys disappear from `frappe.boot.productix_modules`.
- Data is **never deleted** by disabling.

Re-enabling is the reverse; nothing is re-migrated (no patches re-run for a
re-enable).

### uninstalled

`bench --site <site> uninstall-app <app>`:

- Frappe drops owned doctypes/tables (standard uninstall behavior — takes a
  backup decision first, see `rollback.md`).
- `after_uninstall` invalidates registry/entitlement caches so the module
  disappears from boot and from Productix Settings' sync list.
- If re-installed later, `install-app` runs `after_install` again (idempotent)
  and entitlement rows are re-created on next settings sync.

## 2. Platform invariants (core is special)

- `productix_core` is **always enabled**; it cannot be disabled from the
  settings UI (code forces `core` on even if a row were toggled off).
- `productix_core` has no `requires` beyond `erpnext`.
- Uninstalling `productix_core` while feature apps are installed is a
  configuration error — `required_apps` in feature apps prevents it during
  install; operators must uninstall features first.

## 3. Failure semantics

| Event                                | Behavior                                        |
|--------------------------------------|-------------------------------------------------|
| Registry JSON missing/broken          | App skipped from registry; logged at debug.     |
| Productix Settings missing (first boot) | Entitlement defaults to all-enabled.          |
| Gate fails to parse path              | Request passes through (fail-open, logged).     |
| Entitlement settings missing rows     | `sync_module_entitlements()` auto-appends.      |