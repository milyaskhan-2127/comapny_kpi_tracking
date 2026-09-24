#!/bin/bash
# tests/_battery_static.sh — static acceptance battery (post-retirement rerun).
# Validators, compile check, unit/discovery tests, retired-mode coverage audit,
# asset probe. Exit code 0 only if every step exits 0.
cd /home/frappe/frappe-bench || exit 2
export PRODUCTIX_TEST_SITE="${PRODUCTIX_TEST_SITE:-productix-c.local}"

echo "--- validate_dependencies ---"
env/bin/python scripts/validate_dependencies.py --apps-dir apps
echo "VD_EXIT=$?"

echo "--- validate_modules ---"
env/bin/python scripts/validate_modules.py --apps-dir apps
echo "VM_EXIT=$?"

echo "--- compileall (4 modular apps) ---"
env/bin/python -m compileall -q apps/productix_core apps/productix_recipe \
  apps/productix_kpi apps/productix_instruction
echo "CA_EXIT=$?"

echo "--- pytest registry + generic discovery ---"
# pytest is a test-only dependency installed into the container's ephemeral
# env — a `docker compose up -d` recreate wipes it, so self-heal here.
env/bin/pip install -q pytest 2>/dev/null
env/bin/python -m pytest tests/test_registry_consistency.py \
  tests/test_generic_discovery.py -q
echo "PT_EXIT=$?"

echo "--- coverage audit (retired mode expected) ---"
env/bin/python scripts/audit_legacy_coverage.py
echo "AUD_EXIT=$?"

echo "--- asset probe ---"
env/bin/python tests/_asset_probe.py
echo "AP_EXIT=$?"
