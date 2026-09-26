# Productix ERP — Acceptance Evidence Log (Final)

Machine-generated record for the **modularity acceptance gate**: Core + Recipe +
KPI + Instruction as independent Frappe apps, with real Docker install /
migration evidence. All commands below were executed against the running stack
(no code was pushed to any remote).

- Date: 2026-09-24
- Platform: Windows host / Docker Compose — Frappe & ERPNext `v15.121.3`,
  MariaDB 10.6, Redis 7 (cache/queue)
- Sites:
  | Site | DB | Role |
  |---|---|---|
  | productix-a.local | `_1c...` (own) | Fresh combo **A — core only** |
  | productix-b.local | own | Fresh combo **B — core + kpi** |
  | productix-c.local | own | Fresh combo **C — core + recipe + kpi + instruction** (+ ERPNext Manufacturing) |
  | productix-mig.local | `_4e50826e9f6322a7` | Existing-DB migration (legacy `productix` removed) |
  | productix-ref.local | `_650d82d1cc877d44` | Pristine restore of the legacy dump (reference for data-compare) |
  | productix.local | `_5a5cc2442a2840be` | Legacy monolithic site (still ingesting, unchanged) |

---

## 1. Static validators (host, no DB)

Re-run at the end of the session — both green:

```
$ env/bin/python scripts/validate_modules.py
MODULES_OK                        # core always_enabled requires=[erpnext]; recipe/kpi/instruction requires=[erpnext, productix_core]

$ env/bin/python scripts/validate_dependencies.py
DEPENDENCIES_OK                   # core 29 py/4 js; recipe 56/6; kpi 115/23; instruction 9/1
```

`validate_modules.py` enforces the `modules.txt` line ↔ `frappe.scrub(line)`
folder convention (doctype controllers at `<folder>/doctype/<dt>/<dt>.py`) that
`bench install-app` needs (`sync_for` imports `app.<scrubbed_module>`).

## 2. Fresh-install combos (acceptance matrix)

Smoke runner: `tests/combo_smoke.sh` (wrapped by `tests/_run_combo.sh` — the
host is PowerShell, shell scripts run via WSL bash + `docker.exe`). Each check
pings the frontend, verifies `is_module_enabled` for expected/absent keys,
verifies the Productix Settings entitlement rows, verifies the boot payload
(`frappe.boot.productix_modules`), and runs `bench migrate` clean.

| Combo | Command | Result |
|---|---|---|
| **A — core only** | `bash tests/_run_combo.sh productix-a.local core -- recipe kpi instruction` | **12 passed, 0 failed** |
| **B — core + kpi** | `bash tests/_run_combo.sh productix-b.local core kpi -- recipe instruction` | **13 passed, 0 failed** |
| **C — all four** | `bash tests/_run_combo.sh productix-c.local core recipe kpi instruction --` | **15 passed, 0 failed** |

Representative outputs (final re-baseline run, 05:40–05:51):

```
Combo A — expected='core'  absent='recipe kpi instruction'
  ping -> HTTP 200
  is_module_enabled('core') = True
  is_module_enabled('recipe'|'kpi'|'instruction') = False (absent)
  enabled module keys -> ["core"]
  BOOT_MODULES=["core"]
  migrate clean
smoke result: 12 passed, 0 failed

Combo C — expected='core recipe kpi instruction'
  enabled module keys -> ["core", "instruction", "kpi", "recipe"]
  BOOT_MODULES=["core", "instruction", "kpi", "recipe"]
  15 passed, 0 failed
```

## 3. Combo A regression — root cause & post-mortem (DB-global installed apps)

A re-run of combo A after an earlier recipe removal showed `is_module_enabled('recipe') = True`,
a `recipe` entitlement row, and `recipe` in the boot payload on a site that was
supposed to be core-only. Diagnosis:

- **Frappe v15 stores a site's installed apps in the per-site DB global
  `installed_apps`** (row `tabDefaultValue.defkey='installed_apps'`), **not** in
  `sites/<site>/installed_apps.txt` (absent on every site here) and **not** in
  `sites/apps.txt` (a bench-wide list that only says which apps are *mounted*).
- `frappe.get_installed_apps()` reads that DB global → `_load_registry()`
  mirrors it. The earlier recipe removal had not gone through the bench
  uninstall path, so the DB global still contained `productix_recipe`;
  registry, entitlement rows and boot payload all faithfully reflected the
  stale list.
- Probe evidence (before fix):
  ```
  INSTALLED = ['frappe','erpnext','productix_core','productix_recipe']   # << stale
  REGISTRY  = ["core", "recipe"]
  entitlement rows = [core:1, recipe:1]
  ```
- Fix (no code change needed): run the proper uninstall —
  `bench --site productix-a.local uninstall-app productix_recipe --yes --no-backup --force`
  → drops recipe tables, removes the app from the DB global
  (`remove_from_installed_apps` → `DefaultValue`), then runs
  `after_uninstall` → `productix_core.install.after_uninstall()` →
  `_invalidate_module_caches()` + `_prune_entitlement_rows()`.
- After fix (probe):
  ```
  INSTALLED = ['frappe','erpnext','productix_core']
  REGISTRY  = ["core"]
  entitlement rows = [core:1]
  is_module_enabled: core=True recipe=False kpi=False instruction=False
  redis registry/entitlement cache keys: None (invalidated)
  ```
- Why the current code is correct by construction: frappe runs
  `remove_from_installed_apps` **before** `after_uninstall` hooks, so the
  registry rebuild inside `_prune_entitlement_rows()` no longer contains the
  removed key and the ghost row is dropped. Confirmed by the isolation suite
  (§5) which performs real uninstalls.
- Consequence documented for ops: per-site installed apps on a shared bench are
  per-DB; never hand-edit `sites/apps.txt` or a legacy `installed_apps.txt` to
  change a site's installed set.

## 4. API gate — HTTP 403 enforcement (web-level, combo C)

Infrastructure note: nginx `:8080` serves only `SITE_NAME` (productix.local), so
per-site web tests run against the backend gunicorn (`localhost:8000` inside the
backend container) with the `X-Frappe-Site-Name: productix-c.local` header
(`tests/_gate_403_combo_c.py`, urllib — avoids the MSYS curl `//` quirk).
`tests/gate_403.sh` remains the host-facing variant for the nginx path.

For each of recipe / kpi / instruction (representative whitelisted method):

| Step | Expected | Observed |
|---|---|---|
| baseline call (enabled) | 200 | 200 (role context / machines / unread count) |
| `set_entitlement(module, 0)` | 200 | 200 `{"module_key":…, "enabled":false}` |
| call while disabled | **403** + gate message | `PermissionError: Productix module '<m>' is disabled on this site.` |
| platform ping while disabled | 200 | 200 (`{"message":"pong"}`) |
| `set_entitlement(module, 1)` + call | 200 | 200 (recovered) |

Non-gate behavior (per design decision): a call into a **non-installed**
productix app is **never 403'd** — `productix_ghost.smoke` returned HTTP 417
("app is not installed"), not 403. `gate_request` only acts on apps resolved
from the registry.

## 5. Module-removal isolation (real uninstalls on combo C)

`tests/isolation_test.sh <site> <app> <module_key>` — uninstalls the app via
`bench uninstall-app --yes --no-backup --force`, then verifies the remaining
apps still boot, the registry/boot payload shrink, `is_module_enabled` flips to
False, the app leaves Installed Applications, and worker/scheduler/backend logs
stay clean of the removed app. All three runs on productix-c.local:

| App uninstalled | Module | Result |
|---|---|---|
| productix_instruction | instruction | **10 passed, 0 failed** |
| productix_kpi | kpi | **10 passed, 0 failed** |
| productix_recipe | recipe | **10 passed, 0 failed** |

Representative post-uninstall checks (recipe run):
```
PASS: after: registry excludes 'recipe'
PASS: after: boot payload excludes 'recipe'
PASS: is_module_enabled('recipe') = False after uninstall
PASS: productix_recipe removed from Installed Applications
PASS: no productix_recipe references in worker/scheduler/backend logs (5m)
```

After the suite, all three apps were reinstalled (`bench install-app …`);
combo C re-smoke: **15 passed, 0 failed** — full stack restored.

> Harness note: the first instruction isolation run reported one log-scan FAIL.
> Root cause was test noise, not a defect: a pre-fix gate attempt had called
> nonexistent method paths (`productix_instruction.api.messages…`,
> `productix_kpi.api.kpi_dashboard…`), leaving exactly 4
> `ModuleNotFoundError` lines in backend logs timestamped 00:43:36Z; the
> isolation test's 5-minute log window caught them. After those lines aged past
> the window, the same test ran **10/10**. The correct method paths are
> `productix_instruction.instruction_room.doctype.instruction_message.instruction_message.get_unread_count`
> and `productix_kpi.kpi_tracking.api.machine.get_machines`.

## 6. Existing-DB migration (single install path)

Site productix-mig.local = same install path a customer's existing DB would
take: create the site from the git-ignored legacy dump, then install and retire
the monolithic app.

Order of operations and quirks (all reproducible with the retained scripts):

1. **Presync legacy schema before first migrate** — the monolithic app ships an
   old-format `patches.txt`; `bench --site … migrate` failed on the first run
   until `_presync_legacy.py` synced the legacy schema once (and a follow-up
   `_run_presync.sh` pass). After that, `bench migrate` runs cleanly.
2. **Install in dependency order** — `productix_core` first, then
   `productix_recipe` / `productix_kpi` / `productix_instruction` via
   `bench install-app <app> --force` (existing tables → sync, not create).
3. **`Productix Settings` is a Single doctype** — no `tabProductix Settings`
   table; data lives in `tabSingles`. Readiness is asserted as DocType row +
   tabSingles record + child table (`tabProductix Module Entitlement`), not
   `tab<doctype>` existence.
