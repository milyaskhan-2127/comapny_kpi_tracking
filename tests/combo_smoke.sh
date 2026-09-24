#!/bin/bash
# ============================================================================
# tests/combo_smoke.sh — fresh-install smoke checks (tests/README.md §1).
#
# Runs inside a running stack against a freshly created site, prints each
# check's observable result for the acceptance evidence log.
#
# Usage (from repo root, after setup_site.ps1/.sh created the site):
#   COMBO_SMOKE_SITE="productix-a.local" \
#   COMBO_SMOKE_EXPECTED="core recipe" \
#   COMBO_SMOKE_ABSENT="kpi instruction" \
#   bash tests/combo_smoke.sh
#
#   EXPECTED = module keys that MUST be enabled (installed apps)
#   ABSENT   = module keys that MUST be disabled/absent (non-installed apps)
#
# Exit code 0 = all checks passed, 1 = any check failed.
# ============================================================================
set -u

SITE="${COMBO_SMOKE_SITE:?COMBO_SMOKE_SITE required}"
EXPECTED="${COMBO_SMOKE_EXPECTED:?COMBO_SMOKE_EXPECTED required}"
ABSENT="${COMBO_SMOKE_ABSENT:-}"

PASS=0
FAIL=0

# On Windows/WSL, plain `docker` may be Docker Desktop's WSL shim with
# integration disabled; `docker.exe` (the real Windows CLI) works via interop.
# On native Linux `docker.exe` does not exist and `docker` is used.
if command -v docker.exe >/dev/null 2>&1; then
  DC="docker.exe"
else
  DC="docker"
fi

note() { echo "  [$(date +%H:%M:%S)] $*"; }
ok()   { echo "PASS: $*"; PASS=$((PASS+1)); }
bad()  { echo "FAIL: $*"; FAIL=$((FAIL+1)); }

echo "================================================================"
echo " Combo smoke — site=$SITE  expected='$EXPECTED'  absent='$ABSENT'"
echo "================================================================"

# 1) /api/method/ping returns 200 through the frontend
note "check: frontend ping"
CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 60 \
        "http://localhost:8080/api/method/ping" || echo "000")
if [ "$CODE" = "200" ]; then ok "ping -> HTTP $CODE"; else bad "ping -> HTTP $CODE"; fi

BE() {
  # Run a python expression in bench context on the site.
  $DC compose exec -T backend bash -c \
    "cd /home/frappe/frappe-bench && bench --site $SITE execute $1 ${2:+--kwargs '${2}'} 2>/dev/null"
}

IC() {
  # invoke: IC <module_key> -> prints True/False (bench execute only prints
  # truthy returns, so use console which prints real python output)
  local key="$1"
  printf '%s\n' \
    "from productix_core.modules.entitlement import is_module_enabled" \
    "print(is_module_enabled('$key'))" \
  | $DC compose exec -T backend bash -c "cd /home/frappe/frappe-bench && bench --site $SITE console" 2>/dev/null \
  | grep -oE 'True|False' | tail -n1
}

# bench execute prints python/bool results lowercase ('true'/'false')
norm() { tr '[:upper:]' '[:lower:]' <<<"$1"; }

# 2/3) is_module_enabled per expected / absent module keys
note "check: is_module_enabled for expected modules"
for key in $EXPECTED; do
  v=$(norm "$(IC "$key")")
  if [ "$v" = "true" ]; then ok "is_module_enabled('$key') = True"; else bad "is_module_enabled('$key') = '$v'"; fi
done

note "check: is_module_enabled for absent modules"
for key in $ABSENT; do
  v=$(norm "$(IC "$key")")
  if [ "$v" = "false" ]; then ok "is_module_enabled('$key') = False (absent)"; else bad "is_module_enabled('$key') = '$v' (expected False)"; fi
done

# 4) entitlement rows synced in Productix Settings child table
note "check: entitlement rows present"
ROWS=$(BE productix_core.modules.entitlement.get_enabled_module_keys 2>/dev/null | tail -n1)
echo "       enabled module keys -> $ROWS"
if printf '%s' "$ROWS" | grep -q 'core'; then ok "entitlement rows include 'core'"; else bad "entitlement rows missing 'core'"; fi
for key in $EXPECTED; do
  if printf '%s' "$ROWS" | grep -qw "$key"; then ok "entitlement rows include '$key'"; else bad "entitlement rows missing '$key'"; fi
done

# 5) boot payload exposes exactly the enabled modules
note "check: boot payload productix_modules"
BOOT=$(printf '%s\n' \
  "import frappe, json" \
  "frappe.set_user('Administrator')" \
  "boot = {}" \
  "from productix_core.utils.boot import boot_session" \
  "boot_session(boot)" \
  "print('BOOT_MODULES=' + json.dumps(boot.get('productix_modules', [])))" \
  | $DC compose exec -T backend bash -c "cd /home/frappe/frappe-bench && bench --site $SITE console" 2>/dev/null \
  | grep -o 'BOOT_MODULES=.*' | head -n1)
echo "       $BOOT"
BOOTLIST=$(printf '%s' "$BOOT" | sed -E 's/.*BOOT_MODULES=\[(.*)\]$/\1/' | tr -d '"' | tr ',' ' ')
for key in $EXPECTED; do
  if printf '%s' "$BOOTLIST" | grep -qw "$key"; then ok "boot.productix_modules includes '$key'"; else bad "boot.productix_modules missing '$key' (got: $BOOTLIST)"; fi
done
for key in $ABSENT; do
  if printf '%s' "$BOOTLIST" | grep -qw "$key"; then bad "boot.productix_modules unexpectedly includes '$key'"; else ok "boot.productix_modules excludes '$key'"; fi
done

# 6) bench migrate clean on the fresh install
note "check: bench migrate clean"
MG=$($DC compose exec -T backend bash -c "cd /home/frappe/frappe-bench && bench --site $SITE migrate" 2>&1 | tail -n 5)
echo "       $MG"
if printf '%s' "$MG" | grep -qiE 'error|exception|traceback'; then
  bad "migrate reported errors"
else
  ok "migrate completed without errors"
fi

echo "================================================================"
echo " smoke result: $PASS passed, $FAIL failed"
echo "================================================================"
[ "$FAIL" -eq 0 ]