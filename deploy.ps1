# Quick deploy script for updates (pip editable + migrate + clear-cache + build assets)
$SITE_NAME = if ($env:SITE_NAME) { $env:SITE_NAME } else { "productix.local" }

# Same module selection semantics as setup_site.ps1: PRODUCTIX_APPS override,
# otherwise every app discovered via its productix_module.json manifest.
# Platform first (manifest flagged "always_enabled"); the legacy apps/productix
# directory ships no manifest and is never picked up.
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
if ($PlatformName) {
    $ProductixApps = @($PlatformName) + @($ProductixApps | Where-Object { $_ -ne $PlatformName })
}

Write-Host "Deploying updates to $SITE_NAME (apps: $($ProductixApps -join ', ')) ..." -ForegroundColor Yellow

$pipInstall = ($ProductixApps | ForEach-Object { "/home/frappe/frappe-bench/env/bin/pip install -e apps/$_ --quiet" }) -join " && "
$assetDirs = (($ProductixApps + @("productix")) | ForEach-Object { "sites/assets/$_" }) -join " "
$assetCopy = (($ProductixApps + @("productix")) | ForEach-Object { "cp -rn apps/$_/$_/public/* sites/assets/$_/ 2>/dev/null || true" }) -join " && "
# bench build needs node (bundled under .nvm) on PATH; frappe/erpnext assets
# must be REAL dirs in the shared volume so nginx serves freshly built bundles
$assetMats = "if [ -L sites/assets/frappe ]; then rm sites/assets/frappe && cp -a apps/frappe/frappe/public sites/assets/frappe; fi && if [ -L sites/assets/erpnext ]; then rm sites/assets/erpnext && cp -a apps/erpnext/erpnext/public sites/assets/erpnext; fi"

docker compose exec backend bash -c "cd /home/frappe/frappe-bench && export PATH=/home/frappe/.nvm/current/bin:/usr/local/bin:/usr/bin:/bin && $assetMats && $pipInstall && bench --site $SITE_NAME migrate && bench --site $SITE_NAME clear-cache && mkdir -p $assetDirs && $assetCopy && bench build --hard-link"

Write-Host "Restarting background workers and frontend..." -ForegroundColor Yellow
docker compose restart websocket queue-short queue-long scheduler frontend

Write-Host "Done." -ForegroundColor Green