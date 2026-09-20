# Productix ERP - Site Setup Script for Windows PowerShell
# Run this once to initialize the site and install apps

$SITE_NAME = if ($env:SITE_NAME) { $env:SITE_NAME } else { "productix.local" }
$ADMIN_PASSWORD = if ($env:ADMIN_PASSWORD) { $env:ADMIN_PASSWORD } else { "Admin@123" }
$MARIADB_ROOT_PASSWORD = if ($env:MARIADB_ROOT_PASSWORD) { $env:MARIADB_ROOT_PASSWORD } else { "change_me_strong_password_123" }

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Productix ERP — Site Initialization" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n[1/5] Configuring global bench settings & installing productix..." -ForegroundColor Yellow
docker compose exec backend bash -c "cd /home/frappe/frappe-bench && bench set-config -g db_host mariadb && bench set-config -gp db_port 3306 && bench set-config -g redis_cache redis://redis-cache:6379 && bench set-config -g redis_queue redis://redis-queue:6379 && bench set-config -g redis_socketio redis://redis-queue:6379 && bench set-config -gp socketio_port 9000 && bench set-config -g default_site $SITE_NAME && grep -q productix /home/frappe/frappe-bench/sites/apps.txt 2>/dev/null || printf 'frappe\nerpnext\nproductix\n' > /home/frappe/frappe-bench/sites/apps.txt && /home/frappe/frappe-bench/env/bin/pip install -e apps/productix --quiet && bench build --app productix 2>/dev/null || true"

Write-Host "`n[2/5] Creating site: $SITE_NAME ..." -ForegroundColor Yellow
docker compose exec backend bash -c "cd /home/frappe/frappe-bench && bench new-site $SITE_NAME --mariadb-root-password '$MARIADB_ROOT_PASSWORD' --admin-password '$ADMIN_PASSWORD' --no-mariadb-socket --force"

Write-Host "`n[3/5] Installing ERPNext..." -ForegroundColor Yellow
docker compose exec backend bash -c "cd /home/frappe/frappe-bench && bench --site $SITE_NAME install-app erpnext"

Write-Host "`n[4/5] Installing Productix..." -ForegroundColor Yellow
docker compose exec backend bash -c "cd /home/frappe/frappe-bench && bench --site $SITE_NAME install-app productix --force"

Write-Host "`n[5/5] Running migrations, build, assets sync, and demo data..." -ForegroundColor Yellow
docker compose exec backend bash -c "cd /home/frappe/frappe-bench && bench --site $SITE_NAME set-config developer_mode 1 && bench --site $SITE_NAME migrate && bench --site $SITE_NAME clear-cache && bench build --hard-link && bench --site $SITE_NAME execute productix.setup_data.run"

Write-Host "`nRestarting services..." -ForegroundColor Yellow
docker compose restart websocket queue-short queue-long scheduler frontend

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "  Setup Complete!" -ForegroundColor Green
Write-Host "  URL: http://localhost:8080" -ForegroundColor Green
Write-Host "  Username: Administrator" -ForegroundColor Green
Write-Host "  Password: $ADMIN_PASSWORD" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
