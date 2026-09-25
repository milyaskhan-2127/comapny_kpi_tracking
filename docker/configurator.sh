#!/bin/sh
# ============================================================================
# Productix ERP - configurator (one-shot, runs before every other service)
#
# Every other service declares `depends_on: configurator:
# condition: service_completed_successfully`, so this is the first thing that
# touches a fresh deployment. It therefore has to:
#
#   1. fail FAST with a readable message when .env is incomplete - otherwise
#      the backend exits and `restart: unless-stopped` turns one missing
#      variable into an endless, hard-to-diagnose restart loop;
#   2. write the global bench configuration (db / redis / default site);
#   3. make `sites/assets` point at the shared assets volume.
#
# Idempotent. POSIX sh only - no bashisms, no `pipefail`, safe under /bin/sh
# on any host. Compose strips CR before exec (see docker-compose.yml), so a
# Windows checkout cannot break this either.
# ============================================================================
set -eu

BENCH_DIR=/home/frappe/frappe-bench
SITE="${SITE_NAME:-productix.local}"
ASSETS_LINK="$BENCH_DIR/sites/assets"
SHARED_ASSETS="$BENCH_DIR/assets"

cd "$BENCH_DIR"

# ---------------------------------------------------------------------------
# 1. credentials - read from the environment, never hard-coded
# ---------------------------------------------------------------------------
if [ -z "${MARIADB_ROOT_PASSWORD:-}" ]; then
    echo "ERROR: MARIADB_ROOT_PASSWORD is not set." >&2
    echo "       Copy .env.example to .env, set MARIADB_ROOT_PASSWORD and ADMIN_PASSWORD," >&2
    echo "       then run 'docker compose up -d' again." >&2
    exit 1
fi

if [ ! -f "$BENCH_DIR/sites/$SITE/site_config.json" ] && [ -z "${ADMIN_PASSWORD:-}" ]; then
    echo "ERROR: site '$SITE' does not exist yet and ADMIN_PASSWORD is not set." >&2
    echo "       Copy .env.example to .env, set ADMIN_PASSWORD and MARIADB_ROOT_PASSWORD," >&2
    echo "       then run 'docker compose up -d' again." >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# 2. global bench configuration
# ---------------------------------------------------------------------------
bench set-config -g db_host mariadb
bench set-config -gp db_port 3306
bench set-config -g redis_cache redis://redis-cache:6379
bench set-config -g redis_queue redis://redis-queue:6379
bench set-config -g redis_socketio redis://redis-queue:6379
bench set-config -gp socketio_port 9000
bench set-config -g default_site "$SITE"
bench set-config -g allow_cors "*"

# ---------------------------------------------------------------------------
# 3. sites/assets -> shared assets volume
# ---------------------------------------------------------------------------
# The image's own /usr/local/bin/entrypoint.sh does exactly this for every
# other container, but the configurator *replaces* that entrypoint, so the
# link has to be created here or a fresh deployment has no sites/assets at
# all when the first service starts.
#
# IMPORTANT: the `assets` volume is mounted at $SHARED_ASSETS, NOT at
# $ASSETS_LINK. Mounting it at $ASSETS_LINK makes it a mount point and the
# image entrypoint's `rm -rf` then fails with "Device or resource busy",
# which crashes backend + frontend in an endless restart loop.
mkdir -p "$BENCH_DIR/sites"
if [ -L "$ASSETS_LINK" ]; then
    rm -f "$ASSETS_LINK"
elif [ -d "$ASSETS_LINK" ]; then
    rm -rf "$ASSETS_LINK"
fi
ln -s "$SHARED_ASSETS" "$ASSETS_LINK"

# frappe/erpnext must be REAL directories inside the shared volume so that
# (a) nginx serves the built bundles and (b) `bench build` output written
# under sites/assets is visible to the frontend container. Replace a symlink
# leaked by an older layout with a real copy (no-op when already a directory).
for app in frappe erpnext; do
    if [ -L "$SHARED_ASSETS/$app" ]; then
        rm -f "$SHARED_ASSETS/$app"
        cp -a "$BENCH_DIR/apps/$app/$app/public" "$SHARED_ASSETS/$app" || true
    fi
done

# node_modules must be reachable from inside the app trees.
ln -sfn "$BENCH_DIR/apps/frappe/node_modules" \
    "$BENCH_DIR/apps/frappe/frappe/public/node_modules" || true
ln -sfn "$BENCH_DIR/apps/erpnext/node_modules" \
    "$BENCH_DIR/apps/erpnext/erpnext/public/node_modules" || true

# NOTE: the productix apps deliberately get NO asset link here.
# `bench build` materialises sites/assets/<app> as a real directory - which is
# what the long-running deployment does. Symlinking them instead would make
# `bench build` write its bundles back into the bind-mounted source tree.
# productix_instruction ships no public/ assets, so it never gets one either.

echo "[configurator] ready (site=$SITE)"
