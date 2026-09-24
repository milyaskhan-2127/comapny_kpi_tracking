#!/bin/bash
# tests/_clear_cache.sh — clear frappe cache and rebuild the app module map for a site.
# Usage: bash tests/_clear_cache.sh <site>
set -u
SITE="${1:?site required}"
if command -v docker.exe >/dev/null 2>&1; then DC="docker.exe"; else DC="docker"; fi
$DC compose cp ./tests/_clear_cache.py backend:/home/frappe/frappe-bench/tests/_clear_cache.py 2>/dev/null
$DC compose exec -T backend bash -c "cd /home/frappe/frappe-bench && bench --site $SITE console < tests/_clear_cache.py" 2>&1 \
  | grep -E 'CACHE_CLEARED|Error|Traceback' | head -10