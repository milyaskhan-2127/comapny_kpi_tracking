#!/bin/bash
# tests/_migcheck_full.sh — dump the full migration_check report for a site.
# Usage: bash tests/_migcheck_full.sh <site>
set -u
SITE="${1:?site required}"
if command -v docker.exe >/dev/null 2>&1; then DC="docker.exe"; else DC="docker"; fi
$DC compose exec -T backend bash -c "cd /home/frappe/frappe-bench && bench --site $SITE console < tests/_migration_check_run.py" 2>&1 \
  | sed -n '/{/,$p' \
  | grep -vE '^In \[|^    \.\.\.:|^ *\.\.\.:' \
  | head -120