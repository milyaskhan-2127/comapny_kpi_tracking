# Migrating an Existing Productix Database

Applies to sites running the legacy monolithic `productix` app (Recipe + KPI +
Instruction + alarms in one package, data created under modules `Recipe
Management`, `KPI Tracking`, `Instruction Room`, `Alerts`, …).

> The customer production DB used for the acceptance test is
> `20260919_064927-productix_local-database.sql` — **git-ignored**, never
> committed.

## 1. Concept

The new apps describe the **same** tables, doctypes, fields, and fixtures the
old app created — the schema is shared, ownership changes. Migration therefore
has three steps:

1. Install the new apps on the existing site (tables already exist → sync, no
   data loss).
2. Re-own metadata so Frappe looks after the records via the new apps
   (`tabModule Def.app`).
3. Retire the old `productix` app once nothing references it.

## 2. Pre-flight

```bash
# 0. Back up the production DB + files FIRST
./backup.sh            # or: bench --site <site> backup --with-files

# 1. Static validators must be green (from the repo root)
python scripts/validate_dependencies.py --apps-dir apps
python scripts/validate_modules.py --apps-dir apps
```

## 3. Step-by-step

```bash
# 2. Install the platform + feature apps, in dependency order
bench --site <site> install-app productix_core
bench --site <site> install-app productix_recipe      # optional module
bench --site <site> install-app productix_kpi         # optional module
bench --site <site> install-app productix_instruction # optional module

# 3. Migrate — runs the ownership patch:
#    productix_core.migrations.productix.repoint_module_defs
bench --site <site> migrate

# 4. Verify ownership + health
env/bin/python scripts/migration_check.py <site>   # run from the bench root
#   → tabModule Def rows now owned by the modular apps;
#     no "Alerts" orphans; entitlement rows cover the registry.
#   migration_check discovers apps/modules from manifests + legacy
#   modules.txt (no hard-coded lists) and fails if the legacy `productix`
#   app is co-installed with any modular app.

# 5. If any KPI department record had malformed data, the KPI fix patch ran
#    via productix_kpi.migrations.productix.fix_kpi_department_records
#    (idempotent).
```

## 4. What `repoint_module_defs` does

For each `tabModule Def` row that belonged to the old app:

- re-owns rows for the modules the new apps declare: `app` is set to the
  owning new app (`productix_core`, `productix_recipe`, `productix_kpi`,
  `productix_instruction`) — so `bench migrate --patch`, doctype sync, and
  desk module lists attach to the new apps without touching a single table;
- preserves the empty legacy `Alerts` Module Def row **only** when records
  still reference it (e.g. a custom field or report with module `Alerts`);
- never deletes data.

The patch lives in the `productix` migration sub-package
(`productix_core/migrations/productix/repoint_module_defs.py`) purely to keep
legacy-era file layout; it is a `productix_core` patch.

## 5. Fixtures

`bench --site <site> import-fixtures` upserts the split fixture files by name
(Roles, Custom Fields, Workspaces, Reports, Property Setters, Number Cards).
The one intended mutation: the `User-custom_user_role` Custom Field is
re-owned from `Recipe Management` → `Productix Core` (it is now a platform
field).

## 6. Retiring the old app

```bash
# ONLY after migrate + verification:
bench --site <site> uninstall-app productix
# remove it from apps.txt, drop its folder, restart services.
```

**Co-installation rule:** the legacy `productix` app and any modular
`productix_*` app must never be installed on the *same site* (17 hook
categories collide). `scripts/migration_check.py` fails the site when it
detects both; a bench may carry both codebases (legacy site + modular sites
side by side) — the rule is per site.

After retirement re-run `scripts/migration_check.py`, the smoke tests in
`tests/README.md` (module-removal isolation), and confirm worker/scheduler
logs show no `productix.*` module import errors.

## 7. Known constraints

- **Do not uninstall the old app before migrate.** The ownership patch reads
  the legacy rows; uninstall first would orphan them.
- Old monolithic API paths (`productix.api.*`, `productix.kpi_tracking.api.*`)
  are **not** served by the new apps after retirement. Update callers to the
  app-scoped paths (`productix_recipe.*`, `productix_kpi.*`, …).
- ~~Keep `apps/productix` on the bench (mounted, PYTHONPATH) until retirement~~
  — **retirement complete** (2026-09-24): the directory, its compose
  `PYTHONPATH`/mount entries and the deploy-script asset references were
  removed after the migration evidence was recorded (tag
  `pre-legacy-retirement`). Sites no longer carry legacy rows (`module_def_by_app`
  shows no `productix` key; `retired_modules` is empty once the legacy
  `modules.txt` leaves the bench).

## 8. Evidence

Capture: `bench version`, migration_check report, `tabModule Def` before/after
snapshots, `bench migrate` output, and post-retirement smoke results. The
acceptance run follows `tests/README.md` §2.