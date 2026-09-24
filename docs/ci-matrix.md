# CI Matrix

Target CI runs BEFORE any productix change is considered releasable. This
repository is **never pushed**, so the matrix is executed locally (or on a
self-hosted runner once push policy is decided).

## 1. Static gate (always)

```bash
python scripts/validate_dependencies.py --apps-dir apps   # exit 0
python scripts/validate_modules.py --apps-dir apps        # exit 0
python -m compileall -q apps/productix_core apps/productix_recipe \
       apps/productix_kpi apps/productix_instruction
```

Both validators discover apps from `productix_module.json` manifests — no
hard-coded app list, so a future `productix_manufacturing` is covered without
CI edits (`tests/test_generic_discovery.py` proves the discovery rules and
their negatives: duplicate keys, bad deps, missing manifests, cross-app
ownership, hook mismatches, cycles, version drift, legacy dotted refs).

Plus the residual-reference sweep (no stale `productix.` module paths in the
modular apps — the `productix_*` glob picks up future apps too):

```bash
grep -rEn "(^|[^_a-z])(import|from) productix(\b|\.)" apps/productix_* || true
```

## 2. Fresh-install matrix (Docker compose, per combo)

| ID | PRODUCTIX_APPS                            | Notes |
|----|--------------------------------------------|-------|
| A  | `productix_core`                          | Platform alone is a complete site (core-only) |
| B  | `productix_core,productix_kpi`            | KPI w/o Recipe/Instruction |
| C  | `productix_core,productix_recipe,productix_kpi,productix_instruction` (+ placeholder `Manufacturing`) | Full stack: all four core modules coexist + recipe overrides validated against real ERPNext manufacturing |
| M  | Migration combo — legacy `productix` baseline DB → install the new apps → retire `productix` | Tests the existing-DB migration path (see §3) |

Steps per combo (from `tests/README.md`):

1. `setup_site.<sh|ps1>` with the combo's `PRODUCTIX_APPS`.
2. `/api/method/ping` = 200.
3. Registry keys == installed apps; entitlement rows cover registry.
4. Disabled-module predicates false in isolated installs.
5. Toggle a module off in Productix Settings → its `/api/method/...` = **403**.
6. `bench migrate` clean; `bench build` clean; workers/scheduler logs empty of
   `productix.*` import errors.

## 3. Existing-DB migration (combo M)

1. Load `20260919_064927-productix_local-database.sql` (gitignored).
2. Install new apps in order → `migrate` → `scripts/migration_check.py`.
3. Retire `productix` → re-run checks + module-removal isolation smoke.

## 4. Runtime unit tests (inside bench)

```bash
docker compose exec backend bash -c \
  "cd /home/frappe/frappe-bench && /home/frappe/frappe-bench/env/bin/python -m pytest /path/to/tests -q"
```

Covers `tests/test_registry_consistency.py` (skip when no site context).

## 5. Expected artifacts per run

- `bench version` output (frappe/erpnext/app versions, commit hashes).
- `migration_check` JSON report.
- HTTP status captures for gate-403 cases.
- Worker/scheduler log excerpts (post-install, post-uninstall).
- Timestamps for each step.

## 6. Not in this matrix

- Performance/load tests (out of scope for modularity gate).
- ERPNext major upgrades (v16): separately planned.