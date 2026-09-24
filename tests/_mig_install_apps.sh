#!/bin/bash
# tests/_mig_install_apps.sh — install the modular productix apps on the migration site.
# App list is DISCOVERED from productix_module.json manifests (platform app
# flagged "always_enabled" installs first) — no hard-coded app list.
# Usage: bash tests/_mig_install_apps.sh <site>
set -u
SITE="${1:?site required}"
if command -v docker.exe >/dev/null 2>&1; then DC="docker.exe"; else DC="docker"; fi

# Discover modular apps from their manifests (run from the repo root).
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
ORDER=()
[ -n "$PLATFORM_APP" ] && ORDER+=("$PLATFORM_APP")
ORDER+=("${DISCOVERED_APPS[@]}")
if [ ${#ORDER[@]} -eq 0 ]; then
  echo "ERROR: no productix apps discovered under apps/ — run from the repo root."
  exit 1
fi

for APP in "${ORDER[@]}"; do
  echo "==================== INSTALL $APP on $SITE ===================="
  $DC compose exec -T backend bash -c "cd /home/frappe/frappe-bench && bench --site $SITE install-app $APP --force" 2>&1 \
    | grep -viE '^\s*$' \
    | tail -25
  echo "==================== DONE $APP (exit ${PIPESTATUS[0]}) ===================="
done

echo "==================== MIGRATE $SITE ===================="
$DC compose exec -T backend bash -c "cd /home/frappe/frappe-bench && bench --site $SITE migrate" 2>&1 \
  | grep -viE '^\s*$' \
  | tail -30
echo "==================== MIGRATE DONE (exit ${PIPESTATUS[0]}) ===================="
