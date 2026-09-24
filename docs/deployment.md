# Deployment

## 1. Topology

The stack is a standard Frappe/ERPNext v15 Docker deployment (`frappe/erpnext:v15.121.3`)
with the four productix apps mounted from `./apps`:

- `mariadb` (10.6)
- `redis-cache` / `redis-queue`
- `configurator` (one-shot: common_site_config + asset symlinks)
- `backend` (gunicorn)
- `queue-short`, `queue-long`, `scheduler`
- `websocket`
- `frontend` (nginx, renders `nginx.conf.template` → site name is injected,
  never hard-coded)

## 2. Selecting modules

Module selection happens in two layers:

1. **Install set** — which apps are installed on a site, chosen at setup via
   `PRODUCTIX_APPS`:
   - `setup_site.ps1` (Windows) / `setup_site.sh` (Linux)
   - Default: **discovered** — every `apps/productix_*/` app shipping a
     `productix_module.json` manifest, with the platform app (manifest
     flagged `always_enabled`, today `productix_core`) installed first. A
     future app added under `apps/` is picked up with no script edit; the
     legacy `apps/productix` directory ships no manifest and is never
     included.
   - Example subset: `PRODUCTIX_APPS="productix_core,productix_recipe"`
   - When `PRODUCTIX_APPS` is set, the platform app is still auto-added
     first if missing.
2. **Runtime enablement** — Productix Settings → *Productix Module
   Entitlement* can disable an installed module at runtime (API 403 + hidden
   from UI). See `architecture.md` §3.

## 3. Fresh deployment

```bash
# 1. Copy environment reference and set real values (SMTP, DB password, ...)
cp .env.example .env

# 2. Start the stack (background)
docker compose up -d          # or: docker compose up -d mariadb redis-cache redis-queue configurator backend websocket queue-short queue-long scheduler frontend

# 3. Create site + install apps (choose PRODUCTIX_APPS as needed)
PRODUCTIX_APPS="productix_core,productix_recipe,productix_kpi,productix_instruction" ./setup_site.sh
```

Windows: `.\setup_site.ps1` (set `$env:PRODUCTIX_APPS` first if you want a
subset).

The site is served on `http://localhost:8080` (Administrator / password from
`ADMIN_PASSWORD`, default `Admin@123` — change it).

## 4. Updating a running deployment

`./deploy.sh` (or `deploy.ps1`) runs, for each selected app:

1. `pip install -e apps/<app>`
2. `bench --site <site> migrate`
3. `bench --site <site> clear-cache`
4. `bench build --hard-link`
5. restart workers + frontend

### 4.1 Assets / CSS serving (important)

The frontend (nginx) and backend share the `assets` Docker volume mounted at
`/home/frappe/frappe-bench/sites/assets`. Both must see the **same** bundle
files, and `assets.json` (the URL map the served pages are rendered from)
must reference exactly those files. Follow these rules:

- `sites/assets/frappe` and `sites/assets/erpnext` must be **real
  directories** in the shared volume — **not** symlinks into
  `/home/frappe/frappe-bench/apps/...`. Real dirs are guaranteed by the
  configurator (it replaces any leftover symlink with a real copy) and by
  `deploy.sh` before building.
- The configurator **never writes `assets.json`**. Only `bench build`
  regenerates it (and the bundles), which it does into the shared volume.
  This is what keeps the rendered page and nginx perfectly in sync.
  (Historical bug: a hand-rolled configurator step generated `assets.json`
  from `apps/.../public/dist` — a different build tree than the volume —
  so every stylesheet 404'd and the site rendered unstyled.)
- `bench build` needs **node**, which lives under
  `/home/frappe/.nvm/current/bin` and is **not** on the default `bash`
  `PATH` in the backend container. `deploy.sh` exports it explicitly; if you
  run `bench build` by hand, do the same.
- Productix app source assets (`/assets/productix_*`) are served via symlinks
  in the volume that resolve into the app trees, so the **frontend mounts the
  apps too** — see the `frontend` service volumes in `docker-compose.yml`.

Quick manual check after a deploy (must print 200 for every asset):

    docker cp tests/_verify_assets.py productix_erp-backend-1:/home/frappe/frappe-bench/_verify_assets.py
    docker compose exec backend bash -lc "/home/frappe/frappe-bench/env/bin/python /home/frappe/frappe-bench/_verify_assets.py"

## 5. Backup / restore

`./backup.sh` → `bench --site <site> backup --with-files` (output under
`./backups/`, git-ignored). Restore per standard ERPNext practice
(`bench --site <site> restore --with-public-files --with-private-files
<dump.sql.gz>`).

## 6. Environment variables

See `.env.example` (committed reference; `.env` is git-ignored):

- `MAIL_SERVER/MAIL_PORT/MAIL_USE_SSL/MAIL_USE_TLS/MAIL_USERNAME/MAIL_PASSWORD/MAIL_DEFAULT_SENDER`
  — SMTP; the Email Account is only provisioned when `MAIL_PASSWORD` is set.
- `GROQ_API_KEY` — KPI AI assistant (or site config `groq_api_key`).
- `SITE_NAME`, `ADMIN_PASSWORD`, `MARIADB_ROOT_PASSWORD`, `PRODUCTIX_APPS`.

## 7. git-secret hygiene

Secrets were removed from the working tree (SMTP password now env-only). The
old secret **still exists in git history** — before this repository is ever
pushed, rewrite history (`git filter-repo` / BFG) or rotate the SMTP
password. Never commit `*.sql` dumps, `.env`, `sites/`, or `logs/`
(all git-ignored).