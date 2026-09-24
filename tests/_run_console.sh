#!/bin/bash
# tests/_run_console.sh — run a console script for a site and show output.
# Usage: bash tests/_run_console.sh <site> <script.py>
set -u
SITE="${1:?site required}"
PL="tests/${2:?script required}"
if command -v docker.exe >/dev/null 2>&1; then DC="docker.exe"; else DC="docker"; fi
$DC compose cp ./$PL backend:/home/frappe/frappe-bench/$PL 2>/dev/null
$DC compose exec -T backend bash -c "cd /home/frappe/frappe-bench && bench --site $SITE console < $PL" 2>&1 \
  | grep -vE '^In \[|^    \.\.\.:|^ *\.\.\.:|^Out\[' | head -60