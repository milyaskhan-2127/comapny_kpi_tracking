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

# Discover modular apps from their manifests (no hard-coded app list).
PLATFORM_APP=""
DISCOVERED_APPS=()
for manifest in apps/productix_*/productix_*/productix_module.json; do
    [ -f "$manifest" ] || continue
    app=$(basename "$(dirname "$(dirname "$manifest")")")
    if grep -qE '"always_enabled"[[:space:]]*:[[:space:]]*true' "$manifest"; then
        PLATFORM_APP="$app"
    else
        DISCOVERED_APPS+=("$app")
    fi
done

if [ -n "$PRODUCTIX_APPS" ]; then
    IFS=', ' read -r -a PRODUCTIX_APPS_LIST <<< "$PRODUCTIX_APPS"
else
    PRODUCTIX_APPS_LIST=("${DISCOVERED_APPS[@]}")
fi

HAS_PLATFORM=0
for app in "${PRODUCTIX_APPS_LIST[@]}"; do
    [ "$app" = "$PLATFORM_APP" ] && HAS_PLATFORM=1
done
if [ -n "$PLATFORM_APP" ] && [ "$HAS_PLATFORM" = "0" ]; then
    PRODUCTIX_APPS_LIST=("$PLATFORM_APP" "${PRODUCTIX_APPS_LIST[@]}")
    echo "NOTE: $PLATFORM_APP is the platform — added automatically."
    HAS_PLATFORM=1
fi

if [ ${#PRODUCTIX_APPS_LIST[@]} -eq 0 ]; then
    echo "ERROR: no productix apps discovered under apps/ — run from the repo root or set PRODUCTIX_APPS."
    exit 1
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
        hook=$(sed -n 's/^[[:space:]]*"post_install"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$manifest")
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