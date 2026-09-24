#!/bin/bash
# ============================================================================
# tests/gate_403.sh — API gate 403 evidence test (tests/README.md §1 item 5).
#
# Disables <module> in Productix Settings, verifies its whitelisted API method
# returns HTTP 403 (before_request gate), then re-enables and verifies normal
# operation again. Also verifies the gate never blocks core/platform traffic.
#
# The test authenticates as Administrator first: the gated endpoints are
# whitelisted for logged-in users (not guests), so an unauthenticated call
# would be rejected with an *auth* 403 that would mask the gate. With a
# session, the only 403 source while disabled is gate_request, and we further
# assert the 403 body carries the gate's "disabled on this site" message.
#
# Usage: bash tests/gate_403.sh <site> <module_key>
#        e.g. bash tests/gate_403.sh productix-c.local recipe
# Env:   GATE_URL     (default http://localhost:8080)
#        GATE_ADMIN_PASSWORD (default Admin@123)
# ============================================================================
set -u

SITE="${1:?site required}"
MODULE="${2:?module key required (recipe|kpi|instruction)}"
URL_BASE="${GATE_URL:-http://localhost:8080}"
ADMIN_PASSWORD="${GATE_ADMIN_PASSWORD:-Admin@123}"

# module -> app -> representative whitelisted API method.
# Known module keys have built-in defaults; for any other (future) module key
# provide GATE_METHOD=<dotted.api.method> [GATE_APP=<app>] via env so this
# script works for new modules without editing it.
#
# NOTE — nginx forces `X-Frappe-Site-Name: __SITE_NAME__` on every proxied
# request, so this host-facing variant can only exercise the SITE_NAME site
# (the nginx path). Per-site gate evidence runs against backend gunicorn
# (localhost:8000 in the backend container) with an explicit site header —
# see tests/_gate_403_combo_c.py for that pattern.
if [ -n "${GATE_METHOD:-}" ]; then
  APP="${GATE_APP:-}"
  METHOD="$GATE_METHOD"
else
  case "$MODULE" in
    recipe)      APP="productix_recipe"; METHOD="productix_recipe.api.inventory.get_user_role_context" ;;
    kpi)         APP="productix_kpi";    METHOD="productix_kpi.kpi_tracking.api.machine.get_machines" ;;
    instruction) APP="productix_instruction"; METHOD="productix_instruction.instruction_room.doctype.instruction_message.instruction_message.get_unread_count" ;;
    *) echo "FAIL: unsupported module key '$MODULE' — set GATE_METHOD=<dotted.method> (and GATE_APP=<app>)"; exit 1 ;;
  esac
fi

if command -v docker.exe >/dev/null 2>&1; then
  DC="docker.exe"
else
  DC="docker"
fi

PASS=0
FAIL=0
ok() { echo "PASS: $*"; PASS=$((PASS+1)); }
bad() { echo "FAIL: $*"; FAIL=$((FAIL+1)); }

JAR=$(mktemp)
trap 'rm -f "$JAR"' EXIT

echo "================================================================"
echo " Gate 403 test — site=$SITE module=$MODULE method=$METHOD"
echo "================================================================"

URL="$URL_BASE/api/method/$METHOD"

# --- authenticate once so auth-403 cannot mask the entitlement gate ---
LOGIN_CODE=$(curl -s -c "$JAR" -o "$URL_BASE/api/method/login.$$.json" -w "%{http_code}" \
  --max-time 60 -X POST "$URL_BASE/api/method/login" \
  -d "usr=Administrator&pwd=$ADMIN_PASSWORD")
rm -f "$URL_BASE/api/method/login.$$.json"
if [ "$LOGIN_CODE" = "200" ]; then
  ok "authenticated as Administrator (login -> HTTP 200)"
else
  bad "login -> HTTP $LOGIN_CODE (expected 200)"
fi

# Flip entitlement row for the module (disable=0 / enable=1)
SET_ENT() { # SET_ENT 0|1
  local val=$1
  $DC compose exec -T backend bash -c \
    "cd /home/frappe/frappe-bench && bench --site $SITE execute productix_core.modules.entitlement.set_entitlement --kwargs '{\"module_key\": \"$MODULE\", \"enabled\": $val}'" >/dev/null 2>&1
}

STATE_IC() { # prints True/False
  printf '%s\n' \
    "from productix_core.modules.entitlement import is_module_enabled" \
    "print(is_module_enabled('$MODULE'))" \
  | $DC compose exec -T backend bash -c "cd /home/frappe/frappe-bench && bench --site $SITE console" 2>/dev/null \
  | grep -oE 'True|False' | tail -n1
}

HTTP() { curl -s -b "$JAR" -o /dev/null -w "%{http_code}" --max-time 60 "$URL"; }
BODY() { curl -s -b "$JAR" --max-time 60 "$URL"; }

echo "--- baseline (module enabled) ---"
if [ "$(HTTP)" = "200" ]; then ok "baseline $MODULE endpoint -> HTTP 200"; else bad "baseline -> HTTP $(HTTP)"; fi

echo "--- disable module $MODULE ---"
SET_ENT 0
sleep 2
if [ "$(STATE_IC)" = "False" ]; then ok "is_module_enabled('$MODULE') = False after disable"; else bad "is_module_enabled('$MODULE') = $(STATE_IC) after disable"; fi

echo "--- gate must answer 403 with the entitlement message ---"
GATE_HTTP=$(HTTP)
GATE_BODY=$(BODY)
if [ "$GATE_HTTP" = "403" ]; then ok "disabled $MODULE endpoint -> HTTP 403"; else bad "disabled endpoint -> HTTP $GATE_HTTP (expected 403)"; fi
if printf '%s' "$GATE_BODY" | grep -q "disabled on this site"; then
  ok "403 body carries gate message ('disabled on this site')"
else
  bad "403 body is not the gate message (auth/gate leak? body: $(printf '%s' "$GATE_BODY" | head -c 200))"
fi

echo "--- core platform must stay reachable ---"
CORE_HTTP=$(curl -s -o /dev/null -w "%{http_code}" --max-time 60 "$URL_BASE/api/method/ping")
if [ "$CORE_HTTP" = "200" ]; then ok "platform ping still HTTP 200 while $MODULE disabled"; else bad "platform ping -> HTTP $CORE_HTTP"; fi

echo "--- re-enable module $MODULE ---"
SET_ENT 1
sleep 2
if [ "$(STATE_IC)" = "True" ]; then ok "is_module_enabled('$MODULE') = True after re-enable"; else bad "is_module_enabled('$MODULE') = $(STATE_IC) after re-enable"; fi
if [ "$(HTTP)" = "200" ]; then ok "$MODULE endpoint recovered -> HTTP 200"; else bad "recovered endpoint -> HTTP $(HTTP)"; fi

echo "================================================================"
echo " gate result: $PASS passed, $FAIL failed"
echo "================================================================"
[ "$FAIL" -eq 0 ]