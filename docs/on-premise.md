# On-Premise Deployment

Productix ships as ordinary Frappe apps; there is no cloud dependency and no
forced telemetry. On-premise equals: run a Frappe/ERPNext v15 bench on your
own hardware/VM and install the productix apps from this repository.

## 1. Requirements

- Frappe/ERPNext **v15** (tested against `frappe/erpnext:v15.121.3`).
- Python 3.10+ bench environment, MariaDB 10.6+ (or supported MySQL), Redis.
- The productix apps you intend to install, copied into the bench `apps/`
  folder (any app shipping `apps/<app>/<app>/productix_module.json` — see
  `apps.json` for the current list; discovery is manifest-based, so future
  apps need no registry edits).

## 2. Install (no Docker)

```bash
# from the frappe-bench root
bench get-app productix_core /path/to/repo/apps/productix_core
bench get-app productix_recipe /path/to/repo/apps/productix_recipe
bench get-app productix_kpi     /path/to/repo/apps/productix_kpi
bench get-app productix_instruction /path/to/repo/apps/productix_instruction

bench new-site my-site.local --mariadb-root-password '...' --admin-password '...'
bench --site my-site.local install-app erpnext
bench --site my-site.local install-app productix_core
bench --site my-site.local install-app productix_recipe   # optional
bench --site my-site.local install-app productix_kpi      # optional
bench --site my-site.local install-app productix_instruction  # optional
bench --site my-site.local migrate
bench --site my-site.local set-config developer_mode 1     # dev only
bench build --hard-link
supervisorctl restart all   # or restart bench services
```

Dependency order is enforced by `required_apps` in each app's `hooks.py`;
`bench` installs required apps automatically.

## 3. Site-name & customer isolation

- No site names or customer names are hard-coded in any app. The nginx
  template injects `SITE_NAME`; bench `common_site_config.json` is generated
  by the `configurator` service.
- Tenancy/licensing lives in `productix_core` (Productix Settings +
  `subscription_management`); no app assumes a single-customer world.

## 4. Offline / air-gapped installs

All productix code is local to this repository (apps folders are plain source;
no fetch required beyond `frappe`/`erpnext` wheels, which you would mirror into
a local pip index). `pip install -e apps/<app>` after `get-app`/copy is
sufficient.

## 5. Operating at the edge

- Frontend nginx: `nginx.conf.template` → rendered by
  `docker/frontend-entrypoint.sh` on container start (sed, no extra deps).
  Port `8080` inbound; adjust TLS at your reverse proxy.
- Backups: `backup.sh` or site-level `bench backup --with-files`; ship dumps
  to your own storage. DB dumps are git-ignored and must never be committed.

## 6. Upgrade cadence

Follow `versioning.md` (compat matrix) — pin `frappe/erpnext:v15.121.3`
(or a 15.x patch of your choosing), then roll productix apps independently.
Run `deploy.sh` after each change. On-premise installations that do not use
Docker just run `bench migrate` + `bench build` per app version bump.