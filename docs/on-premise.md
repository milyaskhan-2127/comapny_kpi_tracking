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
REPO=/path/to/repo

# 1. register every productix app present in the repo - discovered, not listed
for d in "$REPO"/apps/productix_*; do
  bench get-app "$d"
done

bench new-site my-site.local --mariadb-root-password '...' --admin-password '...'
bench --site my-site.local install-app erpnext

# 2. install what THIS deployment needs. Either every discovered app...
for d in "$REPO"/apps/productix_*; do
  bench --site my-site.local install-app "$(basename "$d")"
done

# ...or just a subset - the platform app is required, the rest are optional:
#   bench --site my-site.local install-app productix_core
#   bench --site my-site.local install-app productix_recipe

bench --site my-site.local migrate
bench --site my-site.local set-config developer_mode 1     # dev only
bench build --hard-link
supervisorctl restart all   # or restart bench services
```

Dependency order is enforced by `required_apps` in each app's `hooks.py`;
`bench` installs required apps automatically. Whether an app ends up on the
site is decided here, not by the repository layout - an app that is present
but not installed stays inert.

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