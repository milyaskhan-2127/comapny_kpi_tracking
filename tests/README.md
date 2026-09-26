# Productix ERP — Acceptance Test Plan

These tests exercise the *modularity acceptance gate* for the productix split.
They are run inside a running Frappe/ERPNext v15 bench (Docker), then capture
evidence for the final report. Nothing here pushes to any remote.

## 1. Fresh-install matrix (docker compose)

Reuse `setup_site.sh` / `setup_site.ps1` with `PRODUCTIX_APPS` to install each
combination on its own site/DB:

| Combo | PRODUCTIX_APPS                                   | What it proves                          |
|-------|--------------------------------------------------|-----------------------------------------|
| A     | `productix_core`                                 | Platform alone is a complete site       |
| B     | `productix_core,productix_kpi`                   | KPI works with platform only            |
| C     | `productix_core,productix_recipe,productix_kpi`, `productix_instruction` (+ placeholder Manufacturing) | All apps coexist without stale `productix.` references |
| D     | *unset*                                          | Manifest discovery (the default) yields exactly combo C with zero configuration |

Every combo can be driven two ways:

* **one shared stack, own site/DB** — `setup_site.sh` / `setup_site.ps1` with
  `PRODUCTIX_APPS` set, as below; or
* **a fully isolated compose project** — `COMPOSE_PROJECT_NAME=px-<id>` plus a
  port override, so the stack gets its own volumes, its own site and its own
  host port and can be torn down with `down -v` without touching anything
  else. `tests/combo_smoke.sh` takes `COMBO_SMOKE_PORT` for this.

Combos A–D were all run this way (isolated projects, fresh volumes each) and
passed; see the evidence log.

Module add/remove pairs (e.g. recipe on a core-only site, kpi removed from a
full site) are exercised by the isolation suite (§3) against combo C.

For combo C the ERPNext `Manufacturing` module is also installed — this is the
placeholder that exercises recipe's Production Order overrides against a real
ERPNext manufacturing stack.

Smoke checks per combo:

1. Site boots; `/api/method/ping` returns 200.
2. `productix_core.modules.entitlement.is_module_enabled('core')` is True.
3. Registry module keys for the installed apps are all enabled in
   Productix Settings → Productix Module Entitlement.
4. In **isolated** combos (A without recipe/kpi/instruction, B without
   recipe/instruction): `is_module_enabled('recipe')` /
   `is_module_enabled('kpi')` is **False**.
5. Disabling a module in Productix Settings then calling its
   `/api/method/...` method returns HTTP **403** (see
   `productix_core.modules.entitlement.gate_request`).
6. Boot JS exposes only the installed apps' modules in
   `frappe.boot.productix_modules`.
7. `bench migrate` is clean (no patches fail).

## 2. Existing-DB migration (single install path)

1. Recreate the production-like DB from the git-ignored dump
   `20260919_064927-productix_local-database.sql` (monolithic `productix` app).
2. The monolithic app ships an old-format `patches.txt`; pre-sync the legacy
   schema once before the first migrate (`_presync_legacy.py`), otherwise the
   first `bench migrate` fails on a stale patch reference.
3. `bench --site <site> install-app productix_core` (tables exist → sync).
4. `bench --site <site> install-app productix_recipe/productix_kpi/productix_instruction`
   in dependency order (`--force`; existing tables → sync, not create).
5. `bench --site <site> migrate` — runs
   `productix_core.migrations.productix.repoint_module_defs` (re-owns
   `tabModule Def` rows) and the KPI data fix.
6. Run `scripts/migration_check.py` → no issues; `tabModule Def.app` shows the
   new apps; legacy `productix` module rows re-mapped (empty `Alerts` def kept
   only if referenced).
7. Uninstall the old `productix` app (`bench` blocks it: substring guard
   `"productix" in "productix_core"`; `--force` does not bypass — use
   `remove_from_installed_apps("productix")`); re-run migration_check + smoke.

## 3. Module-removal isolation

1. Uninstall `productix_instruction`, `productix_recipe`, or `productix_kpi`
   from a full install.
2. Verify: no dangling hooks errors in worker/scheduler logs; remaining apps
   still boot; `ignore_links_on_delete` entries of the removed app no longer
   registered; `frappe.boot.productix_modules` shrinks; list views loaded by
   remaining apps render.

## 4. Static validators (host, no DB)

```
python scripts/validate_dependencies.py --apps-dir apps   # dependency hygiene
python scripts/validate_modules.py --apps-dir apps        # registry & ownership
```

Both must exit 0 before any of the above is attempted. Both validators (and
`scripts/migration_check.py`) discover apps generically from
`productix_module.json` manifests — there is deliberately **no hard-coded app
list**, so a future `productix_manufacturing` is validated with no tool edits.

Runtime/unit tests (inside the bench container, site context via
`PRODUCTIX_TEST_SITE=<site>`):

```
env/bin/python -m pytest tests/test_registry_consistency.py -q   # registry/entitlement invariants
env/bin/python -m pytest tests/test_generic_discovery.py -q      # manifest-discovery rules (pure + frappe-gated)
```

