# Quick deploy script for updates (migrate + clear-cache + build assets)
$SITE_NAME = if ($env:SITE_NAME) { $env:SITE_NAME } else { "productix.local" }

Write-Host "Deploying updates to $SITE_NAME ..." -ForegroundColor Yellow
docker compose exec backend bash -c "cd /home/frappe/frappe-bench && /home/frappe/frappe-bench/env/bin/pip install -e apps/productix --quiet && bench --site $SITE_NAME migrate && bench --site $SITE_NAME clear-cache && mkdir -p sites/assets/frappe sites/assets/erpnext sites/assets/productix && cp -rn apps/frappe/frappe/public/* sites/assets/frappe/ && cp -rn apps/erpnext/erpnext/public/* sites/assets/erpnext/ && cp -rn apps/productix/productix/public/* sites/assets/productix/ 2>/dev/null || true"

Write-Host "Restarting background workers and frontend..." -ForegroundColor Yellow
docker compose restart websocket queue-short queue-long scheduler frontend

Write-Host "Done." -ForegroundColor Green
