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
        # explicit selection from .env, e.g. PRODUCTIX_APPS=productix_core,productix_kpi
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

    case " $PRODUCTIX_APPS_LIST " in
        *" productix_recipe "*)
            echo "[backend] seeding recipe demo data"
            bench --site "$SITE" execute productix_recipe.setup_data.run
            ;;
    esac

    echo "[backend] initial setup complete"
fi

# Hand over to the image's default backend process (gunicorn).
echo "[backend] starting gunicorn"
exec /usr/local/bin/start.sh
