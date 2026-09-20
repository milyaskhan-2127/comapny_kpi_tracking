#!/bin/bash
# Productix ERP - Site Setup Script
# Run this ONCE after first docker-compose up to create the site and install apps.

set -e
export MSYS_NO_PATHCONV=1

SITE_NAME="${SITE_NAME:-productix.local}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-Admin@123}"
MARIADB_ROOT_PASSWORD="${MARIADB_ROOT_PASSWORD:-change_me_strong_password_123}"

echo "========================================"
echo "  Productix ERP — Site Initialization"
echo "========================================"

# Wait for containers
echo "[1/6] Waiting for backend and mariadb containers..."
sleep 5

# Set common bench configuration
echo "[2/6] Configuring global bench settings & installing productix..."
docker compose exec -e MSYS_NO_PATHCONV=1 backend bash -c "
  cd /home/frappe/frappe-bench && \
  bench set-config -g db_host mariadb && \
  bench set-config -gp db_port 3306 && \
  bench set-config -g redis_cache redis://redis-cache:6379 && \
  bench set-config -g redis_queue redis://redis-queue:6379 && \
  bench set-config -g redis_socketio redis://redis-queue:6379 && \
  bench set-config -gp socketio_port 9000 && \
  bench set-config -g default_site $SITE_NAME && \
  grep -q productix /home/frappe/frappe-bench/sites/apps.txt 2>/dev/null || printf 'frappe\nerpnext\nproductix\n' > /home/frappe/frappe-bench/sites/apps.txt && \
  /home/frappe/frappe-bench/env/bin/pip install -e apps/productix --quiet && \
  bench build --app productix 2>/dev/null || true
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

# Install Productix
echo "[5/6] Installing Productix..."
docker compose exec -e MSYS_NO_PATHCONV=1 backend bash -c "
  cd /home/frappe/frappe-bench && \
  bench --site $SITE_NAME install-app productix --force
"

# Run migrations & build
echo "[6/6] Running migrations, build, assets sync, and demo data..."
docker compose exec -e MSYS_NO_PATHCONV=1 backend bash -c "
  cd /home/frappe/frappe-bench && \
  bench --site $SITE_NAME set-config developer_mode 1 && \
  bench --site $SITE_NAME migrate && \
  bench --site $SITE_NAME clear-cache && \
  bench build --hard-link && \
  bench --site $SITE_NAME execute productix.setup_data.run
"

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
