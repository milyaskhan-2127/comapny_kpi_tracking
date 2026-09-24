# Productix Component-Ownership Matrix

Complete mapping of every legacy monolithic `productix` component to its owner
in the four modular apps. This is the reference for requirement §17 ("DocType →
owner → dependencies → migration impact") and the audit that proves **zero
feature loss**.

Audit run: 2026-09-24 (read-only, against `apps/productix` baseline `456bcd7`).
Counts verified directly from the tree: **41/41 legacy doctypes mapped, 0
missing, 0 retired with data**. All legacy APIs, hooks, and scheduled jobs are
accounted for; the only deltas are intentional (see §7).

> **Retirement status (2026-09-24):** the audited `apps/productix` tree has
> been removed from the working tree (tag `pre-legacy-retirement` = commit
> `fd6acb7` keeps it retrievable). This matrix remains the authoritative
> component-by-component record of what the monolith contained and where each
> piece now lives.

Legend: `owner` = the app whose `modules.txt`/`productix_module.json` now owns
the component; `module` = the Frappe Module Def the doctype declares.

---

## 1. DocType ownership (41 legacy + 2 new platform)

| # | DocType | Legacy module | Owner app | Module now | Migration impact |
|---|---------|--------------|-----------|------------|------------------|
| 1 | Recipe | Recipe Management | `productix_recipe` | Recipe Management | tables exist → sync on install |
| 2 | Recipe Item | Recipe Management | `productix_recipe` | Recipe Management | sync |
| 3 | Recipe Extra | Recipe Management | `productix_recipe` | Recipe Management | sync |
| 4 | Production Order | Recipe Management | `productix_recipe` | Recipe Management | sync |
| 5 | Production Order Extra | Recipe Management | `productix_recipe` | Recipe Management | sync |
| 6 | Consumption Log | Recipe Management | `productix_recipe` | Recipe Management | sync |
| 7 | Productix Tenant | Subscription Management | `productix_core` | Subscription Management | sync |
| 8 | Productix License | Subscription Management | `productix_core` | Subscription Management | sync |
| 9 | Instruction Message | Instruction Room | `productix_instruction` | Instruction Room | sync |
| 10 | Message Notification | Instruction Room | `productix_instruction` | Instruction Room | sync |
| 11 | AI Agent Log | Alerts | `productix_core` | **Productix Core** (re-homed) | `trigger_manual_scan` moved out (§7.3) |
| 12–41 | Machine, Machine Type, Machine Type Parameter, Machine KPI Link, Machine Reading, Machine Reading Value, Machine Health Log, KPI Definition, KPI Variable, KPI Formula, KPI Formula Variable, KPI Template, KPI Template Item, KPI Input Definition, KPI Operational Table, KPI Operational Table Variable, KPI Operational Table Customer, KPI Operational Data, KPI Operational Data Value, KPI Data Entry, KPI Data Entry Value, KPI Department, KPI Business Unit, KPI User Assignment, KPI CEO Access, KPI CEO Department Access, KPI CEO KPI Access, KPI Settings, KPI Prediction, KPI Alert (30) | KPI Tracking | `productix_kpi` | KPI Tracking | sync |
| — | **Productix Settings** (NEW) | — | `productix_core` | Productix Core | new Single doctype (`tabSingles`) |
| — | **Productix Module Entitlement** (NEW) | — | `productix_core` | Productix Core | new child table |

Counts: legacy 41 = recipe 6 + subscription 2 + instruction 2 + alerts 1 +
kpi 30. New apps carry 43 = the 41 equivalents + 2 new platform doctypes
(`productix_core` 5 = 3 legacy + 2 new; recipe 6; kpi 30; instruction 2).

**Dependencies:** recipe/kpi/instruction doctypes reference only their own
module + standard ERPNext links; the only cross-module touch is recipe alerts
→ `instruction_room`/`ai_agent_log`, preserved via existence guards and core
`log_event` (§7.4). KPI Alert lives in `productix_kpi` (not an independent
"alerts" app) — see §7.1.

---

## 2. API ownership

| Legacy API | Functions | Owner | Status |
|------------|-----------|-------|--------|
| `productix/api/subscription.py` | `get_subscription_status`, `process_renewal_webhook` | `productix_core/api/subscription.py` | byte-identical |
| `productix/api/inventory.py` | 4 stock/batch fns | `productix_recipe/api/inventory.py` | identical + **new** `trigger_manual_scan` (§7.3) |
| `productix/api/backup.py` | backup/restore manager | `productix_kpi/api/backup.py` | identical |
| `productix/kpi_tracking/api/` (7 files: _dev_checks, ai_assistant, dashboard, data_entry, machine, setup, user_management) | all whitelisted methods | `productix_kpi/kpi_tracking/api/` | function-identical |
| `ai_agent_log.log_event` | audit logging | `productix_core/doctype/ai_agent_log/` | preserved |
| `ai_agent_log.trigger_manual_scan` | manual inventory scan | `productix_recipe/api/inventory.py::trigger_manual_scan` | **intentional re-home** |
| KPI services (7 files, 69 fns) + `security/permissions.py` (21 fns) | formula engine, alert engine, machine health, dashboards, CEO access | `productix_kpi/kpi_tracking/services/` + `security/` | identical |

Old monolithic paths (`productix.*`, `productix.kpi_tracking.api.*`) are **not
served** by the new apps; callers move to app-scoped paths (documented in
`architecture.md` §5).

---

## 3. Hooks ownership

| Legacy hook | Security-relevant / behavior | Owner |
|-------------|------------------------------|-------|
| `app_include_css` | productix.css → recipe; kpi_tracking.css → kpi | recipe + kpi |
| `app_include_js` | split across recipe `productix.js`/`custom_scripts`, kpi `productix.js`/`kpi_user_scripts.js`, core `productix_core.js` | core + recipe + kpi |
| `doctype_js` {Item, Supplier, Batch, Purchase Receipt} | recipe list-view + native doctype scripts | `productix_recipe` |
| `doctype_js` {User} | KPI user scripts | `productix_kpi` |
| `override_doctype_class` {Purchase Receipt, Work Order, Batch} | ERPNext overrides | `productix_recipe/overrides/` |
| `doc_events` Purchase Receipt (before_validate/on_submit/on_cancel), Work Order (on_submit/on_cancel), Stock Entry (before_save) | FEFO, GRN, production | `productix_recipe` |
| `doc_events` User (after_insert/on_update/on_trash) | license + tenant sync | `productix_core` |
| `doc_events` 6 KPI doctypes → registry invalidate | cache coherence | `productix_kpi` |
| `scheduler_events` daily (4) | inventory scan + expiry + KPI alert check + machine health | recipe (2) + kpi (2) |
| `scheduler_events` hourly (1) | scheduled predictions | `productix_kpi` |
| `has_permission` (19) | recipe (2) + kpi (17), identical lists | recipe + kpi |
| `permission_query_conditions` (17) | KPI data segregation | `productix_kpi` |
| `ignore_links_on_delete` (13 = 2+2+9) | instruction 2 + core 2 {Notification Log, Activity Log} + kpi 9 | all four |
| `boot_session` | core: license + unread + module keys; kpi: reports sync + backups page | core + kpi |
| `on_login` | `check_license_on_login` | `productix_core` |
| `website_route_rules`, jinja (`get_usable_stock`, `get_batch_status_label`) | recipe dashboard + template helpers | `productix_recipe` |
| fixtures (11 roles, 17 CF, 5 PS, 6 NC, 2 WS, 15 reports) | split 6+5 roles, 16+1 CF, 10+5 reports, 1+1 WS, recipe others | recipe + kpi + core |
| — (NEW) | `before_request` gate, `after_install`/`after_uninstall`, 4× `productix_module.json` | all (platform wiring) |

---

## 4. Scheduled jobs

| Job | Cadence | Legacy ref | New home | New gating |
|-----|---------|-----------|----------|------------|
| `run_daily_inventory_scan` | daily | `alerts/tasks.py` | `productix_recipe/tasks.py` | `require_module("recipe")` |
| `mark_expired_batches` | daily | `alerts/tasks.py` | `productix_recipe/tasks.py` | `require_module("recipe")` |
| `alert_engine.run_scheduled_alert_check` | daily | `kpi_tracking/services/alert_engine.py` | `productix_kpi` | — |
| `machine_health.run_scheduled_health_check` | daily | `kpi_tracking/services/machine_health.py` | `productix_kpi` | — |
| `kpi_tracking.tasks.run_scheduled_predictions` | hourly | `kpi_tracking/tasks.py` | `productix_kpi/tasks.py` | — |

All 5 legacy jobs re-pointed; no job added or orphaned.

---

## 5. Fixtures & pages & reports & workspaces

| Legacy | Count | Owner split |
|--------|-------|-------------|
| Roles | 11 | recipe 6 + kpi 5 |
| Custom Fields | 17 | recipe 16 + core 1 (`User-custom_user_role`, re-owned Recipe Management → Productix Core) |
| Property Setters | 5 | recipe |
| Number Cards | 6 | recipe |
| Workspaces | 2 | recipe 1 + kpi 1 |
| Reports | 15 | recipe 10 + kpi 5 |
| Pages | 10 | recipe 1 (`recipe_dashboard`) + kpi 9 |
| Public CSS/JS/templates | productix.css, kpi_tracking.css, productix.js, native scripts, backups_template.html | recipe 2 css/js + kpi 2 css/js/template + recipe custom_scripts |

---

## 6. Boundary decisions (recording why)

| Area | Decision | Justification (requirement ref) |
|------|----------|---------------------------------|
| Alerts | **Not an independent app.** Split by subsystem: inventory-scan alerts + email → `productix_recipe.tasks`; KPI Alert engine + KPI Alert doctype → `productix_kpi`; audit log `ai_agent_log` → `productix_core` | §9 — dependency analysis showed no single "alerts" owner; generic notification infra stays in core; creating `productix_alerts` would force every other module to depend on it |
| Subscription | **No separate app.** Licensing/tenant (Productix License/Tenant, webhook, `on_login`, User doc_events) fully in `productix_core` | §8 — licensing/tenant is foundational platform capability required by every customer |
| KPI services / permissions | stay in `productix_kpi` | §10/§11 — KPI-only; no cross-module dependency |
| Recipe overrides (PR/WO/SE/Batch) | stay in `productix_recipe` | recipe-only business rules |
| "Alerts" Module Def | retired from `modules.txt`; legacy row preserved under core **only when still referenced** (`repoint_module_defs.py`) | legacy metadata, not functionality |
| `desktop.py` icon/color metadata | not replicated | cosmetic; module list served via `modules.txt` + `productix_module.json` |

---

## 7. Intentional deltas (explicitly not feature loss)

1. **Alerts Module Def retired** — system preserved across recipe/kpi/core (§6).
2. **`desktop.py` module icons/colors not replicated** — cosmetic only.
3. **`ai_agent_log.trigger_manual_scan` re-homed** to `productix_recipe.api.inventory` — external callers of the old method must migrate; the function still exists under its new owner.
4. **`boot_session` split (core + kpi)** — independent slices; Frappe v15 runs all registered hooks (`frappe/boot.py`), order follows install order.
5. **Legacy JS split into 5 files** — all functionality accounted for (§3).
6. **Recipe jobs now `require_module("recipe")`** — new server-side gating; not a new job.
7. **Email provisioning now `MAIL_PASSWORD`-guarded** (core `email_utils`) — setup skips SMTP with a warning instead of writing placeholder credentials.

## 8. Verification method

- Doctype counts: `*.json` under each `doctype/` tree — legacy 41 = new apps 43 − 2 new platform doctypes.
- API/hooks/jobs: grep + diff of function bodies against the baseline commit.
- Instance-level proof: fresh combos A/B/C, module-removal isolation, and the
  existing-DB migration on `productix-mig.local` (41/41 data match) — see
  `tests/ACCEPTANCE_EVIDENCE.md`.