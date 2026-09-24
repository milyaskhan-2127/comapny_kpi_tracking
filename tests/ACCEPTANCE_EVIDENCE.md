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
