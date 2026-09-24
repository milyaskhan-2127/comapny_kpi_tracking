#!/bin/bash
# tests/_retire_legacy_live.sh — retire the legacy app from a live site, then
# re-run migrate to settle bookkeeping. Pre/post snapshots are taken separately
# by the harness operator (tests/_local_data_snapshot.py + tests/_local_diff.py).
# Usage: bash tests/_retire_legacy_live.sh <site>
set -u
SITE="${1:?site required}"
if command -v docker.exe >/dev/null 2>&1; then DC="docker.exe"; else DC="docker"; fi

echo "==================== RETIRE legacy on $SITE ===================="
$DC compose cp ./tests/_retire_site_legacy.py backend:/home/frappe/frappe-bench/tests/_retire_site_legacy.py
$DC compose exec -T backend bash -c "cd /home/frappe/frappe-bench && env/bin/python tests/_retire_site_legacy.py $SITE" 2>&1 \
  | grep -vE '^\s*$'
RC=${PIPESTATUS[0]}
echo "==================== RETIRE exit $RC ===================="
if [ "$RC" -ne 0 ]; then exit "$RC"; fi

echo "==================== SETTLE MIGRATE $SITE ===================="
$DC compose exec -T backend bash -c "cd /home/frappe/frappe-bench && bench --site $SITE migrate" 2>&1 \
  | tail -15
echo "==================== SETTLE DONE (exit ${PIPESTATUS[0]}) ===================="

$DC compose exec -T backend bash -c "cd /home/frappe/frappe-bench && bench --site $SITE clear-cache" 2>&1 | tail -3
echo "==================== ALL DONE ===================="
