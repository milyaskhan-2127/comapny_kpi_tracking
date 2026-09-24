# Productix ERP - Site Setup Script for Windows PowerShell
# Run this once to initialize the site and install the selected productix apps.
#
# Module selection:
#   $env:PRODUCTIX_APPS = "productix_core,productix_recipe"   # install subset
#   (default: every app discovered via its productix_module.json manifest;
#    the platform app - manifest flagged "always_enabled" - is installed first)

$SITE_NAME = if ($env:SITE_NAME) { $env:SITE_NAME } else { "productix.local" }

# Production safety: if PRODUCTION=1, require explicit credentials via env vars.
# For local development, defaults are allowed but a warning is shown.
if ($env:PRODUCTION -eq "1") {
    if (-not $env:ADMIN_PASSWORD) {
        Write-Error "ERROR: PRODUCTION=1 requires ADMIN_PASSWORD to be set in environment"
        exit 1
    }
    if (-not $env:MARIADB_ROOT_PASSWORD) {
        Write-Error "ERROR: PRODUCTION=1 requires MARIADB_ROOT_PASSWORD to be set in environment"
        exit 1
    }
    $ADMIN_PASSWORD = $env:ADMIN_PASSWORD
    $MARIADB_ROOT_PASSWORD = $env:MARIADB_ROOT_PASSWORD
} else {
    if (-not $env:ADMIN_PASSWORD) {
        $ADMIN_PASSWORD = "Admin@123"
        Write-Warning "Using default ADMIN_PASSWORD ('Admin@123'). Set ADMIN_PASSWORD env var or PRODUCTION=1 for production."
    } else {
        $ADMIN_PASSWORD = $env:ADMIN_PASSWORD
    }
    if (-not $env:MARIADB_ROOT_PASSWORD) {
        $MARIADB_ROOT_PASSWORD = "change_me_strong_password_123"
        Write-Warning "Using default MARIADB_ROOT_PASSWORD. Set MARIADB_ROOT_PASSWORD env var or PRODUCTION=1 for production."
    } else {
        $MARIADB_ROOT_PASSWORD = $env:MARIADB_ROOT_PASSWORD
    }
}

# Discover modular apps from their manifests (no hard-coded app list).
$Manifests = @(Get-ChildItem -Path "apps/productix_*/productix_*/productix_module.json" -ErrorAction SilentlyContinue)
$PlatformName = ""
$DiscoveredApps = @()
foreach ($m in $Manifests) {
    $app = $m.Directory.Parent.Name
    if ((Get-Content $m.FullName -Raw) -match '"always_enabled"\s*:\s*true') {
        $PlatformName = $app
    } else {
        $DiscoveredApps += $app
    }
}

if ($env:PRODUCTIX_APPS) {
    $ProductixApps = @($env:PRODUCTIX_APPS -split '[,\s]+' | Where-Object { $_ })
} else {
    $ProductixApps = @($DiscoveredApps)
}

if ($PlatformName -and -not ($ProductixApps -contains $PlatformName)) {
    $ProductixApps = @($PlatformName) + $ProductixApps
    Write-Host "NOTE: $PlatformName is the platform - added automatically." -ForegroundColor Yellow
}
if (-not $ProductixApps) {
    throw "no productix apps discovered under apps/ - run from the repo root or set PRODUCTIX_APPS"
}
$HasRecipe = $ProductixApps -contains "productix_recipe"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Productix ERP - Site Initialization" -ForegroundColor Cyan
Write-Host "  Apps: $($ProductixApps -join ', ')" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$AppsTxt = "frappe\nerpnext\n" + ($ProductixApps -join "\n") + "\n"

Write-Host "`n[1/6] Configuring global bench settings & installing productix apps..." -ForegroundColor Yellow
$installEditable = ($ProductixApps | ForEach-Object { "/home/frappe/frappe-bench/env/bin/pip install -e apps/$_ --quiet" }) -join " && "
$buildApps = ($ProductixApps | ForEach-Object { "bench build --app $_ >/dev/null 2>&1 || true" }) -join " && "
docker compose exec backend bash -c "cd /home/frappe/frappe-bench && bench set-config -g db_host mariadb && bench set-config -gp db_port 3306 && bench set-config -g redis_cache redis://redis-cache:6379 && bench set-config -g redis_queue redis://redis-queue:6379 && bench set-config -g redis_socketio redis://redis-queue:6379 && bench set-config -gp socketio_port 9000 && bench set-config -g default_site $SITE_NAME && printf '$AppsTxt' > /home/frappe/frappe-bench/sites/apps.txt && $installEditable && $buildApps"

Write-Host "`n[2/6] Creating site: $SITE_NAME ..." -ForegroundColor Yellow
docker compose exec backend bash -c "cd /home/frappe/frappe-bench && bench new-site $SITE_NAME --mariadb-root-password '$MARIADB_ROOT_PASSWORD' --admin-password '$ADMIN_PASSWORD' --no-mariadb-socket --force"

Write-Host "`n[3/6] Installing ERPNext..." -ForegroundColor Yellow
docker compose exec backend bash -c "cd /home/frappe/frappe-bench && bench --site $SITE_NAME install-app erpnext"

Write-Host "`n[4/6] Installing Productix apps..." -ForegroundColor Yellow
foreach ($app in $ProductixApps) {
    Write-Host "    -> installing $app" -ForegroundColor Yellow
    docker compose exec backend bash -c "cd /home/frappe/frappe-bench && bench --site $SITE_NAME install-app $app --force"
}

Write-Host "`n[5/6] Running migrations, build, assets sync..." -ForegroundColor Yellow
docker compose exec backend bash -c "cd /home/frappe/frappe-bench && bench --site $SITE_NAME set-config developer_mode 1 && bench --site $SITE_NAME migrate && bench --site $SITE_NAME clear-cache && bench build --hard-link"

if ($HasRecipe) {
    Write-Host "`n[6/6] Seeding demo data (recipe module)..."
    docker compose exec backend bash -c "cd /home/frappe/frappe-bench && bench --site $SITE_NAME execute productix_recipe.setup_data.run"
} else {
    Write-Host "`n[6/6] Skipping demo data (productix_recipe not installed)."
}

Write-Host "`nRestarting services..." -ForegroundColor Yellow
docker compose restart websocket queue-short queue-long scheduler frontend

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "  Setup Complete!" -ForegroundColor Green
Write-Host "  URL: http://localhost:8080" -ForegroundColor Green
Write-Host "  Username: Administrator" -ForegroundColor Green
Write-Host "  Password: $ADMIN_PASSWORD" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green