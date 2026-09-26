#!/bin/bash
# Quick deploy script for updates (pip editable + migrate + clear-cache + build assets)
set -e
export MSYS_NO_PATHCONV=1

# Shared with setup_site.sh and the Docker bootstrap: one implementation of
# "which modules does this deployment use", so an update can never build a
# different set from the one the site was set up with.
# shellcheck source=docker/productix-selection.sh
. "$(dirname "$0")/docker/productix-selection.sh"
productix_load_dotenv "$(dirname "$0")/.env"

SITE_NAME="${SITE_NAME:-productix.local}"

# Module selection - see docker/productix-selection.sh. An exported
# PRODUCTIX_APPS still overrides .env for a single run.
px_select "apps" "${PRODUCTIX_APPS:-}"

PRODUCTIX_APPS_LIST=()
for _pxa in $PX_SELECTION; do
    PRODUCTIX_APPS_LIST+=("$_pxa")
done

if [ ${#PRODUCTIX_APPS_LIST[@]} -eq 0 ]; then
    echo "ERROR: no productix apps discovered under apps/ - run from the repo root or set PRODUCTIX_APPS." >&2
    exit 1
fi
if [ -n "$PX_UNAVAILABLE" ]; then
    echo "ERROR: PRODUCTIX_APPS selected modules that are not present:$PX_UNAVAILABLE" >&2
    exit 1
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