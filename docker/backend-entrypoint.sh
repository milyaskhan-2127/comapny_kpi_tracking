#!/bin/bash
# Backend entrypoint — auto-initializes site if missing, then starts gunicorn
set -euo pipefail

SITE_NAME="${SITE_NAME:-productix.local}"
BENCH_DIR="/home/frappe/frappe-bench"

echo "[entrypoint] Starting backend for site: $SITE_NAME"

# Ensure bench is configured (configurator should have done this, but be safe)
if [ ! -f "$BENCH_DIR/sites/common_site_config.json" ]; then
    echo "[entrypoint] Configuring bench..."
    bench set-config -g db_host mariadb
    bench set-config -gp db_port 3306
    bench set-config -g redis_cache redis://redis-cache:6379
    bench set-config -g redis_queue redis://redis-queue:6379
    bench set-config -g redis_socketio redis://redis-queue:6379
    bench set-config -gp socketio_port 9000
    bench set-config -g default_site "$SITE_NAME"
    bench set-config -g allow_cors "*"
fi

# Ensure assets symlinks exist (idempotent)
ln -sfn /home/frappe/frappe-bench/apps/productix_core/productix_core/public /home/frappe/frappe-bench/sites/assets/productix_core
ln -sfn /home/frappe/frappe-bench/apps/productix_recipe/productix_recipe/public /home/frappe/frappe-bench/sites/assets/productix_recipe
ln -sfn /home/frappe/frappe-bench/apps/productix_kpi/productix_kpi/public /home/frappe/frappe-bench/sites/assets/productix_kpi

# Check if site exists
if [ ! -f "$BENCH_DIR/sites/$SITE_NAME/site_config.json" ]; then
    echo "[entrypoint] Site '$SITE_NAME' not found — running initial setup..."
    
    # Discover apps to install (same logic as setup_site.sh)
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

    PRODUCTIX_APPS_LIST=("${DISCOVERED_APPS[@]}")
    if [ -n "$PLATFORM_APP" ]; then
        PRODUCTIX_APPS_LIST=("$PLATFORM_APP" "${PRODUCTIX_APPS_LIST[@]}")
    fi

    echo "[entrypoint] Installing apps: ${PRODUCTIX_APPS_LIST[*]}"

    # Install apps in editable mode
    for app in "${PRODUCTIX_APPS_LIST[@]}"; do
        pip install -e "apps/$app" --quiet
    done

    # Create site
    echo "[entrypoint] Creating site: $SITE_NAME"
    bench new-site "$SITE_NAME" \
        --mariadb-root-password "$MARIADB_ROOT_PASSWORD" \
        --admin-password "$ADMIN_PASSWORD" \
        --no-mariadb-socket \
        --force

    # Install ERPNext
    echo "[entrypoint] Installing ERPNext..."
    bench --site "$SITE_NAME" install-app erpnext

    # Install Productix apps
    for app in "${PRODUCTIX_APPS_LIST[@]}"; do
        echo "[entrypoint] Installing $app..."
        bench --site "$SITE_NAME" install-app "$app" --force
    done

    # Run migrations and build
    echo "[entrypoint] Running migrations and building assets..."
    bench --site "$SITE_NAME" set-config developer_mode 1
    bench --site "$SITE_NAME" migrate
    bench --site "$SITE_NAME" clear-cache
    bench build --hard-link

    # Seed demo data if recipe module installed
    if [[ " ${PRODUCTIX_APPS_LIST[*]} " =~ " productix_recipe " ]]; then
        echo "[entrypoint] Seeding demo data (recipe module)..."
        bench --site "$SITE_NAME" execute productix_recipe.setup_data.run
    fi

    echo "[entrypoint] Initial setup complete!"
else
    echo "[entrypoint] Site '$SITE_NAME' already exists — skipping setup"
fi

# Start gunicorn (default command from frappe/erpnext image)
echo "[entrypoint] Starting gunicorn..."
exec /usr/local/bin/bench start