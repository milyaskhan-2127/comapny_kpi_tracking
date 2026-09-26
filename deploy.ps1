# Quick deploy script for updates (pip editable + migrate + clear-cache + build assets)

# Shared with setup_site.ps1 and the Docker bootstrap: one implementation of
# "which modules does this deployment use", so an update can never build a
# different set from the one the site was set up with.
$ProductixRoot = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
. (Join-Path $ProductixRoot 'docker\productix-selection.ps1')
Import-ProductixDotEnv -Path (Join-Path $ProductixRoot '.env')

$SITE_NAME = if ($env:SITE_NAME) { $env:SITE_NAME } else { "productix.local" }

# Module selection - see docker/productix-selection.ps1. An exported
# PRODUCTIX_APPS still overrides .env for a single run.
$Selection = Get-ProductixSelection -AppsRoot (Join-Path $ProductixRoot 'apps') -Requested "$env:PRODUCTIX_APPS"
$ProductixApps = @($Selection.Selected)

if (-not $ProductixApps) {
    throw "no productix apps discovered under apps/ - run from the repo root or set PRODUCTIX_APPS"
}
if ($Selection.Unavailable.Count -gt 0) {
    Write-Error "PRODUCTIX_APPS selected modules that are not present: $($Selection.Unavailable -join ' ')"
    exit 1
}

Write-Host "Deploying updates to $SITE_NAME (apps: $($ProductixApps -join ', ')) ..." -ForegroundColor Yellow

$pipInstall = ($ProductixApps | ForEach-Object { "/home/frappe/frappe-bench/env/bin/pip install -e apps/$_ --quiet" }) -join " && "
$assetDirs = ($ProductixApps | ForEach-Object { "sites/assets/$_" }) -join " "
$assetCopy = ($ProductixApps | ForEach-Object { "cp -rn apps/$_/$_/public/* sites/assets/$_/ 2>/dev/null || true" }) -join " && "
# bench build needs node (bundled under .nvm) on PATH; frappe/erpnext assets
# must be REAL dirs in the shared volume so nginx serves freshly built bundles
$assetMats = "if [ -L sites/assets/frappe ]; then rm sites/assets/frappe && cp -a apps/frappe/frappe/public sites/assets/frappe; fi && if [ -L sites/assets/erpnext ]; then rm sites/assets/erpnext && cp -a apps/erpnext/erpnext/public sites/assets/erpnext; fi"

docker compose exec backend bash -c "cd /home/frappe/frappe-bench && export PATH=/home/frappe/.nvm/current/bin:/usr/local/bin:/usr/bin:/bin && $assetMats && $pipInstall && bench --site $SITE_NAME migrate && bench --site $SITE_NAME clear-cache && mkdir -p $assetDirs && $assetCopy && bench build --hard-link"

Write-Host "Restarting background workers and frontend..." -ForegroundColor Yellow
docker compose restart websocket queue-short queue-long scheduler frontend

Write-Host "Done." -ForegroundColor Green