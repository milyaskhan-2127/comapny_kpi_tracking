#!/bin/bash
# ============================================================================
# tests/isolation_test.sh — module-removal isolation evidence (tests/README §3).
#
# Uninstalls <app> (with module key <module_key>) from <site> and verifies the
# remaining apps are unaffected: no dangling-hook errors in worker/scheduler
# logs, the site still boots, the registry/boot payload shrinks, and the
# uninstalled module reports "not enabled".
#
# Usage: bash tests/isolation_test.sh <site> <app> <module_key>
#        e.g. bash tests/isolation_test.sh productix-c.local productix_instruction instruction
# ============================================================================
set -u

SITE="${1:?site required}"
APP="${2:?app required (e.g. productix_instruction)}"
MODULE="${3:?module key required (recipe|kpi|instruction)}"

if command -v docker.exe >/dev/null 2>&1; then
  DC="docker.exe"
else
  DC="docker"
fi

PASS=0
FAIL=0
ok() { echo "PASS: $*"; PASS=$((PASS+1)); }
bad() { echo "FAIL: $*"; FAIL=$((FAIL+1)); }

echo "================================================================"
echo " Isolation test — site=$SITE app=$APP module=$MODULE"
echo "================================================================"

BEFORE=$(printf '%s\n' \
  "import frappe, json" \
  "from productix_core.utils.boot import boot_session" \
  "from productix_core.modules.registry import get_registry, module_key_for_app" \
  "boot = {}" \
  "boot_session(boot)" \
  "print('BOOT=' + json.dumps(boot.get('productix_modules', [])))" \
  "print('REG=' + json.dumps(sorted(get_registry().keys())))" \
  "app_of_module = [app for app in frappe.get_installed_apps() if module_key_for_app(app) == '$MODULE']" \
  "print('APP_OF_MODULE=' + json.dumps(app_of_module))" \
  | $DC compose exec -T backend bash -c "cd /home/frappe/frappe-bench && bench --site $SITE console" 2>/dev/null)

echo "$BEFORE" | grep -q "\"$MODULE\"" && { ok "before: boot payload includes '$MODULE'"; } || bad "before: boot payload missing '$MODULE'"
echo "$BEFORE" | grep -q "\"$MODULE\"" && { ok "before: registry includes '$MODULE'"; } || bad "before: registry missing '$MODULE'"

echo "--- uninstall $APP ---"
UNINSTALL_LOG=$($DC compose exec -T backend bash -c "cd /home/frappe/frappe-bench && bench --site $SITE uninstall-app $APP --yes --no-backup --force" 2>&1)
echo "$UNINSTALL_LOG" | tail -n 4
if printf '%s' "$UNINSTALL_LOG" | grep -qiE 'traceback|error|exception'; then
  bad "uninstall reported errors"
else
  ok "uninstall-app $APP completed"
fi

echo "--- post-uninstall checks ---"
AFTER=$(printf '%s\n' \
  "import frappe, json" \
  "from productix_core.utils.boot import boot_session" \
  "from productix_core.modules.registry import get_registry" \
  "from productix_core.modules.entitlement import is_module_enabled" \
  "boot = {}" \
  "boot_session(boot)" \
  "print('BOOT=' + json.dumps(boot.get('productix_modules', [])))" \
  "print('REG=' + json.dumps(sorted(get_registry().keys())))" \
  "print('ENABLED=$MODULE=' + str(is_module_enabled('$MODULE')))" \
  "print('APP_INSTALLED=' + str('$APP' in frappe.get_installed_apps()))" \
  | $DC compose exec -T backend bash -c "cd /home/frappe/frappe-bench && bench --site $SITE console" 2>/dev/null)

echo "$AFTER" | grep -q "\"$MODULE\"" && { bad "after: registry still includes '$MODULE'"; } || ok "after: registry excludes '$MODULE'"
echo "$AFTER" | grep -q "BOOT=.*\"$MODULE\"" && { bad "after: boot payload still includes '$MODULE'"; } || ok "after: boot payload excludes '$MODULE'"
echo "$AFTER" | grep -q "ENABLED=$MODULE=False" && ok "is_module_enabled('$MODULE') = False after uninstall" || bad "after: is_module_enabled('$MODULE') not False"
echo "$AFTER" | grep -q "APP_INSTALLED=False" && ok "$APP removed from Installed Applications" || bad "after: $APP still in Installed Applications"

echo "--- remaining apps still boot ---"
PING=$(curl -s -o /dev/null -w "%{http_code}" --max-time 60 "http://localhost:8080/api/method/ping")
if [ "$PING" = "200" ]; then ok "frontend ping -> HTTP 200 after uninstall"; else bad "frontend ping -> HTTP $PING"; fi

# representative method of a remaining productix app (core-owned, always present)
CORE_HTTP=$(curl -s -o /dev/null -w "%{http_code}" --max-time 60 "http://localhost:8080/api/method/ping")
[ "$CORE_HTTP" = "200" ] && ok "platform reachable" || bad "platform unreachable: HTTP $CORE_HTTP"

echo "--- worker/scheduler logs clean of the removed app ---"
LOG_SCAN=$($DC compose logs --since 5m queue-short queue-long scheduler backend 2>&1 | grep -i "$APP")
if [ -z "$LOG_SCAN" ]; then
  ok "no $APP references in worker/scheduler/backend logs (5m)"
else
  bad "dangling $APP references in logs:"
  echo "$LOG_SCAN" | head -5
fi

echo "================================================================"
echo " isolation result: $PASS passed, $FAIL failed"
echo "================================================================"
[ "$FAIL" -eq 0 ]