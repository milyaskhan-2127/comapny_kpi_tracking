# Deployment

## 1. Topology

The stack is a standard Frappe/ERPNext v15 Docker deployment (`frappe/erpnext:v15.121.3`)
with the module source tree mounted from `./apps` (one mount, no per-app
entries — see §4.1):

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

1. **Install set** — which apps are installed on a site, chosen via
   `PRODUCTIX_APPS`. There is exactly **one** implementation of the rules, in
   `docker/productix-selection.sh`, mirrored for Windows by
   `docker/productix-selection.ps1`. Every entry point uses it, so they can
   never disagree:

   | Entry point | Uses |
   |---|---|
   | `docker compose up -d` | `docker/backend-entrypoint.sh` |
   | `setup_site.sh` / `setup_site.ps1` | `productix-selection.sh` / `.ps1` |
   | `deploy.sh` / `deploy.ps1` | `productix-selection.sh` / `.ps1` |

   All four also **read `.env` themselves** (explicit export beats the file),
   so `PRODUCTIX_APPS` written in `.env` applies to the container bootstrap,
   to a manual setup and to an update alike. Before this, `.env` was
   interpolated only by docker compose, so a manual `./setup_site.sh` ignored
   it and installed a different set.

   The rules:

   - **Default: discovered** — every `apps/productix_*/` app shipping a
     `productix_module.json` manifest, with the platform app (manifest
     flagged `always_enabled`, today `productix_core`) installed first. A
     future app added under `apps/` is picked up with no script edit and no
     compose edit: `docker/productix-apps.sh` links whatever `./apps`
     contains, and discovery reads the manifests (see
     `future-module-template.md`).
   - **Explicit list**: `PRODUCTIX_APPS="productix_core,productix_recipe"` —
     commas and/or spaces, any subset. The platform app is always included
     either way, and names that do not exist under `apps/` are reported.
   - **`requires` is resolved transitively**, depth-first, so a dependency is
     installed *before* the module that needs it, even when it was never
     written in `PRODUCTIX_APPS`.
   - **The bench base (`frappe`, `erpnext`, overridable via `PX_BENCH_BASE`)
     is never part of a module selection** and never reported as missing —
     it is installed unconditionally, exactly as a Frappe site always has it.
   - **A module is an app that ships its own manifest.** `frappe` and
     `erpnext` have none, which is how the bench base stays out of a
     selection without being named in one.

   Run either selection file standalone to see what a given `.env` would do —
   it prints the ordered install list, what was requested and what is absent.

2. **Runtime enablement** — Productix Settings → *Productix Module
   Entitlement* can disable an installed module at runtime (API 403 + hidden
   from UI). See `architecture.md` §3. This is a *display/API* switch; it
   never changes what is installed on disk.

### 2.1 Drift: what happens when `.env` changes later

On **every** start the entrypoint reconciles the selection against the
site's own `installed_apps`:

| Situation | Action |
|---|---|
| selected, not installed | `bench install-app --force`, then `migrate` + `build` |
| installed, not selected | **reported loudly, never uninstalled** |
| installed but no module manifest | left alone (that is the bench base) |

`--force` is needed because of *where* drift comes from: a site whose
`installed_apps` row no longer lists an app still has that app's `Module Def`
rows, and a plain `install-app` dies on `Duplicate entry '<Module>' for
PRIMARY`. `force` only relaxes that duplicate check and re-syncs the app's
doctype JSON — it never drops a table or a document, and it never reaches this
script's own `post_install` re-seed (that is a separate runner, see below).
The install is still gated on the site's own `installed_apps`, so `--force`
can never be pointed at an app the site already reports as installed.

Uninstalling is deliberately never automatic: dropping an app drops its
tables with it. If a module really should go, the report prints the exact
`bench --site <site> uninstall-app <module>` to run by hand.

The outcome is printed as a **module status** block just before gunicorn, so
a mismatch is visible without digging a dead container's log out.

## 3. Fresh deployment

A fresh clone comes up with **two commands** — no manual `bench` work:

