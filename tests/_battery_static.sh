#!/bin/bash
# tests/_battery_static.sh - static acceptance battery (post-retirement rerun).
# Validators, compile check, unit/discovery tests, retired-mode coverage audit,
# module shim, asset probe. Prints the per-step XX_EXIT markers documented in
# tests/ACCEPTANCE_EVIDENCE.md and exits 0 only if EVERY step exited 0.
cd /home/frappe/frappe-bench || exit 2
export PRODUCTIX_TEST_SITE="${PRODUCTIX_TEST_SITE:-productix-c.local}"

# Every step's exit code is folded into FAILED. Nothing may silently "pass"
# just because a later step happened to succeed.
FAILED=0
record() {
    if [ "$2" -ne 0 ]; then
        FAILED=$((FAILED + 1))
        echo "!! $1 FAILED (exit $2)"
    fi
}

echo "--- validate_dependencies ---"
env/bin/python scripts/validate_dependencies.py --apps-dir apps
rc=$?
echo "VD_EXIT=$rc"
record "validate_dependencies" "$rc"

echo "--- validate_modules ---"
env/bin/python scripts/validate_modules.py --apps-dir apps
rc=$?
echo "VM_EXIT=$rc"
record "validate_modules" "$rc"

echo "--- compileall (modular apps) ---"
# Generic: compile whatever is actually under apps/, never a fixed list of
# module names. Adding a module must not require touching this battery.
COMPILE_TARGETS=()
for app_dir in apps/productix_*; do
    [ -d "$app_dir" ] && COMPILE_TARGETS+=("$app_dir")
