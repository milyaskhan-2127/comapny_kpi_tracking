#!/bin/sh
# ============================================================================
# Productix ERP - backend container entrypoint
#
#   1. ONCE, on a fresh deployment: create the site and install the selected
#      productix apps. Mirrors setup_site.sh so the stack comes up with zero
#      manual commands on any host.
#   2. ALWAYS: hand over to the image's start.sh (gunicorn).
#
# POSIX sh only - compose runs this with `sh`, and `set -o pipefail` (a bash
# feature) or `[[ ... ]]` would abort with `set: Illegal option`. Compose also
# strips CR before exec, so a Windows checkout cannot break this either.
# ============================================================================
set -eu

BENCH_DIR=/home/frappe/frappe-bench
SITE="${SITE_NAME:-productix.local}"
ENV_PIP="$BENCH_DIR/env/bin/pip"

cd "$BENCH_DIR"

# Link every module found under the source tree and build PYTHONPATH.
# Generic: docker/productix-apps.sh globs ./apps, so this file names no
# modules. Applied here as well as in the queue/scheduler entrypoint so the
# `bench` CLI, gunicorn and every worker see an identical import path.
if [ -f /usr/local/bin/productix-apps.sh ]; then
    tr -d '\r' < /usr/local/bin/productix-apps.sh > /tmp/productix-apps.sh
    # shellcheck disable=SC1091
    . /tmp/productix-apps.sh
fi

if [ -f "$BENCH_DIR/sites/$SITE/site_config.json" ]; then
    echo "[backend] site '$SITE' already exists - skipping setup"
else
    # -----------------------------------------------------------------------
    # credentials: without them `bench new-site` cannot run
    # -----------------------------------------------------------------------
    if [ -z "${MARIADB_ROOT_PASSWORD:-}" ] || [ -z "${ADMIN_PASSWORD:-}" ]; then
        echo "[backend] ERROR: site '$SITE' does not exist yet and the credentials" >&2
        echo "           MARIADB_ROOT_PASSWORD / ADMIN_PASSWORD are not set in .env." >&2
        echo "           Copy .env.example to .env, fill it in, then run 'docker compose up -d' again." >&2
        exit 1
    fi

    # -----------------------------------------------------------------------
    # app discovery (same rules as setup_site.sh)
    # -----------------------------------------------------------------------
    PLATFORM_APP=""
    DISCOVERED_APPS=""
    for manifest in "$BENCH_DIR"/apps/productix_*/productix_*/productix_module.json; do
        [ -f "$manifest" ] || continue
        app=$(basename "$(dirname "$(dirname "$manifest")")")
        if grep -qE '"always_enabled"[[:space:]]*:[[:space:]]*true' "$manifest"; then
            PLATFORM_APP="$app"
        else
            DISCOVERED_APPS="$DISCOVERED_APPS $app"
        fi
    done

    if [ -n "${PRODUCTIX_APPS:-}" ]; then
        # explicit selection from .env - see the module-selection block in
        # .env.example for the format and for examples of every valid shape
        PRODUCTIX_APPS_LIST=$(printf '%s' "$PRODUCTIX_APPS" | tr ',' ' ')
    else
        PRODUCTIX_APPS_LIST="$DISCOVERED_APPS"
    fi

    # the platform app (manifest flagged always_enabled) is never optional
    if [ -n "$PLATFORM_APP" ]; then
        case " $PRODUCTIX_APPS_LIST " in
            *" $PLATFORM_APP "*) ;;
            *) PRODUCTIX_APPS_LIST="$PLATFORM_APP $PRODUCTIX_APPS_LIST" ;;
        esac
    fi

    # shellcheck disable=SC2086
    set -- $PRODUCTIX_APPS_LIST
    if [ "$#" -eq 0 ]; then
        echo "[backend] ERROR: no productix apps discovered under $BENCH_DIR/apps" >&2
        echo "           and PRODUCTIX_APPS is empty." >&2
        exit 1
    fi

    # A selection that is not on this host must fail HERE, listing what IS
    # available, rather than deep inside `pip install` on a half-built site.
    PRODUCTIX_MISSING=""
    for app in "$@"; do
        [ -d "$BENCH_DIR/apps/$app" ] || PRODUCTIX_MISSING="$PRODUCTIX_MISSING $app"
    done
    if [ -n "$PRODUCTIX_MISSING" ]; then
        echo "[backend] ERROR: PRODUCTIX_APPS selected modules that are not present:$PRODUCTIX_MISSING" >&2
        echo "           Modules available under $BENCH_DIR/apps:" >&2
        for candidate in "$BENCH_DIR"/apps/productix_*; do
            [ -d "$candidate" ] || continue
            echo "             ${candidate##*/}" >&2
        done
        echo "           Fix PRODUCTIX_APPS in .env, or drop the missing folder into apps/." >&2
        exit 1
    fi

    echo "[backend] ========================================"
    echo "[backend] installing:$PRODUCTIX_APPS_LIST"
    echo "[backend] ========================================"

    # bench resolves apps through sites/apps.txt - write it before new-site,
    # exactly like setup_site.sh does.
    {
        printf 'frappe\nerpnext\n'
        for app in "$@"; do printf '%s\n' "$app"; done
    } > "$BENCH_DIR/sites/apps.txt"

    for app in "$@"; do
        "$ENV_PIP" install -e "$BENCH_DIR/apps/$app" --quiet
    done

    echo "[backend] creating site '$SITE'"
    bench new-site "$SITE" \
        --mariadb-root-password "$MARIADB_ROOT_PASSWORD" \
        --admin-password "$ADMIN_PASSWORD" \
        --no-mariadb-socket \
        --force

    echo "[backend] installing erpnext"
    bench --site "$SITE" install-app erpnext

    for app in "$@"; do
        echo "[backend] installing $app"
        bench --site "$SITE" install-app "$app" --force
    done

    # `bench build` must materialise a REAL directory at sites/assets/<app>.
    # A symlink left behind by an older layout would send the bundles back
    # into the bind-mounted source tree instead of the shared assets volume.
    for app in "$@"; do
        if [ -L "$BENCH_DIR/sites/assets/$app" ]; then
            rm -f "$BENCH_DIR/sites/assets/$app"
        fi
    done

    echo "[backend] migrating and building assets"
    bench --site "$SITE" set-config developer_mode 1
    bench --site "$SITE" migrate
    bench --site "$SITE" clear-cache
    bench build --hard-link

    # -----------------------------------------------------------------------
    # Optional per-module post-install hook, declared by the module itself:
    #     "post_install": "<dotted.path.callable>"
    # Generic by design - any module (present or future) can seed data by
    # adding one field to its own manifest. This script never names an app.
    # Hooks run in install order (platform app first), one per module.
    # -----------------------------------------------------------------------
    for app in "$@"; do
        for manifest in "$BENCH_DIR"/apps/"$app"/*/productix_module.json; do
            [ -f "$manifest" ] || continue
            hook=$(sed -n 's/^[[:space:]]*"post_install"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$manifest")
            [ -n "$hook" ] || continue
            echo "[backend] running post_install hook for $app: $hook"
            bench --site "$SITE" execute "$hook"
        done
    done

    echo "[backend] initial setup complete"
fi

# Hand over to the image's default backend process (gunicorn).
echo "[backend] starting gunicorn"
exec /usr/local/bin/start.sh