```bash
# 1. Copy environment reference and set real values.
#    MARIADB_ROOT_PASSWORD and ADMIN_PASSWORD are REQUIRED on a fresh host;
#    PRODUCTIX_APPS selects which apps to install - leave it unset to install
#    every app found under apps/, or set it to any subset such as
#    PRODUCTIX_APPS=productix_core
cp .env.example .env

# 2. Start the stack (background)
docker compose up -d
```

What happens automatically:

1. **configurator** (`docker/configurator.sh`) runs first. It aborts with an
   explicit message if `MARIADB_ROOT_PASSWORD`/`ADMIN_PASSWORD` are missing,
   and then **proves** the root password actually authenticates against
   MariaDB (`SELECT 1`) before any other service starts — a `.env` value that
   no longer matches the `db-data` volume therefore stops the stack with one
   readable message instead of coming up broken (see
   `tests/ACCEPTANCE_EVIDENCE.md` §15). A connection problem is retried
   against a deadline, because on a first boot MariaDB answers over its unix
   socket while still listening with `port: 0`; a *refused* password fails at
   once. It then writes the global bench config and links `sites/assets` to
   the shared assets volume.
2. **backend entrypoint** (`docker/backend-entrypoint.sh`) decides from the
   **state of the database**, never from the presence of a file. It asks for
   a verdict — `fresh`, `ok`, `reinstall` or `fatal:*` — by checking that the
   site's configuration exists, that its database exists, that the schema is
   non-empty, and that the site's own database credentials authenticate.

   The verdict alone does not decide the action: a site whose database
   *works* is not the same as a site that *finished installing*. A crash
   after `bench new-site` used to leave a database that verified `ok` for
   ever, so whatever had not been installed stayed missing on every boot.
   Two markers settle it:

   - `sites/.productix_started.<site>` — written before the first step;
   - `sites/<site>/.productix_install_complete` — written only after every
     step **and** every hook succeeded, together with
     `sites/<site>/.productix_hooks_done` (the hooks already run).

   Verdict + markers produce one of three modes:

   | Mode | When | What runs |
   |---|---|---|
   | `fresh` | no usable site | `new-site`, install the selection, migrate/build, run hooks |
   | `resume` | install started but never completed | finish the install, run the hooks still outstanding |
   | `sync` | install completed (or a pre-marker site, adopted as complete) | reconcile only: install the difference, migrate/build |

   In every mode the same selection rules from §2 apply. Reconciliation adds
   what is missing and reports — never removes — what is extra, so adding a
   module to `PRODUCTIX_APPS` later installs it on the next boot, and
   removing one only warns. `apps.txt` is rewritten as a **union** of the
   selection and what is already installed, so an app is never silently
   forgotten by Frappe.

   **`post_install` hooks run only while a site is being provisioned**
   (`fresh` / `resume`). A hook can re-seed — productix_recipe's wipes
   production data before re-creating the demo set — so it is never replayed
   automatically on a completed site. A module added to a finished site is
   installed *without* its hook, and the log prints the one-line command to
   run it deliberately. A hook that fails does not take the site down (the
   site is already verified), but it withholds the completion marker, so the
   failure is re-bannered on every boot until it is fixed.

3. It **re-verifies** the site and only then hands over to the image's
   `start.sh` (gunicorn). If verification fails gunicorn is deliberately not
   started: serving a database that cannot answer is exactly what used to
   turn one bad password into an endless HTTP 500/502. Just before handover
   it prints the module status (§2.1). Between those two steps it also forces
   `developer_mode` **off** — with it on, Frappe writes standard documents
   (Number Cards, Reports, DocTypes) back into the app source tree whenever
   they are saved, and that tree belongs to the host checkout, which the
   `frappe` user cannot write. It is re-asserted on **every** start rather
   than only during install, so a site created before this rule existed
   repairs itself on its next boot
   (`tests/ACCEPTANCE_EVIDENCE.md` §15.6).