4. **Module Def re-owning** — `productix_core.migrations.productix.repoint_module_defs`
   derives module→owner from each new app's `modules.txt`. Final ownership:
   | App | Module Def rows |
   |---|---|
   | productix_core | Productix Core, Subscription Management, Alerts |
   | productix_recipe | Recipe Management |
   | productix_kpi | KPI Tracking |
   | productix_instruction | Instruction Room |
5. **Legacy app retirement** — `bench uninstall-app productix` is blocked by a
   frappe substring guard (`"productix" in "productix_core"`), and `--force`
   does not bypass it. Equivalent performed directly:
   `remove_from_installed_apps("productix")`. After it: DB global installed
   apps = `["frappe","erpnext","productix_core","productix_recipe","productix_kpi","productix_instruction"]`
   (verified in `tabDefaultValue`), **0 Module Def rows with
   `app_name='productix'`**, and a follow-up `bench migrate` exits 0 with all
   six modular apps synced and no orphan doctype drops.

**Data preservation (dump ↔ migration compare).** Against the pristine ref
site (productix-ref.local, straight restore of the same dump), the migrated
site matches **41/41 tables, 0 problems** — including `tabKPI Data Entry`
5006 = 5006. Earlier 1445/3561 "mismatch" readings were dump-parser artifacts
(control chars in the SQL dump), not real differences.

**Migration acceptance report** — `bash tests/_migcheck_full.sh productix-mig.local`
(re-run at close of session) ⇒ `MIGRATION_CHECK_OK`, with
`module_def_by_app` per the table above, doctype counts, registry mapping
(core/recipe/kpi/instruction), all four entitlement rows enabled, and core
singletons present (Productix Settings doctype+record, `tabProductix Module
Entitlement`, `tabAI Agent Log`).

**Web-level smoke on the migrated site** (backend gunicorn, `X-Frappe-Site-Name:
productix-mig.local`, `tests/_web_smoke_mig.py`):
```
PING                  | HTTP 200
LOGIN                 | HTTP 200
RECIPE/KPI/INSTRUCTION| HTTP 200 (all enabled module calls)
GHOST_APP_CALL        | HTTP 417 (app not installed — NOT 403)
DISABLE_RECIPE        | HTTP 200
RECIPE_DISABLED_CALL  | HTTP 403  "Productix module 'recipe' is disabled on this site."
REENABLE_RECIPE       | HTTP 200 → call HTTP 200
```

**Safety backup** taken before legacy removal (in mariadb container):
`/var/lib/mysql-files/backup_preuninstall_20260924_002951.sql` (10.68 MB).

## 7. Hygiene & repo state

- SMTP secret scrubbed from source: `email_utils.py` now defaults
  `MAIL_PASSWORD` to empty and **skips SMTP provisioning with a warning** when
  unset (both monolithic `apps/productix` and `productix_core` copies).
- `.env` (live local credentials) and the legacy dump are git-ignored
  (`.gitignore`: `.env*`, `*.sql`, `sites/`, `logs/`, `__pycache__/`).
- Stale compiled `__pycache__` (which still contained the old password string)
  purged from the working tree; regenerated on demand and git-ignored.
- **Git-history caution**: the secret still exists in the committed history of
  the monolithic app (documented in `.env.example`). Before this repo is ever
  pushed to a remote, rewrite history (git filter-repo / BFG) or rotate the
  SMTP password.
- Debug/diagnostic scripts deleted (all one-off `_probe_*`, `_diag_*`,
  `_dump_*`, `_inspect_*`, gate/debug sims, compare/dump PowerShell scripts,
  `_migrate_full.log`). Retained under `tests/`: `combo_smoke.sh`,
  `_run_combo.sh`, `gate_403.sh`, `isolation_test.sh`, `_gate_403_combo_c.py`,
  `_web_smoke_mig.py`, `_probe_site.py`, and the migration harness
  (`_migcheck_full.sh`, `_migration_check_run.py`, `_mig_install_apps.sh`,
  `_mig_run_migrate.sh`, `_run_presync.sh`, `_presync_legacy.py`,
  `_run_console.sh`, `_clear_cache.{sh,py}`), plus `test_registry_consistency.py`
  + `conftest.py`.
- `git status` at close: modified `.env.example`, `README.md`, `apps.json`,
  legacy `email_utils.py` (scrub), `deploy.*`, `setup_site.*`,
  `docker-compose.yml`; untracked (new, uncommitted): `apps/productix_core/`,
  `apps/productix_recipe/`, `apps/productix_kpi/`, `apps/productix_instruction/`,
  `scripts/`, `tests/`, `docs/`, `docker/`, `nginx.conf.template`. Nothing
  pushed.

