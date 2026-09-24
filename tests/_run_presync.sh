#!/bin/bash
# tests/_run_presync.sh — run the legacy pre-sync console script for a site.
# Usage: bash tests/_run_presync.sh <site>
set -u
SITE="${1:?site required}"
if command -v docker.exe >/dev/null 2>&1; then DC="docker.exe"; else DC="docker"; fi
$DC compose exec -T backend bash -c "cd /home/frappe/frappe-bench && bench --site $SITE console < tests/_presync_legacy.py" 2>&1 \
  | grep -E 'PRESYNC|Error|Traceback' | head -30