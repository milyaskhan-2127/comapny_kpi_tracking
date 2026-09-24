# Versioning & Compatibility Matrix

## 1. Version sources

Each productix app keeps its version in **four places** (keep them in sync):

- `<app>/__init__.py` → `__version__`
- `hooks.py` → `app_version`
- `productix_module.json` → `version`
- `apps/<app>/setup.py` → `version=`

`scripts/validate_modules.py` compares all four on every run and fails the
build on any mismatch or missing source; treat the registry `version` as the
canonical **module contract** version and the app version as the packaging
version. Versions are **independent per app** — releasing `productix_recipe`
never requires a `productix_kpi` (or Core) release; each app bumps its own
four sources together.

## 2. App versioning policy

- **SemVer** (`MAJOR.MINOR.PATCH`).
  - MAJOR: schema or contract-breaking change (renamed doctype field, moved
    API, new platform requirement).
  - MINOR: backward-compatible feature addition.
  - PATCH: backward-compatible fix.
- The platform (`productix_core`) MAJOR pins the **registry contract**;
  feature apps declare `requires: ["erpnext", "productix_core"]` and any app
  may additionally require a minimum core version once the registry supports
  version constraints.

## 3. Compatibility matrix

| productix_core | productix_recipe | productix_kpi | productix_instruction | erpnext | frappe |
|----------------|------------------|---------------|-----------------------|---------|--------|
| 1.0.x          | 1.0.x            | 1.0.x         | 1.0.x                 | v15 (15.x) | v15 |
| 1.0.x          | 1.0.x            | — (not installed) | —                | v15 | v15 |
| 1.0.x          | —                | 1.0.x         | —                     | v15 | v15 |
| 1.0.x          | 1.0.x            | 1.0.x         | 1.0.x                  | v15.121.3 (test image) | v15 |

Rules:

- Any combination that includes a feature app must include `productix_core`.
- `productix_core` on its own is a valid (platform-only) install.
- Recipe + KPI + Instruction never depend on each other → any subset works.
- Upgrading ERPNext within v15 is expected to be safe; a v16 move is a
  separate, untested matrix entry — validate in a staging clone first.

## 4. Releasing a new app version

1. Bump `__version__` / `app_version` / registry `version` together.
2. Add a `patches.txt` entry for any data migration (name it
   `<app>.migrations.<majmin>.patch_name`, expose `execute()`).
3. Run the two static validators.
4. Run the acceptance matrix (`tests/README.md`) for every installed
   combination the change touches.
5. Update this matrix + `ci-matrix.md`.
6. Tag the app folder commit (e.g. `productix_core-v1.0.1`) — local tags only;
   this repository is never pushed.

## 5. Patch/upgrade flow for operators

- From this repo: `./deploy.sh` (or `deploy.ps1`) — pip editable, migrate,
  clear-cache, build, restart.
- Patches run inside `bench --site <site> migrate` in the order listed in
  `patches.txt`; the migration acceptance run records the outputs.