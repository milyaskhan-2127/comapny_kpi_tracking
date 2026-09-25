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

echo "--- summary ---"
if [ "$FAILED" -eq 0 ]; then
    echo "BATTERY=PASS"
    exit 0
fi
echo "BATTERY=FAIL ($FAILED step(s) failed)" >&2
exit 1
