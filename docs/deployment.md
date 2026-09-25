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
     future app added under `apps/` is picked up with no script edit (only
     the compose availability wiring needs the new path — see
     `future-module-template.md`). The legacy `apps/productix` tree shipped
     no manifest and has been retired from the repo.
   - Example subset: `PRODUCTIX_APPS="productix_core,productix_recipe"`
   - When `PRODUCTIX_APPS` is set, the platform app is still auto-added
     first if missing.
2. **Runtime enablement** — Productix Settings → *Productix Module
   Entitlement* can disable an installed module at runtime (API 403 + hidden
   from UI). See `architecture.md` §3.

## 3. Fresh deployment

A fresh clone comes up with **two commands** — no manual `bench` work:

```bash
# 1. Copy environment reference and set real values.
#    MARIADB_ROOT_PASSWORD and ADMIN_PASSWORD are REQUIRED on a fresh host;
#    PRODUCTIX_APPS selects which apps to install (unset = every app found
#    under apps/, e.g. PRODUCTIX_APPS=productix_core,productix_kpi).
cp .env.example .env

# 2. Start the stack (background)
docker compose up -d
```

What happens automatically:

1. **configurator** (`docker/configurator.sh`) runs first. It aborts with an
   explicit message if `MARIADB_ROOT_PASSWORD`/`ADMIN_PASSWORD` are missing
   (so a bad `.env` fails `docker compose up -d` cleanly instead of leaving
   the backend restart-looping), then writes the global bench config and
   links `sites/assets` to the shared assets volume.
2. **backend entrypoint** (`docker/backend-entrypoint.sh`) notices the site
   does not exist yet and, on its own: discovers the apps under `apps/`
   (or honours `PRODUCTIX_APPS`), runs `bench new-site`, installs ERPNext
   plus the selected productix apps, then `migrate` / `clear-cache` /
   `bench build --hard-link`, and seeds the recipe demo data **only** when
   `productix_recipe` is selected.
3. It hands over to the image's `start.sh` (gunicorn). Later restarts detect
   the existing site and skip straight to gunicorn.

`setup_site.sh` / `setup_site.ps1` remain the *manual* path — use them to
provision a second site, to add apps to an existing site, or when you want
the `PRODUCTION=1` credential enforcement from §3.1:

```bash
PRODUCTIX_APPS="productix_core,productix_recipe,productix_kpi,productix_instruction" ./setup_site.sh
```

Windows: `.\setup_site.ps1` (set `$env:PRODUCTIX_APPS` first if you want a
subset).

The site is served on `http://localhost:8080` (Administrator / password from
`ADMIN_PASSWORD`, default `Admin@123` — change it).

### 3.1 Production credentials

The setup scripts enforce safe defaults:

- **Local development**: `ADMIN_PASSWORD` and `MARIADB_ROOT_PASSWORD` default to
  `Admin@123` / `change_me_strong_password_123` with a visible warning.
- **Production** (`PRODUCTION=1`): **no defaults** — the scripts exit with an
  error unless both `ADMIN_PASSWORD` and `MARIADB_ROOT_PASSWORD` are explicitly
  provided via environment variables (or `.env` loaded by docker compose).

Example production invocation:

```bash
PRODUCTION=1 \
ADMIN_PASSWORD="$(openssl rand -base64 24)" \
MARIADB_ROOT_PASSWORD="$(openssl rand -base64 24)" \
PRODUCTIX_APPS="productix_core,productix_recipe,productix_kpi,productix_instruction" \
./setup_site.sh
```

The same applies to `setup_site.ps1` on Windows.

## 4. Updating a running deployment

`./deploy.sh` (or `deploy.ps1`) runs, for each selected app:

1. `pip install -e apps/<app>`
2. `bench --site <site> migrate`
3. `bench --site <site> clear-cache`
4. `bench build --hard-link`
5. restart workers + frontend

### 4.1 Assets / CSS serving (important)

