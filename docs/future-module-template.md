# Future Module Template

Use this template to bootstrap a new productix module (e.g. `productix_payroll`,
`productix_quality`, `productix_traceability`). Copy the structure of
`apps/productix_instruction` (the smallest app) and rename.

```
apps/<app_name>/
├── setup.py                              # version="1.0.0" (4-source sync)
└── <app_name>/
    ├── __init__.py                       # __version__ = "1.0.0"
    ├── hooks.py
    ├── install.py                        # after_install / after_uninstall
    ├── modules.txt                       # owned Module Def name(s)
    ├── patches.txt                       # first line: "No migration patches yet."
    ├── productix_module.json             # registry manifest
    ├── <module_pkg>/                     # e.g. payroll_tracking/
    │   ├── __init__.py
    │   └── doctype/<doc>/<doc>.json + .py (+ .js)
    ├── public/
    │   └── js/<app>.js                   # productix.* methods via Object.assign
    └── api/<area>.py                     # whitelisted methods
```

## hooks.py skeleton

```python
from __future__ import unicode_literals

app_name = "productix_<name>"
app_title = "Productix <Name>"
app_publisher = "TechoHub"
app_description = "Productix <Name> module (modularized from the monolithic productix app)"
app_email = "support@techohub.net"
app_license = "MIT"
app_version = "1.0.0"

required_apps = ["erpnext", "productix_core"]

app_include_js = [
    "/assets/productix_<name>/js/<app>.js",
]

# own doctypes only
ignore_links_on_delete = ["<Your Doc>"]

scheduler_events = {
    "daily": ["productix_<name>.<pkg>.<module>.<func>"],   # guard with require_module
    "all": [],
}

doc_events = {  # only for doctypes THIS app owns
}

fixtures = []  # fixture dt lists for export-fixtures

after_install = "productix_<name>.install.after_install"
after_uninstall = "productix_<name>.install.after_uninstall"

boot_session = "productix_<name>.utils.boot.boot_session"  # optional
```

## install.py (exactly like the others)

```python
def after_install():
    from productix_core.install import after_install as core_provision
    core_provision()

def after_uninstall():
    from productix_core.modules.registry import invalidate_registry_cache
    invalidate_registry_cache()
```

## productix_module.json

```json
{
  "app": "productix_<name>",
  "module_key": "<name>",
  "module_name": "<Module Display Name>",
  "title": "Short title",
  "description": "One sentence.",
  "requires": ["erpnext", "productix_core"],
  "version": "1.0.0"
}
```

Do **not** set `always_enabled` (only the platform may).

## Integration checklist

- [ ] `modules.txt` module name matches registry `module_name`.
- [ ] Every doctype JSON declares that module; no cross-app modules.
- [ ] Entry points start with `require_module("<name>")`.
- [ ] JS merges into `productix` via `Object.assign`; never replaces it.
- [ ] API method paths are `productix_<name>.<pkg>.api…` (app-scoped).
- [ ] No `import productix` anywhere; no sibling feature-app imports.
- [ ] `scripts/validate_dependencies.py` and `validate_modules.py` pass —
      both discover the app from its manifest automatically (no validator
      edits needed; the generic-discovery test suite proves this).
- [ ] Registry `requires` lists only `erpnext` + `productix_core` (+ core
      version constraint when the registry supports it).
- [ ] Version in all four sources matches (`__init__.py`, `hooks.py`,
      manifest, `apps/<app>/setup.py`).
- [ ] **No source edits required** in `setup_site.sh/.ps1` or
      `deploy.sh/.ps1` — they discover apps from manifests (platform first).
- [ ] Deployment wiring (documented, enumerated by design) does need the new
      app added: `docker-compose.yml` (backend PYTHONPATH + backend/frontend
      `./apps/<app>` mounts + configurator asset symlink if applicable) and
      `apps.json`.
- [ ] `tests/README.md` matrix, `docs/versioning.md` compat row updated.
- [ ] Fresh-install + subset combo acceptance (see `tests/README.md`).