> **One-shot runner:** `bash tests/_battery_static.sh` (in the backend
> container) executes both validators, `compileall`, the two pytest modules,
> the legacy-coverage audit, the asset probe and the **deployment self-heal
> guards** (`DEPLOY_EXIT`), printing `*_EXIT=n` for each. The deployment step
> reads `docker/backend-entrypoint.sh`, `docker/configurator.sh`,
> `docker-compose.yml` and `nginx.conf.template` through the read-only mounts
> declared on the backend service, and asserts mechanisms only — that setup is
> decided from database state rather than a file's existence, that the root
> password is really authenticated, that the healthcheck can tell the truth,
> that nginx never pins a container IP, and that no module name appears
> anywhere in the deployment layer. No assertion names a module, so adding one
> cannot change the result. `pytest` is a test-only dependency installed
> ephemerally into the
> container env — a `docker compose up -d` recreate wipes it (the battery
> re-installs it automatically). `tests/conftest.py` also creates `~/logs`,
> the HOME-based logger fallback frappe opens at import time on a fresh
> container (without it, pytest dies with
> `INTERNALERROR: FileNotFoundError: /home/frappe/logs/database.log`).

`tests/test_generic_discovery.py` builds synthetic app trees in a temp dir and
asserts: pass case, future-module discovery without Core edits, and every
negative (duplicate `module_key`, unknown requires, missing manifest,
cross-app DocType ownership, hooks `required_apps` mismatch, dependency cycle,
platform-must-not-depend, four-source version drift, legacy `productix.` dotted
import/string/JS refs, undeclared sibling imports, cross-app hooks doctype
keys, co-install and retired-module rules, plus a monkeypatched `_load_registry`
proof that a fake `productix_manufacturing` joins the registry while legacy
`productix` never does).

`tests/test_registry_consistency.py` also asserts the architectures are never
co-installed on one site (legacy `productix` + any `productix_*` app together
= failure).

> **Module folder convention (validators enforce it):** each line in an app's
> `modules.txt` must have a matching folder whose name is
> `frappe.scrub(line)` (e.g. `Productix Core` → `productix_core/`) inside the
> app package, with doctype controllers at `<folder>/doctype/<dt>/<dt>.py`.
> Frappe's `sync_for` imports `app.<scrubbed_module>` during install; a
> missing folder raises `No module named '<app>.<scrubbed>'` and the
> `bench install-app` fails.

## 5. Final-phase retirement audit tooling

Run before removing the legacy monolith (`scripts/` and `tests/` are the
retained, documented harness):

```
# code-level Task-1 coverage audit (doctypes/APIs/hooks/fixtures/assets/
# pages/workspaces/reports/fields/perms/patches) — exits 0 only if every
# mandatory check passes:
docker cp scripts/audit_legacy_coverage.py <backend-id>:/tmp/
docker compose exec -T backend env/bin/python /tmp/audit_legacy_coverage.py

# pre-retirement DB backup of the two legacy-referencing sites (gzip + gunzip -t
# verified, no secret in file — reads container env):
Get-Content scripts/backup_retirement.sh -Raw | docker compose exec -T -u root mariadb sh -s

# static-asset + module-page probe (nginx /assets 200s, /app module routes):
docker cp tests/_asset_probe.py <backend-id>:/tmp/
docker compose exec -T backend env/bin/python /tmp/asset_probe.py
```

**After retirement** the code-level audit self-reports instead of failing
(the pre-removal 30/30 run is frozen in `ACCEPTANCE_EVIDENCE.md` §11; tag
`pre-legacy-retirement` keeps the audited tree retrievable):

    LEGACY_COVERAGE_AUDIT: RETIRED (apps/productix absent)   # exit 0

Post-retirement harness (all retained under `tests/`):

- `_battery_static.sh` — static battery runner (validators, compileall,
  pytest, audit, asset probe, deployment self-heal guards) with exit codes
  per stage.
- `_field_perm_equivalence.py <siteA> <siteB>` — DocField/DocPerm
  equivalence over the shipped doctype set (B-vs-C → `SHARED=35 MISMATCH=0`;
  local-vs-C → `SHARED=43 MISMATCH=0`).
- `_gate_403_combo_c.py` / `_gate_future_module.py` — per-site gate 403
  evidence via gunicorn :8000 with an explicit site header. The host-facing
  `gate_403.sh` can only exercise the nginx `SITE_NAME` site (nginx forces
  the header) — see its own header note before using it on a non-default
  site.
- `_future_module_state.py` — registry/entitlement/Module Def snapshot for
  a site (used by the future-module E2E).
- `_migcheck_full.sh`, `_web_smoke_local.py`, `_web_smoke_mig.py`,
  `_verify_assets.py`, `_local_data_snapshot.py`/`_local_diff.py`,
  `_site_status.py` — migration, web, asset, zero-data-loss and site-state
  evidence runners (ACCEPTANCE_EVIDENCE §1–§13).
- `_ws_counts.py` / `_ws_dump.py` / `_recipe_ws_analyze.py` /
  `_ws_diff_detail.py` / `_ws_schema_diag.py` — workspace structure and
  content evidence: counts, canonical full-doc SHA dumps, fixture-vs-live
  analysis and normalized diffs (drop system keys + generated child names).
- `_fix_recipe_ws.py` — idempotent one-shot reconciliation that rewrites the
  Recipe module-dir workspace JSON from `fixtures/workspace.json` (the
  fixture-vs-module divergence resolution, §14).
- `_smtp_acct_check.py` / `_site_legacy_diag.py` / `_clear_cache.sh`(+`.py`)
  — SMTP credential-footprint and legacy-reference diagnostics; a stale
  site-scoped `app_modules` cache (module-duplication warnings) is cleared
  with `bash tests/_clear_cache.sh <site>`.

Note: `/assets/*` must be probed through **nginx (:8080)**, not gunicorn —
gunicorn does not serve symlinked public assets (framework behavior, identical
for erpnext and all productix apps).

## Evidence capture

For each step record: version identifiers (`bench version` output), command
run, observable result (HTTP status / migration_check report / log excerpt),
and timestamp — these go into the final report.