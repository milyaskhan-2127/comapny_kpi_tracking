#!/bin/bash
# Productix ERP - Site Setup Script
# Run this ONCE after first docker-compose up to create the site and install
# the selected productix apps.
#
# Module selection:
#   PRODUCTIX_APPS="productix_core,productix_recipe"   # install subset
#   (default: every app discovered via its productix_module.json manifest;
#    the platform app — manifest flagged "always_enabled" — is installed first)

set -e
export MSYS_NO_PATHCONV=1

# The rules AND the .env reader are shared with the Docker bootstrap, so a
# manual setup and `docker compose up` cannot resolve the same PRODUCTIX_APPS
# to two different lists. Relative to this script, so it works from anywhere.
# shellcheck source=docker/productix-selection.sh
. "$(dirname "$0")/docker/productix-selection.sh"

# .env is this deployment's configuration file. Compose reads it for the
# container path; this script used to ignore it completely, which is why a
# PRODUCTIX_APPS=... written in .env installed one set of modules when you
# ran `docker compose up` and a different set when you ran this.
# An exported variable still wins, so one-shot overrides keep working.
productix_load_dotenv "$(dirname "$0")/.env"

SITE_NAME="${SITE_NAME:-productix.local}"

# Production safety: if PRODUCTION=1, require explicit credentials via env vars.
# For local development, defaults are allowed but a warning is shown.
if [ "${PRODUCTION:-0}" = "1" ]; then
    if [ -z "${ADMIN_PASSWORD:-}" ]; then
        echo "ERROR: PRODUCTION=1 requires ADMIN_PASSWORD to be set in environment" >&2
        exit 1
    fi
    if [ -z "${MARIADB_ROOT_PASSWORD:-}" ]; then
        echo "ERROR: PRODUCTION=1 requires MARIADB_ROOT_PASSWORD to be set in environment" >&2
        exit 1
    fi
else
    if [ -z "${ADMIN_PASSWORD:-}" ]; then
        ADMIN_PASSWORD="Admin@123"
        echo "WARNING: Using default ADMIN_PASSWORD ('Admin@123'). Set ADMIN_PASSWORD env var or PRODUCTION=1 for production." >&2
    fi
    if [ -z "${MARIADB_ROOT_PASSWORD:-}" ]; then
        MARIADB_ROOT_PASSWORD="change_me_strong_password_123"
        echo "WARNING: Using default MARIADB_ROOT_PASSWORD. Set MARIADB_ROOT_PASSWORD env var or PRODUCTION=1 for production." >&2
    fi
fi

# Module selection is NOT decided here. It is resolved by the shared rules
# in docker/productix-selection.sh (discovery from each module's own
# productix_module.json, the always_enabled platform app, and the transitive
# `requires` of whatever you selected), so this script installs exactly what
# the Docker bootstrap would install for the same .env.
px_select "apps" "${PRODUCTIX_APPS:-}"

PRODUCTIX_APPS_LIST=()
for _pxa in $PX_SELECTION; do
    PRODUCTIX_APPS_LIST+=("$_pxa")
done