The frontend (nginx) and backend share the `assets` Docker volume, mounted at
**`/home/frappe/frappe-bench/assets`** (the image's baked path).
`sites/assets` is a *symlink* to it that the image's
`/usr/local/bin/entrypoint.sh` recreates on every container start.

> ⚠️ **Never mount the `assets` volume at `sites/assets`.** That path is
> rewritten on every start by the image entrypoint
> (`rm -rf sites/assets && ln -s <baked> sites/assets`). If it is a mount
> point, that `rm` fails with `Device or resource busy`, the entrypoint
> exits non-zero, and **backend and frontend restart-loop forever** — on any
> host whose `sites` volume does not already contain the symlink. Mounting
> at the baked path keeps `sites/assets` a plain symlink inside the shared
> `sites` volume, which is stable everywhere, and lets Docker seed a fresh
> volume with the baked frappe/erpnext bundles so nginx works before the
> first `bench build`.

Both must see the **same** bundle
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
- The configurator's symlink section in `docker-compose.yml` must use a
  **literal block scalar (`- |`)**, not a folded scalar (`- >`): folding
  joins every line into one string after the first `#`, silently commenting
  out the actual `ln -s` commands. This was fixed on 2026-09-24; with `- |`
  the productix asset symlinks are recreated on every container start
  (verified by their container-start mtime).

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

## 7. git-secret hygiene & required pre-push history cleanup

**Working tree:** secrets were removed from tracked files long ago — SMTP
is env-only (`.env`, git-ignored; `.env.example` carries a commented
placeholder only). No dumps/customer data are tracked (`*.sql`, `*.gz`,
`sites/`, `.env`, `logs/` are all git-ignored).

**⚠️ Git history still contains one OLD SMTP password string** — a single
18-character value at `.env.example` line 13 of the first three commits
(`10d6e36`, `8413a0a`, `456bcd7`; sanitized from `fd6acb7` on). Its scope
is verified exhaustively (ACCEPTANCE_EVIDENCE §14): every file of every
commit, the current tracked tree, the running containers' env, and every
site's `tabEmail Account` rows were searched with the exact fixed string —
the only hit is those three `.env.example` blobs. The live `.env` carries
a *different*, current credential, and the one decryptable Email Account
row (site `productix.local`) holds that different value, not the exposed
one.

**Status.** Step 2 (history scrub) is **done**: `git filter-repo
--replace-text` was run locally and the rewritten history has been pushed.
Step 1 (rotation) is **still outstanding** — it is the only thing that makes
the historical string harmless, so do it before the credential is used
anywhere else:

1. **Rotate the old credential (operator action — do this now):** revoke
   the old password for `support@techohub.net` at `mail.techohub.net`.
   Nothing in the running stack uses it, so rotation cannot break the
   system; after rotation the historical string is dead even while it
   still exists in history.

2. **Scrub history (already completed on this repo; kept for reference and
   for re-verifying a clone):** run on a fresh clone (or with `--force` if
   re-running):

   ```bash
   # build the replacement patterns file without echoing the secret into docs:
   git show 456bcd7:.env.example \
     | sed -n 's/^MAIL_PASSWORD=//p' \
     | awk '{print $0 "==>REMOVED"}' > secret-patterns.txt
   git filter-repo --replace-text secret-patterns.txt
   rm secret-patterns.txt
   git push --all --force   # first push; all hashes after 456bcd7 change,
   git push --tags --force  # re-created tag pre-legacy-retirement included
   ```

   (BFG equivalent: `bfg --replace-text expressions.txt`.) Everyone with
   an older clone must re-clone after the rewrite. Verify the scrub with a
   fixed-string sweep: `git grep -F -f secret-patterns.txt $(git rev-list
   --all)` must return nothing — and re-check `.env.example` history shows
   only the commented placeholder.

Never commit `*.sql` dumps, `.env`, `sites/`, or `logs/` (all git-ignored).