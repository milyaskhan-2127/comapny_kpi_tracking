#!/bin/sh
# ============================================================================
# Productix ERP - configurator (one-shot, runs before every other service)
#
# Every other service declares `depends_on: configurator:
# condition: service_completed_successfully`, so this is the first thing that
# touches a fresh deployment. It therefore has to:
#
#   1. fail FAST with a readable message when .env is incomplete OR when
#      MARIADB_ROOT_PASSWORD does not actually authenticate against MariaDB -
#      otherwise the backend exits and `restart: unless-stopped` turns one bad
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

# Link the module source tree into the bench. docker/productix-apps.sh
# discovers whatever is under ./apps and exports PYTHONPATH - this script
# names no modules. Needed here too, because `bench` imports the commands
# module of every app listed in sites/apps.txt.
if [ -f /usr/local/bin/productix-apps.sh ]; then
    tr -d '\r' < /usr/local/bin/productix-apps.sh > /tmp/productix-apps.sh
    # shellcheck disable=SC1091
    . /tmp/productix-apps.sh
fi

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
# 1b. MARIADB_ROOT_PASSWORD has to WORK, not merely be set.
#
# Checked here - before any other service starts - because a wrong-but-set
# password used to pass every check, let the whole stack come up, and only
# surface minutes later as HTTP 500/502 from the backend while `bench
# new-site` died half way through (see docker/backend-entrypoint.sh, which
# verifies the *site's* database on every start; this is its mirror image,
# checking the root account the setup depends on).
#
# MariaDB's own healthcheck cannot do this: `mysqladmin ping` exits 0 even
# when it is refused ("the server is running" is all it answers), so an
# accepted-looking `healthy` state proves nothing about the password.
#
# Two different outcomes, deliberately treated differently:
#
#   REFUSED password  -> fail at once. That is the failure this check exists
#                        for, and waiting would only delay the message.
#   UNREACHABLE host  -> retry against a deadline. On a brand-new deployment
#                        MariaDB runs a temporary server while it initialises
#                        the data directory: it already answers over the unix
#                        socket (so the healthcheck goes green) but is still
#                        listening with `port: 0`, i.e. not yet on 3306. A
#                        fixed sleep would either lose the race or stall every
#                        start, so we wait for the real listener instead.
# ---------------------------------------------------------------------------
DB_HOST="${DB_HOST:-mariadb}"
DB_PORT="${DB_PORT:-3306}"
DB_READY_TIMEOUT="${DB_READY_TIMEOUT:-180}"
DB_ERR=/tmp/productix-configurator.err
DB_DEADLINE=$(( $(date +%s) + DB_READY_TIMEOUT ))

while :; do
    if MYSQL_PWD="$MARIADB_ROOT_PASSWORD" mysql -h "$DB_HOST" -P "$DB_PORT" -u root \
        --connect-timeout=10 --batch --skip-column-names -e "SELECT 1" \
        >/dev/null 2>"$DB_ERR"; then
        rm -f "$DB_ERR"
        break
    fi

    err=$(cat "$DB_ERR" 2>/dev/null || true)

    case "$err" in
    *"Access denied"*)
        rm -f "$DB_ERR"
        echo "ERROR: MARIADB_ROOT_PASSWORD was rejected by MariaDB ($DB_HOST)." >&2
        echo "       The db-data volume keeps the password it was initialised with, so editing" >&2
        echo "       .env alone does not change it - .env and that volume now disagree." >&2
        echo "       Fix: set MARIADB_ROOT_PASSWORD in .env to the password the volume uses." >&2
        echo "       On a host whose data you can lose you may instead start over with" >&2
        echo "       'docker compose down -v' - that DESTROYS the database." >&2
        exit 1
        ;;
    esac

    if [ "$(date +%s)" -ge "$DB_DEADLINE" ]; then
        rm -f "$DB_ERR"
        echo "ERROR: MariaDB at $DB_HOST:$DB_PORT did not accept TCP within ${DB_READY_TIMEOUT}s: $err" >&2
        echo "       Check 'docker compose ps' and 'docker compose logs mariadb'." >&2
        exit 1
    fi

    echo "[configurator] waiting for MariaDB at $DB_HOST:$DB_PORT to accept TCP connections..."
    sleep 5
done
rm -f "$DB_ERR"

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
# A module that ships no public/ assets simply gets no directory at all.

echo "[configurator] ready (site=$SITE)"