**Acceptance verdict: all gates pass** — static validators ✓, fresh combos
A/B/C ✓ (12/0, 13/0, 15/0), gate 403 × 3 modules ✓ (ghost app never 403'd),
module-removal isolation × 3 ✓ (10/0 each), existing-DB migration ✓
(41/41 data match, MIGRATION_CHECK_OK, legacy retired, web smoke ✓).

## 8. Component-ownership audit (zero-feature-loss proof)

Closing audit against the legacy baseline (commit `456bcd7`), read-only:
**41/41 legacy doctypes mapped** (recipe 6 + subscription 2 + instruction 2 +
alerts 1 + kpi 30 = new-app totals 41 equivalents + 2 new platform doctypes
`Productix Settings` / `Productix Module Entitlement`); all legacy APIs 1:1
re-homed (byte/function-identical; `ai_agent_log.trigger_manual_scan` moved
intentionally to `productix_recipe.api.inventory`); every legacy hooks entry
covered (split across core/recipe/kpi/instruction); all 5 scheduled jobs
re-pointed, none orphaned. Alerts split by subsystem (inventory scans →
recipe, KPI alert engine → kpi, audit log → core); licensing/tenancy 100% in
`productix_core`. Intentional deltas only: retired empty `Alerts` Module Def,
dropped `desktop.py` icon metadata, cross-app `boot_session`/JS splits — none
is feature loss. Full detail: `docs/ownership-matrix.md`.
## 9. Post-acceptance deployment fix � assets / CSS serving

Symptom: the site loaded unstyled (all CSS 404) through the frontend/nginx.
Diagnosis: `assets.json` (generated by a configurator one-liner from
`apps/.../public/dist`) referenced bundle hashes that did not exist in the
shared `assets` volume that nginx actually serves; a later `bench build`
in the backend also wrote bundles into the backend's copy-on-write layer only
(`sites/assets/frappe` was a symlink into the image tree), so nginx kept
serving a different build. Every stylesheet 404'd while most JS happened to
match.

Fixes applied (docker-compose.yml / deploy.sh / ops):
1. Materialised real `sites/assets/{frappe,erpnext}` directories in the
   shared volume (bundles + source images) and reran `bench build --force`
   with `/home/frappe/.nvm/current/bin` on PATH (node otherwise absent from
   the backend `bash` PATH).
2. Configurator no longer writes `assets.json` (`bench build` owns it)
   and replaces any leftover `frappe`/`erpnext` symlink with a real copy
   (idempotent) instead of `ln -sfn`-ing over it.
3. `frontend` now mounts the productix app trees so the
   `/assets/productix_*` source-asset symlinks resolve in nginx.
4. `deploy.sh` exports node PATH and materializes the asset dirs before
   `bench build --hard-link` so built bundles always land in the
   nginx-served volume.
5. Retained reproducible harness `tests/_verify_assets.py` (login page +
   productix app_include assets + desk framework bundles; asserts all 200
   through the proxy).

Verification (post-fix, via `host:8080` and `frontend:8080`): login page
7/7 asset URLs 200; productix source assets 5/5 200; desk framework bundles
9/9 200 - VERDICT: ALL ASSETS OK. Documented in `docs/deployment.md`
s4.1.

## 10. Site-C data anomalies: root cause, repair, stability + final re-run battery

Site productix-c.local (combo C) failed two probes when per-site gate evidence
was first attempted (~07:46Z): `set_entitlement` raised
`AttributeError: 'NoneType' object has no attribute 'options'` (empty meta), and
its `installed_apps` DB global held the pre-migration list. Both anomalies share
one root: **site C was re-seeded from the legacy dump and then partially
re-applied by the KPI backup-restore API**.

### 10.1 Timestamp model (established empirically)

Frappe-written DB timestamps are **real UTC + exactly 5h** (MariaDB `NOW()` is
real UTC; container clocks are UTC; `frappe.log` is real UTC). Proof: a gate run
wrote `tabProductix Module Entitlement.modified = 13:53:49` at real 08:53:49,
and a query 682s later showed `NOW() - modified = -17318 = 682 - 18000`. All
timelines below are converted to real UTC.

### 10.2 Timeline of site C (real UTC)

| Time (Sep 23/24) | Event | Effect on C's DB |
|---|---|---|
| Sep 23 23:32 | `bench restore` of legacy dump `20260919_064927-productix_local-database.sql` | full dump state (716 tables) |
| Sep 24 00:07 | wave-1 install (`productix_core`) | Settings/MEnt/AI-Agent/Tenant DocType rows **+ DocField children** written; 4th entitlement `core` created (05:07:39 DB); `ensure_entitlements` succeeded (meta had fields) |
| 01:01 | dump file copied into `sites/productix-c.local/private/backups/` | |
| **01:04:36** | `productix_kpi.api.backup.restore_backup_file` invoked (Form Dict logged: `confirm=1`, the dump filename). Fast path pipes the whole dump into `/usr/bin/mariadb`; **MariaDB connection died mid-run** (frappe.log.1: connection-refused cascade at 01:04:36,667); fallback then died on `SET FOREIGN_KEY_CHECKS=0` with a dead frappe connection -> logged traceback | partial dump application: `tabDefaultValue` (incl. the pristine-legacy `installed_apps` row, dump line 8514) **+ `tabDocField`** <- dump; **stopped before `tabDocType`** (alphabetical order: DefaultValue < DocField < DocType). Settings/MEnt children wiped (absent from dump); every other doctype's children reverted to dump rows (Sep 18/19 dates) |
| **01:20** | wave-2 install (`productix_recipe`, `productix_kpi`, `productix_instruction`) | DocType parents created / re-created with install-time rows + `migration_hash`; recipe entitlement rows created (06:20:16-39 DB) |
| 07:39-07:40 | `bench migrate` (patch-runner proof run) | Patch Log row re-created; Module Defs all modular |
| 07:46 | first gate attempt | `set_entitlement` 500s on empty meta (the symptom) |
| 08:45-08:55 | **repairs** (below) + verification | full recovery |

Corroborating facts:

- **`tabDocField` was byte-equivalent to the dump**: pre-repair C total = 12691
  rows = pristine ref site total = 12691, with identical parent sets, counts and
  creation dates (e.g. `Recipe` children `2024-01-01`, `AI Agent Log` `Sep 18
  21:12`, `KPI Alert` `Sep 19 05:07`). Doctypes with **0** DocField rows are
  exactly those with **0 occurrences in the whole dump file** (`Machine*`, `KPI
  CEO*`, `Productix Settings`, `Productix Module Entitlement`).
- **`tabDocType` kept install-time rows** (Settings/AI-Agent wave-1 at 05:07 DB,
  KPI Alert/KPI CEO/Machine/Machine Type wave-2 at 06:20 DB) + `migration_hash`
  - proving the dump application died before `tabDocType`'s section.
- **No later restore is possible** (boundary analysis): a full fast-path success
  would have clobbered `tabDocType` (wave rows survive -> no); a fallback run on
  a live connection would have executed `DROP TABLE tabDocType` (table non-empty
  -> no); either path would have logged (frappe.log has exactly three windows:
  01:04:36 restore + connection fallout, 07:46 gate errors, nothing between).
  `ipython.log` sessions were read-only probes; shell/mysql histories empty.
- `installed_apps` repair: `scripts/_repair_c_installed_apps.py` restored the
  modular six-app list (pre-repair backup
  `/var/lib/mysql-files/backup_c_prefixrepair_20260924.sql`); `migration_check.py`
  then passed (`MIGRATION_CHECK_OK`). Patch-runner proof: deleted the Patch Log
  row for `productix_core.migrations.productix.repoint_module_defs`, re-ran
  `bench migrate` -> exit 0 and the row re-created.

### 10.3 Repair + proof of equivalence

`scripts/_repair_c_docfields.py` (standalone bootstrap) ran `sync_for(app,
force=1)` for the four modular apps + `frappe.clear_cache()`:

- Before: 12 productix doctypes with **0** DocField rows (Settings, Module
  Entitlement, KPI CEO Access/Department/KPI Access, Machine, Machine Type,
  Machine Type Parameter, Machine Reading (+ Value/Health/KPI Link),
  off-by-one field deficits on KPI Data Entry 18 vs 19 and KPI Department 7 vs 8).
- After: `ZERO_FIELD_COUNT=0`; all **43 shipped doctypes** present with fields;
  Settings=6 fields, Module Entitlement=3, Machine=25, KPI CEO Access=11;
  meta probe: `Productix Settings` exposes the exact 6 fieldnames + the
  `module_entitlements` table field; entitlement child rows intact (core,
  recipe, kpi, instruction).
- **B-equivalence**: authoritative comparison (doctype list walked from the
  shipped JSON, no hard-coded names) -> **35/35 shared doctypes between healthy
  B and repaired C match exactly on field AND perm counts, MISMATCH=0**; the 8
  `NOT_IN_DB` on B are recipe/instruction doctypes (B is core+kpi only). Two
  perm movements observed during repair (KPI Alert 5->6, KPI Definition 2->6)
  are dump-era deficits now equal to B (JSON-correct); DocPerm otherwise
  preserved.

### 10.4 Stability under `bench migrate` (acceptance-critical)

- `bench --site productix-c.local migrate` -> clean (after_migrate + search
  index queued); **pre/post field-perm diff: SHARED=43 MISMATCH=0
  EQUIVALENT** - the repair is NOT re-wiped by migrate.
- `test_registry_consistency.py` on C: **6 passed** (was 5 passed / 1 failed)
  - re-run again after the migrate and after the instruction reinstall: 6 passed
  each time.
- `bench migrate` inside combo smoke C also clean (second and third post-repair
  migrates).

### 10.5 Final re-run battery (all after repair)

| Check | Site | Result |
|---|---|---|
| Gate 403 web-level (gunicorn, `X-Frappe-Site-Name`) | C | **full PASS** x2 (pre- and post-reinstall): baseline 200 / `set_entitlement` 200 / disabled call **403** with gate message / platform ping 200 while disabled / re-enabled call 200, for recipe + kpi + instruction; ghost app **417** (never 403) |
| `test_registry_consistency.py` | C | **6 passed** (x3) |
| Isolation (`isolation_test.sh ... productix_instruction instruction`) | C | **10 passed, 0 failed** |
| Manual reinstall + registry verify | C | `REG=["core","instruction","kpi","recipe"]`, 4 enabled entitlement rows |
| Combo smoke A / B / C | A / B / C | **12/0, 13/0, 15/0** (fresh re-run 14:20; each includes a clean `bench migrate`) |
| `migration_check.py` | mig | **`MIGRATION_CHECK_OK`** |
| Registry diagnostics | mig | 6 apps installed, REG=4, all enabled, 4 rows |
| Registry diagnostics | productix.local, -ref.local (legacy-only) | `INSTALLED=[frappe,erpnext,productix]`, `REG=[]` (legacy app excluded naturally - no manifest), `core=true / recipe/kpi/instruction=false`, entitlement table correctly unavailable (core not installed) - matches baseline |
| Meta probe | C | 6 exact fields + table field + 4 child rows |

### 10.6 Restore-machinery findings (operational lessons)

- `productix_kpi.api.backup.restore_backup_file`'s `_execute_sql_dump` fast path
  pipes a raw SQL dump straight into `/usr/bin/mariadb`; on failure the fallback
  executes statements one-by-one **swallowing every error**
  (`except Exception: pass`) and fast-path success/failure leaves no
  database.log trace (fast path bypasses `frappe.db`). A partial application can
  therefore land silently with only the fallback's connection errors logged.
- The residual open micro-detail (documented, not guessed): wave-2 (01:20)
  created DocType parents but no DocField children for `Machine*`/`KPI CEO*` and
  did not re-date `KPI Alert`'s children. The proven post-01:04 dump application
  explains every child state *except* these wave-2 first-imports; the fitting
  hypothesis is a stale/negative site-scoped meta cache during import (same
  cache-staleness family as the `installed_apps` anomaly, both stemming from the
  23:32 re-seed), but the exact branch is not provable from available logs.
  Regardless of sub-cause, `sync_for(force=1)` + `clear_cache` is the definitive
  repair and is proven stable under repeated migrates (10.3/10.4).
- Ops rule now documented: after any `bench restore` of a site, run
  `bench --site <site> clear-cache` (flush site-scoped redis) **before**
  installs/migrates; treat the KPI raw-dump restore path as unsafe for partial
  application (prefer frappe-native backup/restore).

**Final verdict: all acceptance gates pass** - validators green, generic
discovery tests 21/21, combos A/B/C (12/0, 13/0, 15/0), gate x3 modules (403 +
ghost 417), isolation x3 apps (10/0 each), existing-DB migration (41/41 data,
MIGRATION_CHECK_OK, legacy retired, web smoke green), site-C anomalies root-caused
+ repaired + B-equivalent + migrate-stable, security sweep clean (no secrets,
dumps, or `.env` in tracked files; known SMTP-history caveat pre-documented).

## 11. Final completion phase — legacy retirement audit & backups (2026-09-24)

Task-1 pre-removal checklist evidence (code-level items 1-9) plus the backup
step (item 11). Tools retained: `scripts/audit_legacy_coverage.py`,
`scripts/backup_retirement.sh`, `tests/_asset_probe.py` (see `tests/README.md` §5).

**Backups (checklist item 11).** Full `mysqldump --single-transaction
--routines --triggers` of both legacy-referencing DBs, gzip + `gunzip -t`
verified, in mariadb `/var/lib/mysql-files/`:
`productix_local_pretirement_20260924_113554.sql.gz` (live legacy site,
748 `CREATE TABLE`, valid header/footer) and
`productix_ref_pretirement_20260924_113554.sql.gz` (pristine reference site,
721 `CREATE TABLE`). Read-back spot-check passed. (An earlier attempt produced
`productix_local_pretirement_earlier_manual.sql.gz` — same dump, retained.)

**Coverage audit — `LEGACY_COVERAGE_AUDIT: ALL_CHECKS_PASS` (30/30).**
`apps/productix/productix` vs union of the four modular apps:
doctypes 41/41 (+2 platform: Productix Settings, Productix Module Entitlement);
whitelisted API names 91/91 (+2 platform: `reload_registry`, `set_entitlement`);
hooks scheduler keys/jobs (3 keys,5 jobs), doc_events (10 keys), permission
query conditions (17), has_permission (19), override methods (0), fixtures dt
(6/6) — cross-app hook-key duplicates flagged `dup-ok` (frappe merges hook
dicts per site by design); `doctype_js` 5/5 with all target files present and
the legacy `native_doctype_scripts.js` split into
`recipe_doctype_scripts.js` (Item/Supplier/Batch/Purchase Receipt) +
`kpi_user_scripts.js` (User) verified `[4e] PASS`; public asset files4/4
(legacy `public/images` exists but is empty — no content to migrate); pages
10/10; workspaces2/2 (legacy dirs relocated during modularization — git `D`);
number cards1/1; report files15/15; **fixture records exact per class**:
custom_field 17 = core1+recipe16, number_card6 = recipe6, property_setter5 =
recipe5, report15 = recipe10+kpi5, role11 = recipe6+kpi5, workspace2 =
recipe1+kpi1; instruction owns zero legacy fixture records (correct);
**DocType fields legacy⊆new: 41/41, missing = none; DocPerm JSON differences
0/41**; patches re-homed: legacy `productix.migrations.productix.
fix_kpi_department_records` → `productix_kpi.migrations...` (same patch), core
carries `repoint_module_defs`.

**Hooks variable sweep.** All23 legacy hooks.py variables present in the new
union except `role_defaults`, which was **empty** (`= {}`, no-op) — correctly
not carried. New-only additions: `after_install`, `after_uninstall`,
`before_request` (platform lifecycle).

**Frontend/API integrity.** Zero legacy dotted references (`productix.api.`,
`productix.kpi_tracking.`, etc.) anywhere in the four new apps (.py/.js/.html).
Split JS files call re-homed APIs (`productix_recipe.api.inventory.*`,
`productix_kpi.kpi_tracking.api.user_management.*`). Asset serving via nginx
(:8080): app-include files 200 for recipe/kpi/core (and legacy, pre-removal);
`doctype_js` hook targets resolve200 via the public-stripped path
(`/assets/<app>/js/custom_scripts/...`) for recipe + kpi (legacy = same
mechanism); standard module-tree doctype JS returns404 for **erpnext too**
(framework serving characteristic — no legacy/new delta). Module pages
`/app/productix-recipe`, `/app/kpi-tracking`, `/app/instruction-room` =200.
`sites/assets` has working symlinks for productix/core/recipe/kpi;
`productix_instruction` link is absent and the app ships **no public assets**
(no `app_include_*` hooks) — nothing to serve; compose symlink line reviewed
for the Task-2 docker cleanup.

**Hygiene.** Removed stale duplicate
`apps/productix_recipe/productix_recipe/number_card/` (package-root orphan —
frappe loads only module-path number cards; module-level copy under
`recipe_management/` is authoritative). Container-side junk catalogued for
cleanup (bench-root `legacy_dump.sql`, stray `patches.txt`, nested
`scripts/scripts/` + `tests/tests/` copies, `productix-c.local/` logger dir).
Docker/deploy legacy references inventoried for Task 2: compose PYTHONPATH,
per-service `./apps/productix` mounts (backend/frontend), legacy
`assets/productix` symlink line, `deploy.ps1` asset-dir list, setup/deploy
comments.

**Git.** Working tree staged as the known-good pre-retirement state and tagged
(see §12 for the migration/removal steps that follow).

## 12. In-place migration of the live legacy site `productix.local` (2026-09-24)

Live legacy default site migrated in place (no restore/rebuild): pre-snapshot →
manifest installs (`_mig_install_apps.sh`, all four `--force`, final migrate) →
legacy removal from `installed_apps` (`_retire_legacy_live.sh` = retire script +
settle `bench migrate` + `clear-cache`) → post-snapshot → row-level diff.

**Install/retire outcome.**
- `installed_apps`: `["frappe","erpnext","productix",+4]` after install, then
  `["frappe","erpnext",+4 modular]` after retire (`RETIRE_OK`,
  `Installed Application` rows updated, zero Module Defs owned by `productix`).
- Module re-ownership (patch `productix_core.migrations.productix.
  repoint_module_defs`, ran 2026-09-24): `Alerts→core`,
  `Subscription Management→core`, `Productix Core` module (new, core),
  `Instruction Room→instruction`, `KPI Tracking→kpi`,
  `Recipe Management→recipe`; zero modules on app `productix`.
- Registry (generic discovery): `[] → ["core","instruction","kpi","recipe"]`;
  entitlement table seeded4 rows (`enabled=1` each) by app `after_install`.
- `bench migrate` exit 0 after install, after retire (settle), and after the
  workspace repair below (3 clean runs; no co-install state ever existed).

**Zero-data-loss verdict: `LOCAL_DIFF: ZERO_DATA_LOSS_OK` (exit 0)**
(`tests/_local_data_snapshot.py` + `tests/_local_diff.py`, pre vs final post;
`_precheck` scratch DB = pre-dump `…_113554.sql.gz` restored for row-level
classification). Business counts exact (Recipe8, Recipe Item32, Consumption
Log20, Production Order10, KPI Definition79, KPI Data Entry5017, KPI
Department13, KPI Alert202, Machine5, Machine Reading1, Instruction Message8,
Message Notification36, AI Agent Log25, Item24, Purchase Receipt6, Batch24,
Supplier6, Productix License1, DefaultValue89, …); meta name sets EXACT
(Custom Field30, Number Card30, Page26, Property Setter117, Report204, Role66,
Workspace24); doctype set +2 platform only; installed_apps/registry/entitlement
as above.

**Transient deltas found, root-caused, and repaired (never guessed):**

1. *Deleted Document +31* — row-level: **all `Scheduled Job Type`** tombstones
   (`alert_engine…`, `machine_health…`, `tasks.mark_expired_batches`,
   `run_daily_inventory_scan`, `run_scheduled_predictions`) from hook re-sync
   delete+recreate; gained/lost set **equal** (G1/G2 empty) → churn, not loss.
   Classified into diff `BOOKKEEPING` with evidence.
2. *Installed Application 3→6* — `-1 legacy +4 modular` bookkeeping; classified
   into `BOOKKEEPING`.
3. *Workspace `Company Tracking System` Link -6 / Shortcut -2 / role -1; Page
   `backups` roles -2* — root cause: the committed fixture
   `apps/productix_kpi/productix_kpi/fixtures/workspace.json` is an **early
   export** predating the Machine Health card/links, Machine Health + Backup
   Manager shortcuts and the KPI CEO role; fixture import runs **last** on
   `bench migrate` (after module-dir sync), so it overwrote the live workspace;
   the Page `backups` JSON shipped only5 of the7 roles that
   `productix_kpi.utils.boot.boot_session` provisions (missing `Desk User`,
   `All`).
   - Repair: `tests/_rebuild_workspace_fixture.py` reconstructed the workspace
     doc **exactly** from the pre-dump (`_precheck`) and wrote it to *both*
     representations (fixture list + module-dir doc =37 links /10 shortcuts /
    9 roles, cannot diverge again); `page/backups/backups.json` roles →7
     (matches boot_session) with `modified` bumped so doc sync re-imports.
   - Post-repair migrate: links37, shortcuts10, workspace roles9, page roles7 —
     **identical to pre**, residue query empty. (Lost-link label
     “Enterprise Backup & Restore Manager” vs fixture “Download Backups”:
     same target Page `backups`; the reconstructed pre-state content was kept
     verbatim.)
4. *Recipe workspace fixture-vs-module divergence (documented, not modified):*
   `fixtures/workspace.json` (32 links/14 roles/13 shortcuts) matches live pre
   **and** post exactly (no delta — no loss), while the module-dir
   `recipe_management.json` (35/16/12, `creation` stamped today) diverges.
   Runtime proves the fixture is the authoritative/last writer (a module-last
   import would have changed live; it did not), so **no action taken** pending
   product decision — module-dir file is inert-but-retained; re-export from
   live recommended if the alternate layout is ever intended.

**Functional verification on the migrated site.**
- `tests/_migcheck_full.sh productix.local` → `MIGRATION_CHECK_OK`
  (architecture=modular, no co-install, core tables + registry + entitlement OK).
- `tests/_web_smoke_local.py productix.local` → exit 0: ping200, login200,
  recipe/kpi/instruction enabled calls200, ghost app **417 not-installed**
  (isolation), legacy `productix.api.*` route **417 “App productix is not
  installed”** (legacy API surface gone), gate disable→403→re-enable→200.
- Transitional duplicate-Module-Def warnings (`… found in apps productix_* and
  productix`) observed only while both app folders existed — vanished after
  folder removal (see removal step).

**Backups re-taken mid-flight:** `productix_local/…ref…_20260924_121929.sql.gz`
(post-install, pre-retire safety point) alongside the
`…_113554.sql.gz` pre pair. Scratch DB `_precheck` (read-only grant to the
site DB user) retained until acceptance completes, then dropped.

## 13. Legacy retirement execution, post-removal validation & future-module E2E (2026-09-24)

### 13.1 Retirement gate → removal (all 13 checks passed first)

- Coverage audit pre-removal: `scripts/audit_legacy_coverage.py` →
  `LEGACY_COVERAGE_AUDIT: ALL_CHECKS_PASS` **30/30** (frozen here in §11).
- Backups: `productix_local/ref_pretirement_20260924_113554.sql.gz` +
  mid-state `_121929` pair, `gzip -t` verified; ref-site dump re-verified
  (gzip OK, 716 `CREATE TABLE`).
- Checkpoint commit `fd6acb7` + tag **`pre-legacy-retirement`** = the
  rollback point (retains `apps/productix/` + all legacy compose/deploy refs).
- `git rm -r apps/productix` + sweep of 239 untracked leftovers → `apps/` =
  the four modular apps only.
- Legacy compose/deploy references removed: backend `PYTHONPATH`, both
  backend volume mounts, the frontend app mount, the legacy asset symlink,
  the compose header comment, `deploy.ps1` asset-dir/copy list, and the
  `deploy.sh`/`setup_site.*` comments → `CONFIG_LEGACY_REFS_CLEAN`;
  `docker compose config --quiet` exit 0.
- Containers recreated; bench registries cleaned: legacy line out of
  `sites/apps.txt`, stale `sites/assets/productix` symlink removed, no
  `productix` pip package present.
- **Configurator YAML fix:** the asset-symlink section used a folded scalar
  (`- >`), which joins every line into one string after the first `#` —
  silently commenting out the actual `ln -s` commands. Changed to `- |`.
  Verified: `productix_core`/`recipe`/`kpi` symlinks recreated with
  container-start mtime; `frappe`/`erpnext` real-dir guards no-op;
  `productix_instruction` ships no `public/` (no `app_include_*`) so no
  symlink by design. (Bench `ModuleNotFoundError` tracebacks in the
  configurator log are bench's own caught `get_app_commands` noise for apps
  without `commands.py` — harmless.) Recorded in `docs/deployment.md` §4.1.
- Reference site dropped: DBs `_650d82d1cc877d44` + `_precheck` dropped with
  their grants, `sites/productix-ref.local` removed; remaining sites =
  a/b/c/mig/local (5 DBs).
- Container-FS junk from the phase removed (`.pytest_cache`, stray
  bench-root `patches.txt`, legacy dump gone with the recreate); ad-hoc
  `scripts/_q_*.sh` one-offs and the `tests/_migrate_full.log` artifact
  deleted (findings live in this file; `_mig_run_migrate.sh` regenerates
  the log).

### 13.2 Post-removal migration re-validation

- `_migcheck_full.sh productix.local` → `MIGRATION_CHECK_OK`;
  `_migcheck_full.sh productix-mig.local` → `MIGRATION_CHECK_OK`.
  **`retired_modules` semantics:** pre-removal runs listed `["Alerts"]`
  only because `_legacy_modules()` reads the legacy `apps/productix/modules.txt`
  (still present then); with the tree gone, both sites now report `[]`, and
  `module_def_by_app` has **no `productix` key** (zero Module Defs owned by
  the retired app).
- `_web_smoke_local.py productix.local` → exit 0 (ping/login/recipe/kpi/
  instruction 200, ghost 417, legacy `productix.api.*` **417 “App productix
  is not installed”**, gate disable→403→re-enable→200);
  `_web_smoke_mig.py` → exit 0 (same shape on `productix-mig.local`).
- Bench-wide module-map redis cache (`app_modules`) on `productix.local`
  still held the legacy app (rebuilt during the settle window, before the
  `apps.txt`/folder cleanup) → `bench clear-cache`; every site now reports
  `MODULE_MAP_KEYS = [frappe, erpnext, +4 modular]`, `DUP_WARNINGS=[]`
  (`tests/_diag_doctype.py`). Last legacy footprint gone.

### 13.3 Static battery (re-run on the final canonical state)

`tests/_battery_static.sh`: `VD_EXIT=0 DEPENDENCIES_OK`, `VM_EXIT=0
MODULES_OK`, `CA_EXIT=0`, `PT_EXIT=0` (**27 passed**), `AUD_EXIT=0`
(`LEGACY_COVERAGE_AUDIT: RETIRED (apps/productix absent)` — new retired-mode
branch), `AP_EXIT=0`.

- Fresh-container pytest root cause + portable fix: frappe opens a
  HOME-based `~/logs/database.log` fallback at import; `~/logs` is in
  neither the image nor any volume → `FileNotFoundError` → pytest
  `INTERNALERROR`. `tests/conftest.py` now creates `~/logs` (plus the site
  log dirs) **before** importing frappe — proven by `rm -rf /home/frappe/logs`
  then 27 passed.
- `_asset_probe.py` reworked: `/assets/*` probed via nginx `frontend:8080`
  (gunicorn never serves symlinked public assets) and `doctype_js` targets
  use the public-stripped paths (`/assets/<app>/js/custom_scripts/…`, all
  200). Module-tree doctype JS paths 404 for every app incl. erpnext =
  documented framework characteristic.
- `_verify_assets.py` → `VERDICT: ALL ASSETS OK` (login page, productix
  source assets, and the hashed desk bundles under `/assets/frappe/dist/…`
  all 200 through nginx).

### 13.4 Combos, subsets, isolation, gates, field-perm equivalence

- **Combos (baseline and final re-run identical):** A `12/0` (core only),
  B `13/0` (core+kpi), C `15/0` (all four).
- **Subsets on C** (interleaved with isolation to halve install/uninstall
  cycles): Core+Recipe+KPI `14/0`, Core+Recipe `13/0`,
  Core+Instruction `13/0`.
- **Isolation ×3:** uninstall instruction / kpi / recipe → `10/0` each
  (registry + boot shrink, app leaves Installed Applications, site boots,
  no worker/scheduler/backend residue).
- **Gates (per-site `_gate_403_combo_c.py` over gunicorn :8000):** for each
  of recipe/kpi/instruction: baseline 200 → disable 200 → **disabled call
  403 “Productix module '<k>' is disabled on this site.”** → core ping 200
  while disabled → re-enable 200 → recovered 200; ghost app **417**
  (registry-gated only, never 403).
  *Harness note:* host-facing `gate_403.sh` hits nginx, which forces
  `X-Frappe-Site-Name: __SITE_NAME__` — it can only exercise the default
  site. Running it against C disabled C but called local → false FAILs;
  this usage error is documented in the script header, per-site evidence =
  `_gate_403_combo_c.py`.
- **Field/perm equivalence (`tests/_field_perm_equivalence.py`, walks the 43
  shipped doctype JSONs):** B-vs-C `SHARED=35 MISMATCH=0 EQUIVALENT`
  (8 `NOT_IN_DB` = exactly the recipe+instruction doctypes); local-vs-C
  `SHARED=43 MISMATCH=0`.

### 13.5 Future-module E2E (generic discovery proven, zero Core edits)

Scaffolded `apps/productix_manufacturing` from
`docs/future-module-template.md` (manifest key `manufacturing`, module name
**“Manufacturing Line”** to avoid colliding with ERPNext’s own
`Manufacturing` Module Def) + compose `PYTHONPATH`/3 volume entries
(`docker compose config` 0, `up -d`):

1. **Validators with 5 apps, zero tool edits:** `MODULES_OK` +
   `DEPENDENCIES_OK`; registry output lists
   `productix_manufacturing: key='manufacturing' module='Manufacturing Line'`.
2. **Bench availability:** `install-app` refuses until the app is in
   `sites/apps.txt` (`get-app` normally appends it) — the concrete
   “available on bench” vs “installed on site” split.
3. **Bug found & fixed (now a documented template lesson):** shipping
   `install.py` **without** `hooks.py` `after_install`/`after_uninstall`
   declarations means frappe never calls it → registry stayed at 4 keys, no
   entitlement row was seeded, and `set_entitlement('manufacturing')`
   answered **417 “not installed on this site.”** After declaring both
   hooks (list form, as the real apps do): uninstall → reinstall →
   `REGISTRY=[core, instruction, kpi, manufacturing, recipe]`,
   `ENTITLEMENT` 5 rows (`manufacturing=1`), `MFG_ENABLED=True`, Module Def
   owned by `productix_manufacturing`, `installed_apps` includes the scaffold
   (`tests/_future_module_state.py`).
4. **Generic gate (`tests/_gate_future_module.py`):** baseline 200 →
   disable → **403 + standard gate message on an unknown-to-core key** →
   core ping 200 while disabled → re-enable 200 → recovered 200 →
   `FUTURE_MODULE_GATE: PASS`.
5. **Clean uninstall:** registry/entitlement back to 4, `MODULE_DEF=[]`,
   `installed_apps` back to 6.
6. **Revert to canonical repo state:** scaffold folder deleted, compose
   refs removed, `apps.txt` line removed, containers recreated →
   `docker compose config --quiet` 0, `apps/` = 4 apps, validators green
   again (4-app registry).

### 13.6 Final canonical-state suite (post-revert)

Static battery all exit 0 (pytest 27, audit RETIRED, assets OK); validators
4-app OK; combos `12/0`, `13/0`, `15/0`; gates ×3 403-pass; field-perm
`35/0` + `43/0`; `MIGRATION_CHECK_OK` ×2 (local, mig); web smokes exit 0 ×2;
`_verify_assets.py` ALL ASSETS OK.

### 13.7 Hygiene & docs

- **Secrets/data:** working tree holds only the documented dev defaults
  (`Admin@123`, `change_me_strong_password_123` in `.env`/setup
  scripts/README, each flagged “change it”); no dumps/customer data tracked
  (`*.sql`, `*.gz`, `sites/`, `.env` ignored; `git ls-files` clean for
  dumps/env). The legacy SMTP secret exists only in git history → pre-push
  still requires rotation + history rewrite; **nothing was pushed.**
- `.gitignore` += `*.log`, `*.gz` (run artifacts).
- Docs updated to the retired state: `architecture.md` (removal + tag),
  `rollback.md` (tag pointer + checkout step), `migration.md` (window
  closed), `deployment.md` (legacy wording + configurator `|` fix),
  `ownership-matrix.md` (retirement note), `README.md`,
  `future-module-template.md` (hooks-are-mandatory lesson + E2E proof),
  `tests/README.md` §4/§5 (battery runner, pytest/`~/logs` notes,
  retired-mode audit, new harness list).

---

## 14. De-specialisation + dynamic module wiring (2026-09-26)

Goal of this pass: no code path, config file or document may name a preferred
combination of modules. Any subset must work, and a new module must be
addable by dropping a folder into `apps/` - no compose edit, no script edit.

### 14.1 What changed

- `docker-compose.yml` now contains **no module names at all**. The four
  per-app bind mounts and the static `PYTHONPATH` anchor are replaced by ONE
  mount: `./apps -> /opt/productix-apps`.
- New `docker/productix-apps.sh` (sourced, POSIX sh, idempotent) discovers
  whatever is under that path at container start and:
  1. links each module into the bench `apps/` tree (for `bench`, `pip
     install -e`, `frappe.get_app_path`),
  2. exports `PYTHONPATH` for the process that sources it and everything it
     execs,
  3. rewrites `env/lib/python3.*/site-packages/productix-modules.pth`.
- The `.pth` is what keeps `docker compose exec backend bench ...` working:
  exec shells receive the image environment, not PID 1's, so a compose-level
  `PYTHONPATH` no longer reaches them. It is exactly the mechanism the image
  already uses for `frappe.pth` / `erpnext.pth`, and it needs no interpreter
  or version knowledge beyond globbing `env/lib/python3*`.
- `queue-short` / `queue-long` / `scheduler` gained a wrapper entrypoint that
  sources the shim and then hands the original `command` to the image's own
  entrypoint. `configurator.sh` and `backend-entrypoint.sh` source it
  directly. `frontend` needs no app mount (nginx only reads `sites/assets`).
- The `productix_recipe`-specific `case` block in `backend-entrypoint.sh`,
  `setup_site.sh` and `setup_site.ps1` is replaced by a generic optional
  manifest field: `"post_install": "<dotted.callable>"`. Any module can seed
  data by adding one key to its own manifest; a module with no seeding omits
  it and no deployment script changes.
- `backend-entrypoint.sh` fails fast, listing the modules that ARE available,
  when `PRODUCTIX_APPS` selects something absent from `apps/`.
- `.env.example` states module selection as a neutral spec plus five
  equally-valid illustrations - no default combination implied.
- `tests/_battery_static.sh` compiles `apps/productix_*` (glob, never a list)
  and now folds every step's exit code into one verdict, so a failing
  validator can no longer be masked by a later step.

### 14.2 Static battery (backend container)

`BATTERY=PASS`, 7/7 steps:

```
VD_EXIT=0  VM_EXIT=0  CA_EXIT=0  PT_EXIT=0 (27 passed)
AUD_EXIT=0 SHIM_EXIT=0 AP_EXIT=0   BATTERY=PASS
```

`SHIM_EXIT=0` is the new genericity proof (`tests/_test_module_shim.sh`, 13
assertions, all inside a throwaway sandbox - the real bench tree and the real
`PYTHONPATH` are never touched): every module folder linked under its own
name, non-module folders ignored, `PYTHONPATH` exact, idempotent across a
second run, safe under `set -eu` with and without a source tree, and the
`.pth` rewritten rather than appended.

### 14.3 Fresh-install matrix - all four combos

Each combo ran as an isolated compose project (`COMPOSE_PROJECT_NAME=px-<id>`,
fresh volumes, own site name, own host port) and was torn down afterwards with
an explicit `-p <project> down -v` - never the main project.

| Combo | PRODUCTIX_APPS | list-apps (exact) | smoke | restart | result |
|---|---|---|---|---|---|
| A | `productix_core` | `productix_core` | 12/0 | idempotent | **PASS** |
| B | `productix_core,productix_kpi` | `productix_core, productix_kpi` | 13/0 | idempotent | **PASS** |
| C | all four written out explicitly | all four | 15/0 | idempotent | **PASS** |
| D | *unset* (manifest discovery) | all four | 15/0 | idempotent | **PASS** |

Combo D is the important one: it is the default on every fresh host and on the
development machine, and it produces exactly combo C's installed set with zero
configuration. Every combo asserted `list-apps` **exactly** (nothing extra,
nothing missing), HTTP 200 through the frontend, entitlement rows and
`frappe.boot.productix_modules` matching the installed set, absent modules
reporting `False`, and `bench migrate` clean.

### 14.4 Post-run state

- Main stack (`productix_erp`) untouched and healthy: 9 containers Up,
  battery green, 4 apps installed, routes 200.
- No `px-*` containers, volumes or networks left behind.
- `git status`: only the intended changes; no build artifacts, no `.egg-info`.
- Nothing pushed.

### 14.5 nginx upstream resolution (pre-existing 502 found while verifying combo D)

- **Symptom:** after `docker compose up -d --force-recreate backend` (a
  backend-only change, which any host can hit), every dynamic route on the
  running stack returned **502**, while `/assets/*` stayed 200. Restarting
  the frontend restored it - so nginx was proxying a dead address.
- **Cause:** `nginx.conf.template` used `upstream backend-server { server
  backend:8000 fail_timeout=0; }`. nginx resolves an `upstream server`
  hostname **once**, at config-load time. Docker gives a recreated
  container a new IP, and nginx keeps the old one until reloaded.
- **Fix:** removed both `upstream` blocks and routed through variables in
  `server` context:

  ```
  resolver 127.0.0.11 valid=5s ipv6=off;
  set $backend_upstream  backend:8000;
  set $socketio_upstream websocket:9000;
  ...
  proxy_pass http://$backend_upstream;
  proxy_pass http://$socketio_upstream;
  ```

  A variable defers resolution to request time via Docker's embedded DNS.
  Side benefit: nginx no longer needs `backend` / `websocket` to be
  resolvable while it starts, so container start order cannot fail it.
- **Proof (not just a restart test - the first attempt was inconclusive
  because Docker reused the same IP):** the backend's former IP
  `172.18.0.8` was captured by an unrelated container, the backend was
  brought back on `172.18.0.11`, and all routes were checked **with the
  frontend never restarted**:

  ```
  /app                                              200
  /api/method/ping                                  200
  /assets/productix_core/js/productix_core.js       200
  /app/productix-recipe                             200
  /app/kpi-tracking                                 200
  /app/instruction-room                             200
  /socket.io/?EIO=4&transport=polling               200
  PROOF PASSED: nginx re-resolved to 172.18.0.11 on its own
  ```

  Same routes still 200 after removing the squatter. Covered in
  `docs/deployment.md` 4.1.
---

## 15. Half-created site: verify the database, never a file (2026-09-26)

Reported from a second host: all nine containers `Up`, `mariadb` and the
backend both reporting `healthy`, yet every request answered **502**, later
**500**. The site never recovered on its own, and restarting did not help.

### 15.1 Causal chain

| # | Where | Exact error | Consequence |
|---|---|---|---|
| 1 | install, at `bench new-site` | `Access denied for user 'root'@'...' (using password: YES)` during the `DROP USER` step | install died **after** `site_config.json` had been written |
| 2 | mariadb healthcheck | `mysqladmin ping` exited 0 despite the refusal | reported `healthy` - a false pass, no failure signal |
| 3 | configurator | checked only that `MARIADB_ROOT_PASSWORD` was *set*, never that it worked | `docker compose up -d` proceeded normally |
| 4 | every request | `pymysql.err.OperationalError: (1045, "Access denied for user '_5a5cc...'@'...'")` | HTTP **500** |
| 5 | nginx, while gunicorn was not yet listening | `connect() failed (111: Connection refused) while connecting to upstream` | HTTP **502** |
| 6 | (fixed in section 14.5) | static `upstream` block pinned a stale container IP | 502 after every container recreate |

`.env` ? `MARIADB_ROOT_PASSWORD` no longer matched the password the existing
`db-data` volume had been initialised with. Links 2 and 3 both passed anyway,
so nothing stopped the boot.

The decisive bug was the entrypoint's skip condition:

```sh
if [ -f "$BENCH_DIR/sites/$SITE/site_config.json" ]; then
    echo "[backend] site '$SITE' already exists - skipping setup"
```

`bench new-site` writes that file **before** it touches MariaDB, so a refused
root password left a configuration file with no database behind it. Existence
of a file was read as "site installed": setup was skipped, gunicorn booted
against a database that did not exist, and 1045 ? 500/502 repeated forever.
Because the decision was based on a file, restarting could never heal it.

The failing object was the site's database `_5a5cc2442a2840be` - a hash of
the site path, not of any application. Zero module names appear in any of the
errors, all four apps were installed (discovery mode) when it failed, and an
app absent from `apps/` caused no error either: **the fault had nothing to do
with which combination was selected.**

### 15.2 What changed in this repository

| File | Change |
|---|---|
| `docker/backend-entrypoint.sh` | Replaced the file-existence skip with `site_verdict` ? `fresh` / `ok` / `reinstall` / `fatal:*`, driven by the database: config present, database present, schema non-empty, the site's own credentials authenticate. Added `mysql_run`, `sql_escape`, `repair_site_grants`, `report_fatal`, `root_state`, `orphan_guard`; a pre-install root fail-fast; and a **post-install re-verification** so gunicorn never starts on a database that cannot answer. |
| `docker/configurator.sh` | Real `SELECT 1` authentication test with an actionable message, before any other service starts. |
| `docker-compose.yml` | Backend healthcheck (`curl -H "Host: $$SITE_NAME" .../api/method/ping`, `start_period: 900s`); comment explaining why the mariadb healthcheck is deliberately liveness-only; read-only mounts of the deployment sources so the battery can guard them. |
| `nginx.conf` | **Deleted** - stale, never mounted, still carrying the static-upstream block from section 14.5. |
| `tests/_battery_static.sh` | New `deployment self-heal guards` step (`DEPLOY_EXIT`). |
| `docs/deployment.md` section 3 | Rewritten to describe the verdict flow. |

A mismatched site password on a database that **holds data** is repaired
(`CREATE USER IF NOT EXISTS` + `ALTER USER` + `GRANT` - accounts only, never a
table) instead of being reinstalled; `reinstall` is only reachable when the
schema has zero tables.

### 15.3 A regression this fix introduced - found by testing it

The first run of the new configurator check **failed every fresh deployment**:

```
ERROR: MariaDB at mariadb:3306 did not answer: ERROR 2002 (HY000): Can't connect to server on 'mariadb' (115)
```

The MariaDB container logs show why:

```
10:09:30  mysqld: ready for connections.  socket: '/run/mysqld/mysqld.sock'  port: 0    ? temporary server
10:09:30  healthcheck `mysqladmin ping -h localhost` ? succeeds (it answers on the SOCKET)
10:09:30  configurator `mysql -h mariadb:3306`        ? no TCP listener yet   ? exit 1
10:09:34  mysqld: ready for connections.  port: 3306                            ? real server
```

During first-time initialisation MariaDB runs a temporary server that
listens on the unix socket but with **`port: 0`** - so `healthy` genuinely
precedes a reachable `3306`. A single-shot credential check therefore turned
a harmless race into a hard failure on every new host.

**Fix (generic):** the two outcomes are now treated differently. A *refused*
password fails immediately, because that is the failure the check exists for;
an *unreachable* server is retried against a deadline (`DB_READY_TIMEOUT`,
default 180 s), because it is almost always initialisation. The same
distinction was applied to the entrypoint via `root_state` ? `ok` / `auth` /
`connect`, so a connection problem is reported as `fatal:root-connect` rather
than being mislabelled `fatal:root-auth`. Neither path contains a fixed sleep
that would stall a healthy start.

### 15.4 Regression guard in the static battery

`tests/_battery_static.sh` gained a `deployment self-heal guards` step
(`DEPLOY_EXIT`), asserting mechanisms only - no assertion names a module, so
adding a module cannot change the result:

1. entrypoint parses under `sh -n`, contains `site_verdict` and
   `FINAL_VERDICT`, does **not** contain `already exists - skipping setup`,
   still discovers modules through `productix_module.json`, and hands over to
   `start.sh` **after** the final verdict;
2. configurator parses and contains both `MARIADB_ROOT_PASSWORD was rejected`
   and a real `SELECT 1` (a set-only check fails);
3. compose has the ping healthcheck, its `Host: $$SITE_NAME` header and a
   first-boot-safe `start_period`, and **hard-codes no module**
   (`grep -o 'productix_[a-z0-9_]*'` ? empty);
4. the nginx template has no static `upstream` block and still has its
   `resolver`;
5. behaviour: root really authenticates, and the exact probe the compose
   healthcheck runs answers 200.

The guard was proven to be capable of failing - a marker line was added to
`docker-compose.yml`, then to the entrypoint, and removed after each run:

```
--- deployment self-heal guards ---
  !! docker-compose.yml hard-codes a module: productix_kpi
DEPLOY_EXIT=1
!! deployment_self_heal FAILED (exit 1)
BATTERY=FAIL (1 step(s) failed)

--- deployment self-heal guards ---
  !! entrypoint skips setup whenever site_config.json exists (the original bug)
DEPLOY_EXIT=1
!! deployment_self_heal FAILED (exit 1)
BATTERY=FAIL (1 step(s) failed)
```

Both markers were then removed and the battery returned to `BATTERY=PASS`
with `DEPLOY_EXIT=0`.

### 15.5 Evidence (live runs, 2026-09-26)

All runs on this machine against this working tree (nothing committed).

**A. Happy path - existing site.** Backend restarted to exercise the final
entrypoint: `site verdict: ok` ? `site verified` ? `starting gunicorn`,
`restarts=0`, `(healthy)`, `grep 1045|Access denied` ? none.

**B. Wrong root password - configurator (the fail-fast that was missing).**

```
ERROR: MARIADB_ROOT_PASSWORD was rejected by MariaDB (mariadb).
       The db-data volume keeps the password it was initialised with, so editing
       .env alone does not change it - .env and that volume now disagree.
       Fix: set MARIADB_ROOT_PASSWORD in .env to the password the volume uses.
       On a host whose data you can lose you may instead start over with
       'docker compose down -v' - that DESTROYS the database.

  EXIT=1   elapsed=1s
```

1 second - the refused-password branch must **not** pay the 180 s connection
retry (section 15.3), and it does not.

**C. Wrong root password - backend.** Throwaway container, correct apps,
bad password:

```
[backend] selected modules:productix_core  productix_instruction productix_kpi productix_recipe
[backend] site verdict: fatal:root-auth
[backend] ==================== FATAL ====================
[backend] MariaDB rejected MARIADB_ROOT_PASSWORD.
...
>>> EXIT CODE = 1  (expected 1, and gunicorn must NOT start)
```

**D. Fresh install, first-init race replayed.** `px-verdict` - isolated
project, **volumes destroyed first** so MariaDB re-ran initialisation
(port 8086):

```
[configurator] waiting for MariaDB at mariadb:3306 to accept TCP connections...
[configurator] ready (site=productix.local)
  up -d elapsed = 37s          configurator exit=0
[backend] site verdict: fresh
[backend] installing:productix_core  productix_instruction productix_kpi productix_recipe
[backend] running post_install hook for productix_recipe: productix_recipe.setup_data.run
[backend] site verified: 'productix.local' is answering
```

The temp-server window that broke the first draft of this fix (section 15.3) is now
retried through instead of failing.

**E. THE INCIDENT, REPRODUCED AND REPAIRED.** A fully installed site (748
tables) was damaged into the friend's exact state - database dropped,
`site_config.json` deliberately left in place - then given an ordinary
`docker compose restart backend`:

```
db_name = _5a5cc2442a2840be
--- tables before drop (site is fully installed) ---
748
--- dropping the database ---
  drop exit = 0
--- site_config.json is deliberately LEFT IN PLACE ---
-rw-r--r-- 1 frappe frappe 116 ... /sites/productix.local/site_config.json
```

Next boot:

```
[backend] site 'productix.local' is half-created (config without a usable database)
[backend] site verdict: reinstall
[backend] removing the half-created site directory sites/productix.local
[backend] installing:productix_core  productix_instruction productix_kpi productix_recipe
[backend] running post_install hook for productix_recipe: productix_recipe.setup_data.run
[backend] site verified: 'productix.local' is answering
```

Full verdict history for that stack:

| # | verdict | what happened |
|---|---|---|
| 1 | `fresh` | first install |
| 2 | `ok` | verified, gunicorn |
| 3 | `reinstall` | **config present, database gone ? rebuilt** |
| 4 | `ok` | rebuilt and verified |

Final state: `health=healthy`, all five routes **200** following redirects,
`grep 1045|Access denied` ? **none**. Under the old rule (`if [ -f
site_config.json ]`) verdict 3 would have been `ok`, gunicorn would have booted
against a missing database, and every request would have answered 500/502
forever - restarting could never have healed it.

**F. Not a regression.** `/app` answers `301 ? /login?redirect-to=...`
unauthenticated. The untouched old-code stack `px-fresh` answers the
**identical** redirect, so this is ordinary Frappe behaviour, not a change:
`-L` ? 200 for `/app`, `/app/productix-recipe`, `/app/kpi-tracking`,
`/app/instruction-room` on both stacks.

**G. Battery.** `BATTERY=PASS`, all eight steps `=0` including
`DEPLOY_EXIT=0`. Guard proven capable of failing in both directions
(section 15.4), then markers removed and re-run to green.

### 15.6 Separate issue found while proving this fix (not caused by it)

The fresh install surfaced a **pre-existing** failure, recorded here so it is
not mistaken for a regression of the work above.

`set-config developer_mode 1` was already in the committed entrypoint
(HEAD line 141) and in `setup_site.sh:138` / `setup_site.ps1:91`. With
`developer_mode` on, Frappe's `NumberCard.on_update` writes the card back into
the **app source tree**:

```python
def on_update(self):
    if frappe.conf.developer_mode and self.is_standard:
        export_to_files(record_list=[["Number Card", self.name]], record_module=self.module)
```

Inside the container, every file that came from the host git checkout is
`root:root` while the runtime user is `frappe` (uid 1000):

```
--- probe: a NEW file created by frappe (uid 1000) ---
  -rw-r--r-- frappe:frappe  .../.ownprobe
--- a python file that came from git on the host ---
  -rw-r--r-- root:root      .../productix_recipe/__init__.py

ownership census over every linked module (files):
  productix_core         36 frappe:frappe   46 root:root
  productix_instruction  15 frappe:frappe   18 root:root
  productix_kpi         121 frappe:frappe  193 root:root
  productix_recipe       63 frappe:frappe   96 root:root
  total                 235 frappe:frappe  353 root:root
```

`open(path, "w+")` on an existing file needs write permission on the *file*,
not the directory, so the export dies:

```
File ".../export_file.py", line 56, in write_document_file
    with open(path, "w+") as txtfile:
PermissionError: [Errno 13] Permission denied: '.../total_active_items.json'
```

Frappe's `bench execute` then swallows that real exception and re-raises a
misleading one, which is what appears in the log:

```python
try:
    ret = frappe.get_attr(method)(*args, **kwargs)
except Exception:
    ret = eval(method + "(*args, **kwargs)", globals(), locals())   # ? NameError
```

**Consequence.** `setup_workspace.run()` calls `_setup_custom_docperms()`
first (line 14, which completes) and then `_create_number_cards()` (line 15,
which throws), so lines 16-19 - dashboard charts, workspace layout,
builtin-workspace hiding, page roles - plus `setup_data.run()`'s
`_create_team_messages()` are skipped, and the hook exits non-zero. The
container restarts once and then serves normally: **steps 1-11 did commit**
(verified - the rebuilt site holds exactly the 6 suppliers `_create_suppliers()`
creates, 24 items, 66 roles) and all 6 recipe Number Cards are present because
they also ship as **fixtures** declared in `hooks.py:115`, which `bench migrate`
imports independently. End state is `healthy` with every route 200.

**Status: FIXED (option A) - `developer_mode` is now forced off in the
deployment path.** The entrypoint runs as `frappe` with no root, so it can
never `chown`/`chmod` host-bound files; removing the reason to write the
source tree at all is the fix that needs no privilege.

| File | Change |
|---|---|
| `docker/backend-entrypoint.sh` | Install path sets `developer_mode 0` before `migrate` and the hooks. A new step between the final verdict and the gunicorn handover re-asserts `0` on **every** start, so a site created before this change heals itself. |
| `setup_site.sh` / `setup_site.ps1` | The manual path sets `0` instead of `1`. |
| `docker-compose.yml` | The two setup scripts were added to the read-only deployment mounts so the battery can check them. |
| `tests/_battery_static.sh` | New group 6: fails if any of the three scripts enables `developer_mode`, or if it stops forcing it off. |

Checked against the frappe source before changing it, because `bench migrate`
and the fixture import must keep working:

- `frappe/utils/fixtures.py` - `import_fixtures` is **not** gated on
  `developer_mode` at all, so fixtures (Role, Custom Field, Workspace,
  Number Card, Report) still import on every migrate.
- `frappe/commands/site.py` and `frappe/installer.py` contain no
  `developer_mode` reference, so `bench new-site` never enables it either.
- `frappe/modules/patch_handler.py:149` already forces it to `0` while
  patches run, so migrate never depended on it being on.
- The two developer-only actions it does gate (`export_customizations`,
  login-as-a-user) are called nowhere in this repo.
- Telemetry's `is_enabled()` additionally requires `on_frappecloud()` and a
  `pulse_api_key`, both absent - it stays disabled.
- Two runtime effects move in the right direction: `assets_json` becomes
  cached (`frappe/utils/__init__.py:1025`) and CORS preflight gains
  `Access-Control-Max-Age` (`frappe/app.py:333`).

Evidence - fresh install, volumes destroyed first (project `px-verdict`,
port 8086):

```
[backend] site verdict: fresh
[backend] running post_install hook for productix_recipe: ...setup_data.run
  Custom DocPerms configured         = 1    (last line reached before the crash)
  Number Cards created               = 1    (was 0 - this is exactly where it died)
  configured successfully            = 1    (hook's final line, never reached before)
  PermissionError                    = 0    (was 2)
  NameError                          = 0    (was 2)
  Traceback                          = 0    (was 4)
[backend] initial setup complete
[backend] site verified: 'productix.local' is answering
developer_mode = 0
restarts=0    health=healthy    1045/Access denied: none
/login /app /app/productix-recipe /app/kpi-tracking /app/instruction-room -> 200
```

The crash-restart is gone as well: `restarts=0`, against `1` before.

Self-healing on a site that already existed: the main stack's
`productix.local` was installed with `developer_mode: 1`. After the backend
container was recreated with this change, its next boot printed
`site verdict: ok` -> `site verified` -> `starting gunicorn`, and
`site_config.json` now reads `developer_mode = 0`.

Guard proof - `# marker developer_mode 1` planted in both files at once:

```
!! /usr/local/bin/backend-entrypoint.sh enables developer_mode (saving a standard document then writes the source tree)
!! /opt/productix/deployment/setup_site.sh enables developer_mode (saving a standard document then writes the source tree)
DEPLOY_EXIT=1    BATTERY=FAIL    exit 1
```

Both files then restored byte-identical and the battery went green again.

## 16. Boot race: nginx served for minutes before gunicorn bound :8000 (2026-09-26)

### 16.1 What was actually broken

A deployment on a second machine came up reporting **502 Bad Gateway** on
every route while `docker compose ps` showed every container green. The log
showed the selection layer working correctly (`selected: productix_core
productix_recipe`, `missing: (none)`), no crash loop, gunicorn listening on
`0.0.0.0:8000` with four workers booted — so neither this repo's two known
502 causes (§14.5 stale container IP, §15 half-created site) nor the module
selection was involved.

The cause was a **race at boot**, invisible in every one of those places:

- `docker-compose.yml` had `frontend.depends_on: backend` in the **short
  form**, i.e. `service_started`, not `service_healthy`. The frontend was
  released the moment the backend *container* existed.
- `docker/frontend-entrypoint.sh` rendered the nginx config and
  `exec nginx` immediately, with **no readiness check at all**.

The backend deliberately does its slow work *before* handing over to gunicorn
(`bench new-site` → `bench build` → `bench migrate` → compile translations).
nginx therefore accepted traffic while nothing was listening on `:8000` →
`connect() failed (111: Connection refused)` → 502 on every request.

Measured on the affected host: nginx started accepting at **15:45:39**,
gunicorn reported `Listening on http://0.0.0.0:8000` at **15:47:50** — a
**2 min 11 s** continuous window of 502. On a true first boot that window is
many minutes, which is exactly why the backend healthcheck carries
`start_period: 900s`.

### 16.2 The fix — two layers

**Layer 1, the gate (`docker/frontend-entrypoint.sh`).** Before
`exec nginx` the script probes the backend in a loop. The probe is
deliberately the *same* request the compose healthcheck makes — ping **with a
`Host` header**, because frappe resolves the site from that header; without it
a perfectly healthy backend answers 404 and reads as dead. It runs at most
`FRONTEND_BACKEND_WAIT_SECONDS` (default 300) and on timeout starts nginx
**anyway**, loudly: a slow first boot is delayed, never blocked. Missing
`BACKEND`/`SOCKETIO` is a hard, explanatory failure, and after substitution
any surviving `__UPPER_CASE__` token aborts the start — nginx can never
silently proxy to a literal placeholder.

**Layer 2, the net (`nginx.conf.template`).** For a backend that dies
*later*:

```nginx
error_page 502 504 =503 /_warming_up;
```

`location = /_warming_up` is `internal`, serves a self-reloading page from
`__WARMING_DIR__` and adds `Retry-After: 5` + `Cache-Control: no-store`
(`always` — 503 is not in `add_header`'s default status list). Only
connection-level failures take this path: `proxy_intercept_errors` stays off,
so an error the **application** returns passes through untouched.

Nothing is hard-coded. The upstreams are now `__BACKEND_UPSTREAM__` /
`__SOCKETIO_UPSTREAM__` rendered from the `BACKEND`/`SOCKETIO` env vars — the
same `BACKEND` the gate probes, so the address nginx proxies to and the
address the gate waits on are the same string and cannot drift apart. The
warming-page directory is resolved at container start and injected as
`__WARMING_DIR__`; the image runs as uid 1000 so system paths such as `/opt`
are read-only and `mkdir` there fails, hence a candidate list with an
explicitly-announced fallback rather than a crash loop.

**Why `depends_on` was not changed to `service_healthy`:** the backend
healthcheck's `start_period` is 900 s, so on a first boot that would hold the
static assets back for the entire install. The short form is kept on purpose
and the gate waits only for gunicorn to actually serve.

### 16.3 Bug found by the new check itself

The first run of the container check failed on its own guard: the header
comment of `nginx.conf.template` contained the literal token `__UPPER_CASE__`
as an illustration of the substitution syntax. The entrypoint's
placeholder-left check (correctly) refused to start nginx. The comment was
rewritten to describe the syntax without emitting a match. This is the check
working as intended — before it, that class of mistake would have shipped as
nginx proxying to a nonsense upstream.

### 16.4 Evidence (all run on this checkout, 2026-09-26)

**Behavioural check** — `tests/frontend_gate_check.sh`, throwaway container
at the image's default uid (24 checks, exit 0):

```
ok  empty BACKEND / empty SOCKETIO are hard, explanatory failures
ok  nginx -t passes on the rendered config; no placeholder survives
ok  backend + socketio upstreams came from the env vars; site name rendered
ok  unwritable FRONTEND_WARMING_DIR was not used, fallback announced loudly
ok  warming page written to a writable path, and reloads itself
ok  / -> 503 + Retry-After: 5 (was 502)
ok  /login -> 503 + Retry-After: 5      ok /app -> 503 + Retry-After: 5
ok  warming response is not cacheable; body is the self-reloading page
ok  nginx held back the full window (4s), timeout reported, started anyway
ok  a serving backend releases nginx immediately (1s, window was 30)
ok  requests proxy through (200)
RESULT PASS=24 FAIL=0
```

**Live stack** — gate on a real backend restart:

```
[frontend] waiting up to 300s for http://backend:8000/api/method/ping
[frontend] backend is serving (after 10s) - starting nginx
[frontend] starting nginx (site=productix.local, backend=backend:8000,
                            socketio=websocket:9000, warming=/tmp/productix-warming)
```

**Live stack** — layer 2, with the frontend *never restarted*
(`docker compose stop backend`, then `start`):

```
before:  / -> 200   /login -> 200   /api/method/ping -> 200   /app -> 301   /favicon.ico -> 404
stopped: / -> HTTP/1.1 503 + Retry-After: 5   (all five routes)
         body = the self-reloading "Starting up" page (1019 bytes)
restarted: / -> 200  /login -> 200  /api/method/ping -> 200  /app -> 301  /favicon.ico -> 404
           (no Retry-After on any of them - exact baseline restored)
```

**Regression guards and matrix** (unchanged baselines):

```
deployment guard group 4b added .... DEPLOY_EXIT=0    BATTERY=PASS
combo A (core only) ................ 12 passed, 0 failed
combo B (core + kpi) ............... 13 passed, 0 failed
combo C (all four) ................. 15 passed, 0 failed
host selection tests ............... LOCAL-SELECTION=PASS, LOCAL-SELECTION-PS=PASS
docker compose config --quiet ...... exit 0
sh -n on the entrypoint / bash -n on the battery  .... exit 0
```

Guard 4b is mechanism-based — probe before `exec nginx`, loud timeout,
refusal of a blank target, upstream taken from the env, `error_page` +
`Retry-After` present, warming location `internal` — so adding a module cannot
make it pass or fail.

### 16.5 Files changed

`docker/frontend-entrypoint.sh`, `nginx.conf.template`, `docker-compose.yml`
(frontend readiness env + the entrypoint mounted read-only into the backend so
the battery can read it), `.env.example`, `tests/_battery_static.sh` (group
4b), `tests/frontend_gate_check.sh` (new), `tests/README.md` §4,
`docs/deployment.md` §4.2/§6.
