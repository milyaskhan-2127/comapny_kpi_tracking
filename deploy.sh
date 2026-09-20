#!/bin/bash
# Quick deploy script for updates (migrate + clear-cache + build assets)
set -e
export MSYS_NO_PATHCONV=1

SITE_NAME="${SITE_NAME:-productix.local}"

echo "Deploying updates to $SITE_NAME ..."
docker compose exec -e MSYS_NO_PATHCONV=1 backend bash -c "
  cd /home/frappe/frappe-bench && \
  /home/frappe/frappe-bench/env/bin/pip install -e apps/productix --quiet && \
  bench --site $SITE_NAME migrate && \
  bench --site $SITE_NAME clear-cache && \
  bench build --hard-link
"
echo "Restarting background workers and frontend..."
docker compose restart websocket queue-short queue-long scheduler frontend
echo "Done."
