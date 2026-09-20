#!/bin/bash
# Backup script - saves site files + DB dump to ./backups/
set -e
export MSYS_NO_PATHCONV=1

SITE_NAME="${SITE_NAME:-productix.local}"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p backups

echo "Creating backup for $SITE_NAME ..."
docker compose exec -e MSYS_NO_PATHCONV=1 backend bash -c "
  cd /home/frappe/frappe-bench && \
  bench --site $SITE_NAME backup --with-files
"
echo "Backup created."
