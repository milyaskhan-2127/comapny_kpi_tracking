# Productix ERP — Architecture

## 1. What changed

The monolithic `productix` app (Recipe + KPI + Instruction + licensing +
alerts/audit in one package) was split into four independently installable
Frappe/ERPNext v15 apps:

| App                   | Module(s) owned                                  | Folder          |
|-----------------------|--------------------------------------------------|-----------------|
| `productix_core`      | `Productix Core`, `Subscription Management`      | `apps/productix_core` |
| `productix_recipe`    | `Recipe Management`                              | `apps/productix_recipe` |
| `productix_kpi`       | `KPI Tracking`                                   | `apps/productix_kpi` |
| `productix_instruction`| `Instruction Room`                              | `apps/productix_instruction` |

The legacy monolith was **retired** on 2026-09-24 after the 13-point coverage
audit (41/41 doctypes, APIs, hooks, fixtures, assets — see
`tests/ACCEPTANCE_EVIDENCE.md` §11): the `apps/productix` directory, its
compose `PYTHONPATH`/mount entries and all deploy-script references are gone
from the working tree. The full pre-retirement tree is preserved by git tag
`pre-legacy-retirement` (commit `fd6acb7`), which is the rollback point for
`docs/rollback.md` §5. All current code lives in the four apps; the retired
tree ships no `productix_module.json`, so it was never part of the module
registry.

## 2. Dependency rules

- Every app requires `erpnext` (Frappe is implicit).
- `productix_core` is the **platform**: it depends on nothing productix.
- Feature apps (`productix_recipe`, `productix_kpi`,
  `productix_instruction`, future apps) depend on `productix_core` **only** —
  never on each other.
- No new app may `import productix` (the legacy package). Enforced by
  `scripts/validate_dependencies.py`.
- Apps participate by **shipping a `productix_module.json` manifest** — the
  runtime registry, validators, `migration_check`, and setup/deploy scripts
  all discover modules from manifests (no hard-coded app lists anywhere).
- The legacy `productix` app and any modular `productix_*` app are
  **mutually exclusive per site** (never co-installed; `migration_check`
  enforces it).

`requires` in each `productix_module.json` records these app-level
dependencies and is checked by `scripts/validate_modules.py`.

## 3. Module registry & entitlement

### 3.1 Registry

Each app ships `productix_module.json`:

```json
{
  "app": "productix_recipe",
  "module_key": "recipe",
  "module_name": "Recipe Management",
  "title": "Recipe & Production",
  "description": "...",
  "requires": ["erpnext", "productix_core"],
  "version": "1.0.0"
}
```

`productix_core.modules.registry` (`get_registry`,
`module_key_for_app`, `module_key_for_module_name`,
`platform_module_keys`, `invalidate_registry_cache`) discovers every manifest
across installed apps — **manifest-driven, no hard-coded app list**, so a
future `productix_manufacturing` is recognised the moment it is installed
(without any Core change). The registry is cached in shared Redis under
`productix_module_registry` and re-read per request refresh.

### 3.2 Entitlement (Productix Settings)

`Productix Settings` (Single, module `Productix Core`) holds a child table
**Productix Module Entitlement** (`module_entitlements`): one row per
installed module (`module_key`, `module_name`, `enabled`, default 1).

- `validate()` → `sync_module_entitlements()` — auto-appends rows for any
  registry module that is missing a row (all installed modules start enabled).
- `on_update` → invalidates the per-request entitlement cache.
- The platform module (`core`) can never be disabled.
- A whitelisted `reload_registry()` method re-syncs rows and caches (wired to
  the Productix Settings UI button).

`productix_core.modules.entitlement` exposes:

| Call                     | Purpose                                            |
|--------------------------|----------------------------------------------------|
| `is_module_enabled(key)` | Predicate: True for `core` always, installed-and-enabled modules; False for disabled or not-installed modules. |
| `require_module(key)`    | Raise `PermissionError` if disabled (entry points).|
| `get_enabled_module_keys()` | Sorted enabled keys (boot payload, UI).        |
| `gate_request()`         | `before_request` hook, API 403 for disabled apps.  |
| `invalidate_entitlement_cache()` | Drop caches on settings save.            |

### 3.3 Server-side enforcement

- Core hooks register `before_request = …entitlement.gate_request`. Any call
  to `/api/method/<productix app>.…` for a disabled module returns **403**.
- Scheduled-task and whitelisted entry points call `require_module("<key>")`
  at the top (e.g. `productix_recipe.tasks`).
- There are **no scattered `if recipe:` checks** in the codebase; conditional
  behavior is driven by the registry/entitlement helpers (e.g. the AI Agent
  Log scan button is rendered only when
  `productix.is_module_enabled('recipe')`).

### 3.4 Frontend

- Core injects `frappe.boot.productix_modules` (enabled keys) via
  `boot_session`.
- Each app exposes its own methods under the shared `productix` namespace by
  `frappe.provide('productix')` + `Object.assign` — never overwriting the
  whole object.
- `productix_core` provides `productix.is_module_enabled(key)`.
- Frappe v15 runs **all** registered `boot_session` hooks (verified in
  `frappe/boot.py: get_bootinfo`), so core, recipe, and kpi each contribute
  their own slice.

## 4. Hooks ownership

| Concern                      | Owner            |
|------------------------------|------------------|
| Licensing / tenancy (`User` doc_events, `on_login`) | `productix_core` |
| `before_request` gate        | `productix_core` |
| Audit log (`AI Agent Log` doctype, module-level `log_event`) | `productix_core` |
| Shared email utils           | `productix_core` |
| Alerts scan tasks (`run_daily_inventory_scan`, `mark_expired_batches`) | `productix_recipe.tasks` |
| `trigger_manual_scan` API    | `productix_recipe.api.inventory` |
| Inventory API (`get_item_stock_info`, `get_dashboard_kpis`, …) | `productix_recipe.api.inventory` |
| Recipe docs permissions      | `productix_recipe` |
| KPI report sync + backups page provisioning (`boot_session`) | `productix_kpi` |
| Backups API                  | `productix_kpi.api.backup` |
| KPI permissions/query conditions | `productix_kpi` |
| Instruction Message whitelisted methods | `productix_instruction` |
| Ignore-links-on-delete       | owned by the app that owns the doctype |

## 5. API surface

All API paths changed from `productix.*` to app-scoped names:

- `productix_core.api.subscription.*`
- `productix_recipe.api.inventory.*`
- `productix_kpi.api.backup.*`
- `productix_kpi.kpi_tracking.api.*`
- `productix_instruction.instruction_room.doctype.instruction_message.*`

Old monolithic `productix.*` endpoints are **not** served by the new apps;
clients must be updated (or the migration path's old app stays installed until
retired).

## 6. Data model ownership

`tabModule Def` rows are re-owned to the new apps by
`productix_core.migrations.productix.repoint_module_defs` (runs on `migrate`
after installing `productix_core`). The empty legacy `Alerts` Module Def row
is preserved **only** when still referenced by records.

Fixtures were split per app (role / custom_field / workspace / report /
property_setter / number_card) — see `scripts/validate_modules.py` for the
ownership invariants and the app `fixtures/` folders.

## 7. Missing-module resilience

`setup_data.py` (recipe) guards Instruction Message and KPI-role seeding
behind table/doctype existence checks, so a `Core+Recipe` install never
fails because KPI/Instruction tables do not exist. Idempotent core
provisioning is delegated by every app's `after_install` to
`productix_core.install.after_install`.