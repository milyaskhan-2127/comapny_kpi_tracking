#!/bin/bash
# Quick deploy script for updates (pip editable + migrate + clear-cache + build assets)
set -e
export MSYS_NO_PATHCONV=1

SITE_NAME="${SITE_NAME:-productix.local}"

# Same module selection semantics as setup_site.sh: PRODUCTIX_APPS override,
# otherwise every app discovered via its productix_module.json manifest.
# Platform first (manifest flagged "always_enabled").
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

# platform first, de-duplicated
if [ -n "$PLATFORM_APP" ]; then
    REST=()
    for app in "${PRODUCTIX_APPS_LIST[@]}"; do
        [ "$app" = "$PLATFORM_APP" ] || REST+=("$app")
    done
    PRODUCTIX_APPS_LIST=("$PLATFORM_APP" "${REST[@]}")
fi

PIP_INSTALLS=""
for app in "${PRODUCTIX_APPS_LIST[@]}"; do
    [ -z "$app" ] && continue
    PIP_INSTALLS="${PIP_INSTALLS} && /home/frappe/frappe-bench/env/bin/pip install -e apps/${app} --quiet"
done

echo "Deploying updates to $SITE_NAME ..."
docker compose exec -e MSYS_NO_PATHCONV=1 backend bash -c "
  cd /home/frappe/frappe-bench && \
  # bench build needs node (bundled under .nvm) on PATH
  export PATH=\"/home/frappe/.nvm/current/bin:/usr/local/bin:/usr/bin:/bin\" && \
  # frappe/erpnext assets must be REAL dirs in the shared volume so nginx
  # serves freshly built bundles (convert leftover symlinks to real copies)
  if [ -L sites/assets/frappe ]; then rm sites/assets/frappe && cp -a apps/frappe/frappe/public sites/assets/frappe; fi && \
  if [ -L sites/assets/erpnext ]; then rm sites/assets/erpnext && cp -a apps/erpnext/erpnext/public sites/assets/erpnext; fi && \
  ${PIP_INSTALLS# && } && \
  bench --site $SITE_NAME migrate && \
  bench --site $SITE_NAME clear-cache && \
  bench build --hard-link
"
echo "Restarting background workers and frontend..."
docker compose restart websocket queue-short queue-long scheduler frontend
echo "Done."