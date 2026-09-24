# Developing a Productix Module

This guide covers adding features to an existing module and — more importantly —
**how modules must stay decoupled** so the four-app modularity contract holds.

## 1. The contract

- `productix_core` = platform only (settings, licensing/tenant, registry,
  shared audit log, shared utils).
- Feature apps (`recipe`, `kpi`, `instruction`) depend **only** on
  `productix_core` (+ `erpnext`). They never import each other.
- Module→Core dependency is enforced by `scripts/validate_dependencies.py` in
  CI. Keep it green.
- **Discovery is generic everywhere**: the runtime registry, both validators,
  `migration_check`, and the setup/deploy scripts all find modules by reading
  `productix_module.json` manifests — there is no hard-coded app list
  anywhere. A new app (e.g. `productix_manufacturing`) joins the platform
  without editing Core, the validators, or the scripts.

## 2. Anatomy of a modular app

```
apps/<app_name>/<app_name>/
├── hooks.py                 # hook points owned by THIS app only
├── modules.txt              # Frappe Module Def names owned by this app
├── productix_module.json    # registry manifest (module_key, module_name, ...)
├── patches.txt              # migration patches (app.migrations.<name>)
├── install.py               # after_install/after_uninstall (delegate to core)
├── api/                     # whitelisted server methods, app-scoped paths
├── public/                  # JS/CSS; JS attaches methods to `productix.*`
└── <module>/doctype/...     # doctypes, all declaring a module this app owns
```

## 3. Registering a module (new app or new module)

1. Create `productix_module.json`:

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

   The manifest **is** the registration: the registry, entitlement, validators,
   and setup scripts all discover apps by its presence. (Only the platform
   app sets `"always_enabled": true`.)
2. Add the owned Module Def name(s) to `modules.txt`.
3. Every doctype JSON in the app must set `"module"` to one of those names
   (`scripts/validate_modules.py` enforces this — cross-app or orphan module
   declarations fail the build).
4. Ship `apps/<app>/setup.py` with the same `version=` (four-source version
   sync is enforced).

## 4. Wiring entry points that must respect enablement

Scheduled tasks, background jobs, webhook handlers, and any API that should
not run when the module is disabled start with:

```python
from productix_core.modules.entitlement import require_module

def run_daily_inventory_scan():
    require_module("recipe")
    ...
```

Server-side API methods in a disabled module are already rejected at the
request gate (`before_request` → `gate_request`, HTTP 403). Use
`is_module_enabled(key)` when a UI element or a cross-cutting service needs a
predicate (e.g. core's AI Agent Log scan button):

```js
if (frappe.boot.productix_modules.includes('recipe')) { /* render button */ }
```

## 5. Frontend rules

- Always `frappe.provide('productix')` then merge:

  ```js
  frappe.provide('productix');
  Object.assign(productix, {
      my_method: function() { ... }
  });
  ```

  Never assign `productix = ...` (that would clobber another app's methods).
- API calls use the app-scoped dotted path, e.g.
  `frappe.call({ method: 'productix_recipe.api.inventory.…' })`.
- Add your app to `boot_session` (Frappe runs every registered hook) when you
  need boot-time data; read `frappe.boot.productix_modules` to know what is
  enabled on this site.

## 6. Hooks ownership rules

- `doc_events`, `scheduler_events`, `fixtures`, `has_permission`,
  `permission_query_conditions`, `doctype_js`, `ignore_links_on_delete` —
  each app declares hooks only for doctypes **it owns**.
- Shared/platform behavior lives in `productix_core` (User doc events,
  ignition, license check, request gate, shared audit log).

## 7. Fixtures

`bench export-fixtures` honors each app's `fixtures` list in `hooks.py`.
Import fixtures with `bench --site <site> import-fixtures`. Records are
upserted by `name`, so keep `name`/module fields stable per app (the split
fixtures already do).

## 8. Versioning rules

See `versioning.md` — bump the app version in **four** places together:
`__init__.py` (`__version__`), `hooks.py` (`app_version`),
`productix_module.json` (`version`), and `apps/<app>/setup.py` (`version=`).
`scripts/validate_modules.py` fails on any mismatch. Keep the compat matrix
in `versioning.md` up to date. Versions are independent per app.

## 9. Common pitfalls

| Pitfall                                   | Fix                                              |
|-------------------------------------------|--------------------------------------------------|
| Importing `productix.*` (legacy)          | Re-point to the owning new app.                  |
| Importing a sibling feature app           | Push shared behavior into `productix_core`.      |
| Hard-coding a site name / customer        | Parameterize (env / settings), never hard-code.  |
| White-labeling boot with a whole-object JS overwrite | Use `Object.assign`.             |
| Chain-breaking `if recipe:` checks        | Use `is_module_enabled('recipe')` in one place.  |

## 10. Verification

```
python scripts/validate_dependencies.py --apps-dir apps
python scripts/validate_modules.py --apps-dir apps
```

Both must exit 0 before merging. Full runtime verification matrix lives in
`ci-matrix.md` and `tests/README.md`.