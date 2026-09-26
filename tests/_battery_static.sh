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
# the discovery glob lives in the shared selection now - see guard 7
grep -qF 'productix-selection.sh' "$ENTR" \
    || deploy_fail "entrypoint no longer resolves the selection through docker/productix-selection.sh"
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

# 7. module selection: ONE implementation, driven by .env, reconciled on every
#    start. Three things used to be able to disagree about what
#    PRODUCTIX_APPS meant - the entrypoint, setup_site and deploy - which is
#    how a .env asking for recipe+core ended up running KPI instead: the
#    selection only ever reached the container path, and only ever on a site
#    that did not exist yet.
SEL=$DEPLOY_SRC/productix-selection.sh
SELP=$DEPLOY_SRC/productix-selection.ps1

if [ -f "$SEL" ]; then
    sh -n "$SEL" 2>/dev/null || deploy_fail "docker/productix-selection.sh does not parse"
    grep -qF 'productix_*/productix_*/productix_module.json' "$SEL" \
        || deploy_fail "the shared selection no longer discovers modules through their manifests"
    grep -qF 'productix_load_dotenv' "$SEL" \
        || deploy_fail "the shared selection lost the .env reader"
    grep -q 'px_list_missing' "$SEL" \
        || deploy_fail "the shared selection lost the drift check (selected minus installed)"
    grep -q 'PX_BENCH_BASE' "$SEL" \
        || deploy_fail "the shared selection no longer tells the bench base from a module"
    grep -q 'px_order' "$SEL" \
        || deploy_fail "the shared selection no longer resolves 'requires' ahead of its dependents"
else
    deploy_fail "$SEL is not mounted - the selection guard cannot run"
fi
if [ -f "$SELP" ]; then
    grep -qF 'function Get-ProductixSelection' "$SELP" \
        || deploy_fail "docker/productix-selection.ps1 lost Get-ProductixSelection"
    grep -qF 'function Import-ProductixDotEnv' "$SELP" \
        || deploy_fail "docker/productix-selection.ps1 lost the .env reader"
    grep -qF 'BenchBase' "$SELP" \
        || deploy_fail "the Windows twin does not tell the bench base from a module"
else
    deploy_fail "$SELP is missing - a Windows host would resolve the selection differently"
fi

# every entry point resolves the selection with THOSE rules ...
for _sel in "$ENTR" "$DEPLOY_SRC/setup_site.sh" "$DEPLOY_SRC/deploy.sh"; do
    if [ ! -f "$_sel" ]; then
        deploy_fail "$_sel is not mounted - the shared-selection guard cannot run"
        continue
    fi
    grep -qF 'productix-selection.sh' "$_sel" \
        || deploy_fail "$_sel resolves the selection on its own instead of using the shared rules"
done
# ... and every entry point that runs ON THE HOST also reads .env itself, so a
# value written there applies outside `docker compose`. The entrypoint runs
# inside the container, where .env is deliberately not mounted: it receives
# the same value through compose interpolating the `environment:` block.
for _sel in "$DEPLOY_SRC/setup_site.sh" "$DEPLOY_SRC/deploy.sh"; do
    if [ ! -f "$_sel" ]; then
        deploy_fail "$_sel is not mounted - the .env guard cannot run"
        continue
    fi
    grep -qF 'productix_load_dotenv' "$_sel" \
        || deploy_fail "$_sel ignores .env - a PRODUCTIX_APPS written there would not apply"
done
grep -qE 'PRODUCTIX_APPS:-' "$ENTR" \
    || deploy_fail "the entrypoint no longer consumes PRODUCTIX_APPS from its environment"
grep -qE 'PRODUCTIX_APPS:\s*\$\{PRODUCTIX_APPS' "$DEPLOY_SRC/docker-compose.yml" \
    || deploy_fail "docker-compose.yml no longer forwards .env's PRODUCTIX_APPS to the backend"
for _sel in "$DEPLOY_SRC/setup_site.ps1" "$DEPLOY_SRC/deploy.ps1"; do
    if [ ! -f "$_sel" ]; then
        deploy_fail "$_sel is not mounted - the shared-selection guard cannot run"
        continue
    fi
    grep -qF 'productix-selection.ps1' "$_sel" \
        || deploy_fail "$_sel resolves the selection on its own instead of using the Windows twin"
    grep -qF 'Import-ProductixDotEnv' "$_sel" \
        || deploy_fail "$_sel ignores .env - a PRODUCTIX_APPS written there would not apply"
done

# a setup that did not finish must resume, not verdict "ok" and skip forever
grep -qF 'productix_started' "$ENTR" \
    || deploy_fail "the entrypoint no longer flags an install as started"
grep -qF '.productix_install_complete' "$ENTR" \
    || deploy_fail "the entrypoint no longer records a completed install"
grep -qF 'MODE=resume' "$ENTR" \
    || deploy_fail "the entrypoint cannot resume an install that died part way through"
grep -qF 'report_module_status' "$ENTR" \
    || deploy_fail "the entrypoint no longer prints what is selected vs installed"

# reconcile: install the difference, never destroy it
grep -q 'px_list_missing' "$ENTR" \
    || deploy_fail "the entrypoint no longer compares the selection with the site"
grep -q 'install_app_if_missing' "$ENTR" \
    || deploy_fail "the entrypoint installs blind instead of reconciling against installed_apps"
# The reconcile installs with --force (a re-install whose Module Def rows
# already exist would otherwise die on a duplicate key), so the DATABASE must
# be consulted first: force is only ever allowed to reach an app the site does
# not already report as installed. It never uninstalls anything.
grep -qF 'px_list_has "$INSTALLED_APPS"' "$ENTR" \
    || deploy_fail "install_app_if_missing no longer consults installed_apps before installing"
grep -qF 'install-app "$1" --force' "$ENTR" \
    || deploy_fail "the reconcile cannot re-install a module whose Module Def rows still exist"
if grep -n 'uninstall-app' "$ENTR" | grep -v 'echo ' >/dev/null 2>&1; then
    deploy_fail "the entrypoint would uninstall a module - that drops its tables with it"
fi

# post_install re-seeds, so it may only run while a site is being created
grep -qF 'run_post_install_hooks' "$ENTR" \
    || deploy_fail "the entrypoint lost the generic post_install hook runner"
grep -qF 'announce_pending_seed' "$ENTR" \
    || deploy_fail "a module added to a finished site would be seeded without being asked"

echo "DEPLOY_EXIT=$DEPLOY_RC"
record "deployment_self_heal" "$DEPLOY_RC"

echo "--- summary ---"
if [ "$FAILED" -eq 0 ]; then
    echo "BATTERY=PASS"
    exit 0
fi
echo "BATTERY=FAIL ($FAILED step(s) failed)" >&2
exit 1
