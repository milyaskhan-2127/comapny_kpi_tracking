#!/bin/bash
# tests/_mig_run_migrate.sh — run bench migrate for a site, full log to tests/_migrate_full.log
# Usage: bash tests/_mig_run_migrate.sh <site>
set -u
SITE="${1:?site required}"
if command -v docker.exe >/dev/null 2>&1; then DC="docker.exe"; else DC="docker"; fi
LOG="tests/_migrate_full.log"
$DC compose exec -T backend bash -c "cd /home/frappe/frappe-bench && bench --site $SITE migrate" > "$LOG" 2>&1
RC=$?
echo "migrate exit: $RC"
echo "=== last 60 lines ==="
tail -60 "$LOG"
echo "=== error context ==="
grep -nE "Executing|OperationalError|Error:|Traceback|Unknown column" "$LOG" | tail -40