if [ ${#PRODUCTIX_APPS_LIST[@]} -eq 0 ]; then
    echo "ERROR: no productix apps discovered under apps/ — run from the repo root or set PRODUCTIX_APPS."
    exit 1
fi

# A module that was named but is not in this checkout has to fail HERE,
# listing what IS available, rather than deep inside `bench install-app` on a
# half-created site.
if [ -n "$PX_UNAVAILABLE" ]; then
    echo "ERROR: PRODUCTIX_APPS selected modules that are not present:$PX_UNAVAILABLE" >&2
    echo "        Modules available under apps/:" >&2
    for _pxd in apps/productix_*; do
        [ -d "$_pxd" ] || continue
        echo "          ${_pxd##*/}" >&2
    done
    echo "        Fix PRODUCTIX_APPS in .env, or drop the missing folder into apps/." >&2
    exit 1
fi

if [ -n "$PX_PLATFORM_APP" ] && [ -n "$PX_REQUESTED" ] && ! px_list_has "$PX_REQUESTED" "$PX_PLATFORM_APP"; then
    echo "NOTE: $PX_PLATFORM_APP is the platform — added automatically."
fi

# A manifest can point at a module this checkout does not carry: loud, but
# not fatal - stopping here would take down an otherwise usable deployment.
if [ -n "$PX_DEP_GAPS" ]; then
    echo "WARNING: a module declares 'requires' an app that is not in apps/:$PX_DEP_GAPS" >&2
fi

echo "========================================"
echo "  Productix ERP — Site Initialization"
echo "  Apps: ${PRODUCTIX_APPS_LIST[*]}"
echo "========================================"

# Wait for containers
echo "[1/6] Waiting for backend and mariadb containers..."
sleep 5

PIP_INSTALLS=""
BUILDS=""
APPS_TXT="frappe\nerpnext\n"
for app in "${PRODUCTIX_APPS_LIST[@]}"; do
    PIP_INSTALLS="${PIP_INSTALLS} && /home/frappe/frappe-bench/env/bin/pip install -e apps/${app} --quiet"
    BUILDS="${BUILDS} && bench build --app ${app} 2>/dev/null || true"
    APPS_TXT="${APPS_TXT}${app}\n"
done

# Set common bench configuration and install productix apps
echo "[2/6] Configuring global bench settings & installing productix apps..."
docker compose exec -e MSYS_NO_PATHCONV=1 backend bash -c "
  cd /home/frappe/frappe-bench && \
  bench set-config -g db_host mariadb && \
  bench set-config -gp db_port 3306 && \
  bench set-config -g redis_cache redis://redis-cache:6379 && \
  bench set-config -g redis_queue redis://redis-queue:6379 && \
  bench set-config -g redis_socketio redis://redis-queue:6379 && \
  bench set-config -gp socketio_port 9000 && \
  bench set-config -g default_site $SITE_NAME && \
  printf '$APPS_TXT' > /home/frappe/frappe-bench/sites/apps.txt && \
  ${PIP_INSTALLS# && } && \
  ${BUILDS# && }
"

# Create new site
echo "[3/6] Creating site: $SITE_NAME ..."
docker compose exec -e MSYS_NO_PATHCONV=1 backend bash -c "
  cd /home/frappe/frappe-bench && \
  bench new-site $SITE_NAME \
    --mariadb-root-password '$MARIADB_ROOT_PASSWORD' \
    --admin-password '$ADMIN_PASSWORD' \
    --no-mariadb-socket \
    --force
"

# Install ERPNext
echo "[4/6] Installing ERPNext..."
docker compose exec -e MSYS_NO_PATHCONV=1 backend bash -c "
  cd /home/frappe/frappe-bench && \
  bench --site $SITE_NAME install-app erpnext
"

# Install Productix apps
echo "[5/6] Installing Productix apps..."
for app in "${PRODUCTIX_APPS_LIST[@]}"; do
    echo "    -> installing $app"
    docker compose exec -e MSYS_NO_PATHCONV=1 backend bash -c "
      cd /home/frappe/frappe-bench && \
      bench --site $SITE_NAME install-app $app --force
    "
done

# Run migrations & build
echo "[6/6] Running migrations, build, assets sync..."
docker compose exec -e MSYS_NO_PATHCONV=1 backend bash -c "
  cd /home/frappe/frappe-bench && \
  bench --site $SITE_NAME set-config developer_mode 0 && \
  bench --site $SITE_NAME migrate && \
  bench --site $SITE_NAME clear-cache && \
  bench build --hard-link
"

# Optional per-module post-install hook, declared by the module itself:
#     "post_install": "<dotted.path.callable>"
# Generic - any module can seed data by adding one field to its own manifest;
# this script never names an app. Hooks run in install order (platform first).
for app in "${PRODUCTIX_APPS_LIST[@]}"; do
    for manifest in "apps/$app"/*/productix_module.json; do
        [ -f "$manifest" ] || continue
        hook=$(px_manifest_get "$manifest" post_install)
        [ -n "$hook" ] || continue
        echo "    Running post_install hook for $app: $hook"
        docker compose exec -e MSYS_NO_PATHCONV=1 backend bash -c "
          cd /home/frappe/frappe-bench && \
          bench --site $SITE_NAME execute $hook
        "
    done
done

# Restart background services and frontend
echo "Restarting services to ensure all workers sync with new site..."
docker compose restart websocket queue-short queue-long scheduler frontend

echo ""
echo "========================================"
echo "  Setup Complete!"
echo "  URL: http://localhost:8080"
echo "  Username: Administrator"
echo "  Password: $ADMIN_PASSWORD"
echo "========================================"