done
if [ ${#COMPILE_TARGETS[@]} -eq 0 ]; then
    echo "no modules found under apps/"
    rc=1
else
    env/bin/python -m compileall -q "${COMPILE_TARGETS[@]}"
    rc=$?
fi
echo "CA_EXIT=$rc"
record "compileall" "$rc"

echo "--- pytest registry + generic discovery ---"
# pytest is a test-only dependency installed into the container's ephemeral
# env - a `docker compose up -d` recreate wipes it, so self-heal here.
env/bin/pip install -q pytest 2>/dev/null
env/bin/python -m pytest tests/test_registry_consistency.py \
  tests/test_generic_discovery.py -q
rc=$?
echo "PT_EXIT=$rc"
record "pytest" "$rc"

echo "--- coverage audit (retired mode expected) ---"
env/bin/python scripts/audit_legacy_coverage.py
rc=$?
echo "AUD_EXIT=$rc"
record "audit_legacy_coverage" "$rc"

echo "--- module shim (generic module discovery) ---"
bash tests/_test_module_shim.sh
rc=$?
echo "SHIM_EXIT=$rc"
record "module_shim" "$rc"

echo "--- asset probe ---"
env/bin/python tests/_asset_probe.py
rc=$?
echo "AP_EXIT=$rc"
record "asset_probe" "$rc"

echo "--- deployment self-heal guards ---"
# Regression guard for the half-created-site incident described in
# tests/ACCEPTANCE_EVIDENCE.md section 15. `bench new-site` writes
# site_config.json BEFORE it touches MariaDB, so a refused root password
# used to leave behind a file that every restart read as "site installed,
# skip setup" - and gunicorn then served 500/502 forever. What has to stay
# true: the backend decides from the state of the DATABASE, the root
# password is really authenticated (not merely present), the backend
# healthcheck can tell the truth, nginx never pins a container IP, and no
# module name appears anywhere in the deployment layer.
# Generic by construction: every assertion is about a mechanism, none of
# them mentions which modules are installed, and adding a module cannot
# make this step pass or fail.
DEPLOY_SRC=/opt/productix/deployment
DEPLOY_RC=0
deploy_fail() {
    DEPLOY_RC=1
    echo "  !! $1"
}

# 1. backend entrypoint: a verdict, never a file's existence
ENTR=/usr/local/bin/backend-entrypoint.sh
sh -n "$ENTR" 2>/dev/null || deploy_fail "docker/backend-entrypoint.sh does not parse"
grep -q 'site_verdict' "$ENTR" || deploy_fail "entrypoint lost site_verdict - a file would decide again"
grep -q 'FINAL_VERDICT=' "$ENTR" || deploy_fail "entrypoint does not re-verify the site before gunicorn"
if grep -q 'already exists - skipping setup' "$ENTR"; then
    deploy_fail "entrypoint skips setup whenever site_config.json exists (the original bug)"
fi
grep -qF 'productix_*/productix_*/productix_module.json' "$ENTR" \
    || deploy_fail "entrypoint no longer discovers modules through their manifests"
grep -q 'root_state' "$ENTR" \
    || deploy_fail "entrypoint can no longer tell an unreachable server from a refused password"
ENTR_VERIFY=$(grep -n 'FINAL_VERDICT=' "$ENTR" | head -n1 | cut -d: -f1)
ENTR_HANDOVER=$(grep -n 'exec /usr/local/bin/start.sh' "$ENTR" | head -n1 | cut -d: -f1)
if [ -z "$ENTR_VERIFY" ] || [ -z "$ENTR_HANDOVER" ]; then
    deploy_fail "could not locate the final verdict or the gunicorn handover"
elif [ "$ENTR_HANDOVER" -le "$ENTR_VERIFY" ]; then
    deploy_fail "gunicorn would start BEFORE the site is re-verified"
fi

# 2. configurator: authenticates root, does not merely check a variable
CONF=$DEPLOY_SRC/configurator.sh
if [ -f "$CONF" ]; then
    sh -n "$CONF" 2>/dev/null || deploy_fail "docker/configurator.sh does not parse"
    grep -q 'MARIADB_ROOT_PASSWORD was rejected' "$CONF" \
        || deploy_fail "configurator no longer reports a rejected root password"
    grep -qF 'SELECT 1' "$CONF" \
        || deploy_fail "configurator check is set-only - it never authenticates against MariaDB"
    grep -qF 'to accept TCP connections' "$CONF" \
        || deploy_fail "configurator no longer waits for MariaDB's first-init TCP listener (port 0)"
else
    deploy_fail "$CONF is not mounted - the configurator guard cannot run"
fi

# 3. compose: a healthcheck that tells the truth, and no module named
COMPOSE=$DEPLOY_SRC/docker-compose.yml
if [ -f "$COMPOSE" ]; then
    grep -qF 'api/method/ping' "$COMPOSE" || deploy_fail "the backend healthcheck is missing"
    grep -qF 'Host: $$SITE_NAME' "$COMPOSE" || deploy_fail "the backend healthcheck lost its Host header (frappe would 404 it)"
    grep -qF 'start_period: 900s' "$COMPOSE" || deploy_fail "the backend healthcheck would abort a first-boot install"
    DEPLOY_MODS=$(grep -o 'productix_[a-z0-9_]*' "$COMPOSE" | sort -u | tr '\n' ' ')
    if [ -n "$DEPLOY_MODS" ]; then
        deploy_fail "docker-compose.yml hard-codes a module: $DEPLOY_MODS"
    fi
else
    deploy_fail "$COMPOSE is not mounted - the compose guard cannot run"
fi

# 4. nginx resolves per request - a pinned container IP is a guaranteed 502
NGX=$DEPLOY_SRC/nginx.conf.template
if [ -f "$NGX" ]; then
    if grep -qE '^[[:space:]]*upstream[[:space:]]' "$NGX"; then
        deploy_fail "the nginx template pins a static upstream block (stale-IP 502 trap)"
    fi
    grep -qF 'resolver 127.0.0.11' "$NGX" || deploy_fail "the nginx template lost its DNS resolver"
else
    deploy_fail "$NGX is not mounted - the nginx guard cannot run"
fi

# 5. behaviour: the credential the whole setup depends on must really work,
#    and the exact probe the compose healthcheck runs must answer.
if MYSQL_PWD="${MARIADB_ROOT_PASSWORD:-}" mysql -h "${DB_HOST:-mariadb}" -P "${DB_PORT:-3306}" \
    -u root --connect-timeout=10 --batch --skip-column-names -e "SELECT 1" >/dev/null 2>&1; then
    :
else
    deploy_fail "MariaDB root does not authenticate with MARIADB_ROOT_PASSWORD"
fi
if curl -fsS -m 5 -H "Host: ${SITE_NAME:-productix.local}" \
    http://127.0.0.1:8000/api/method/ping >/dev/null 2>&1; then
    :
else
    deploy_fail "the healthcheck probe (ping with Host header) does not answer 200"
fi

# 6. developer_mode stays OFF. With it on, Frappe writes standard documents
#    (Number Cards, Reports, DocTypes ...) back into the bind-mounted app
#    source tree whenever they are saved. That tree comes from the host
#    checkout and is not writable by the `frappe` user, so the save fails
#    with PermissionError - which `bench execute` re-raises as a misleading
#    NameError, aborting an install mid-hook. Checked in every deployment
#    script, not just the entrypoint, so the manual path cannot regress it.
for _dm in "$ENTR" "$DEPLOY_SRC/setup_site.sh" "$DEPLOY_SRC/setup_site.ps1"; do
    if [ ! -f "$_dm" ]; then
        deploy_fail "$_dm is not mounted - the developer_mode guard cannot run"
        continue
    fi
    if grep -qE 'developer_mode[[:space:]]+1' "$_dm"; then
        deploy_fail "$_dm enables developer_mode (saving a standard document then writes the source tree)"
    fi
    grep -qE 'developer_mode[[:space:]]+0' "$_dm" \
        || deploy_fail "$_dm no longer forces developer_mode off"
done

echo "DEPLOY_EXIT=$DEPLOY_RC"
record "deployment_self_heal" "$DEPLOY_RC"

echo "--- summary ---"
if [ "$FAILED" -eq 0 ]; then
    echo "BATTERY=PASS"
    exit 0
fi
echo "BATTERY=FAIL ($FAILED step(s) failed)" >&2
exit 1