> **Change `.env` → `docker compose up -d`, not `docker compose restart`.**
> `restart` re-uses the container that was created, and container settings
> are baked at `up` time — the old values of `.env` would keep applying
> silently. `up -d` re-interpolates and recreates what changed.

The verdicts, for when you are reading a log:

| Verdict | Meaning | Action |
|---|---|---|
| `fresh` | no site configuration yet | install |
| `ok` | configuration + database + non-empty schema + the site's own credentials all check out | resume if the install never finished, otherwise reconcile and start gunicorn |
| `reinstall` | half-created site: configuration present but no database, or an **empty** schema | drop the empty leftovers and rebuild (0 rows — nothing to lose) |
| `fatal:root-auth` | MariaDB refused `MARIADB_ROOT_PASSWORD` | stop, with the fix printed |
| `fatal:root-connect` | MariaDB unreachable | stop, pointing at `docker compose logs mariadb` |
| `fatal:site-auth` | the site's database holds data but its own credentials were refused even after repair | stop, printing the last error |

A refused *site* account on a database that **does** hold data is repaired
rather than reinstalled: `CREATE USER IF NOT EXISTS` + `ALTER USER` + `GRANT`
touch only accounts, never a table, so a rotated password heals itself on the
next restart.

The stack stops loudly rather than starting broken. Nothing here is tied to a
particular combination of apps — every decision above reads manifests and
database state, so any subset of the modules behaves identically.

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
- Productix bundles under `/assets/productix_*` are **real directories**
  written into the shared assets volume by `bench build` (the backend
  entrypoint removes any symlink an older layout left behind first). nginx
  only ever reads `sites/assets`, so the **frontend needs no app mounts at
  all** — see the `frontend` service volumes in `docker-compose.yml`.
- ⚠️ **Never mount `./apps` at `/home/frappe/frappe-bench/apps`.** That path
  already holds `frappe` and `erpnext` from the image, so an overlay would
  hide them. The module tree is mounted once at the staging path
  `/opt/productix-apps`, and `docker/productix-apps.sh` links each folder it
  finds into `apps/` at container start (also exporting `PYTHONPATH`).
  Likewise, do not mount `./apps/<app>` back into `apps/<app>`: the link
  must stay a **symlink created at runtime**, or a new module folder would
  require editing `docker-compose.yml` again.
- nginx resolves its upstreams **per request**, never at config load.
  `nginx.conf.template` routes through
  `set $backend_upstream __BACKEND_UPSTREAM__;` (rendered from the `BACKEND`
  env var at start-up) + `resolver 127.0.0.11 valid=5s`, not an
  `upstream { server backend:8000; }` block. The `upstream` form is resolved
  exactly once, when nginx reads its config, and Docker gives a recreated
  container a new IP — so a backend-only `docker compose up -d` would leave
  nginx proxying a dead address and **every dynamic route would 502 until
  someone restarted the frontend by hand**. With the variable form nginx
  re-resolves through Docker's embedded DNS within `valid=`, so a recreated
  backend is picked up on its own; it also no longer needs
  `backend`/`websocket` to be resolvable while it boots, so container start
  order cannot break it either.
  (Proven by occupying the backend's former IP with an unrelated container
  and confirming all routes still return 200 with the frontend untouched —
  see `tests/ACCEPTANCE_EVIDENCE.md` §14.5.)
- `docker/productix-apps.sh` is executed only after `tr -d '\r'`, exactly
  like the other entrypoints — compose strips CR first, so a CRLF checkout
  on Windows cannot break it.

Quick manual check after a deploy (must print 200 for every asset):

    docker cp tests/_verify_assets.py productix_erp-backend-1:/home/frappe/frappe-bench/_verify_assets.py
    docker compose exec backend bash -lc "/home/frappe/frappe-bench/env/bin/python /home/frappe/frappe-bench/_verify_assets.py"

### 4.2 Boot readiness (the 502 you get while the site builds itself)

On a **first** boot the backend deliberately does its slow work *before*
handing over to gunicorn — `bench new-site` → `bench build` →
`bench migrate` → compile translations. That is minutes of work, and the
frontend never used to wait for it:

- `docker-compose.yml` had `frontend.depends_on: backend` in the **short
  form**, which means `service_started`, not `service_healthy` — the frontend
  was released as soon as the backend *container* existed.
- `docker/frontend-entrypoint.sh` rendered the nginx config and
  `exec nginx` immediately, with no readiness check at all.

nginx therefore came up and served traffic while nothing was listening on
`:8000` → `connect() failed (111: Connection refused)` → **502 on every
request** for the whole build. `docker compose ps` still shows everything
green, and a boot-time 502 is visually identical to the two 502 causes this
repo already fixed (§14.5 stale container IP, §15 half-created site), which
is what makes it expensive to chase.

Two layers fix it.

**1. The gate — `docker/frontend-entrypoint.sh`.** Before `exec nginx` it
probes the backend in a loop and only releases nginx once the probe answers:

- The probe is **the same request the compose healthcheck makes**: ping with
  a `Host` header, because frappe resolves the *site* from that header.
  Without it a perfectly healthy backend answers `404` and reads as dead.
- The probe address is the `BACKEND` env var — the very value substituted
  into `__BACKEND_UPSTREAM__`, so the address nginx proxies to and the
  address the gate probes **cannot drift apart**.
- It runs for at most `FRONTEND_BACKEND_WAIT_SECONDS` (default `300`). On
  timeout nginx starts **anyway**, with a loud warning: a slow first boot is
  delayed, never blocked. `0` (or a non-numeric value) disables the wait.
- Missing/empty `BACKEND` or `SOCKETIO` is a hard, explanatory failure —
  refusing to boot beats serving a blank proxy target.
- After substitution the script refuses to start if any `__PLACEHOLDER__`
  survives, so nginx can never silently proxy to a literal
  `__BACKEND_UPSTREAM__`.

**2. The net — `nginx.conf.template`.** For a backend that dies *later*
(after nginx is already running):

```nginx
error_page 502 504 =503 /_warming_up;
```

`location = /_warming_up` is `internal`, serves a self-reloading
"starting up" page from `__WARMING_DIR__`, and adds `Retry-After: 5` +
`Cache-Control: no-store` (`always` — 503 is not in `add_header`'s default
status list). The result is a **503 that the browser retries on its own**
instead of a dead 502 that looks like a broken proxy. Only *connection-level*
failures take this path: `proxy_intercept_errors` stays off, so an error the
**application** returns is passed through untouched.

The page directory is resolved at container start (the image runs as uid
1000, so system paths such as `/opt` are read-only and `mkdir` there fails).
`FRONTEND_WARMING_DIR` is tried first and an unusable value falls back to
`/tmp` and `$HOME` rather than crash-looping.

**Why not `depends_on: condition: service_healthy`?** Because the backend
healthcheck's `start_period` is `900s`: on a first boot that would hold the
static assets back for the whole install. The short form is kept on purpose
and the gate waits only for gunicorn to actually serve — nginx comes up a few
seconds after the backend does, and immediately on every later boot.

Verification (both layers):

1. Gate — with the stack stopped, `docker compose up -d` and watch
   `docker compose logs -f frontend`: the `waiting up to …` line, then
   `backend is serving (after Ns) - starting nginx`, then **zero** 502s from
   the first request onward (the window before the fix was ~2 min 11 s).
2. Net — with the frontend *already running and never restarted*,
   `docker compose stop backend`, then request `/`, `/login`,
   `/api/method/ping`, `/app` and `/favicon.ico`: each must return
   **503 + `Retry-After: 5`** (was 502) and self-recover to 200 after
   `docker compose start backend`.

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
- `FRONTEND_BACKEND_WAIT_SECONDS` (default `300`), `FRONTEND_BACKEND_PROBE_PATH`
  (default `/api/method/ping`), `FRONTEND_BACKEND_PROBE_INTERVAL` (default
  `2`), `FRONTEND_WARMING_DIR` (default `/tmp/productix-warming`) — frontend
  boot readiness; see §4.2.

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