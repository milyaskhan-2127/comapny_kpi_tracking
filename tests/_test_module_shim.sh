#!/bin/bash
# tests/_test_module_shim.sh - genericity proof for docker/productix-apps.sh
#
# The shim is what lets a deployment mount "./apps" once instead of listing
# every module in docker-compose.yml. This asserts it:
#   * links EVERY folder found in the module source tree (no name list),
#   * links it under its own name, whatever that name is,
#   * ignores folders that are not modules,
#   * exports PYTHONPATH covering exactly what it linked,
#   * is idempotent (a container restart must not grow PYTHONPATH),
#   * is safe to source under `set -eu`, with or without a source tree.
#
# Runs inside the backend container, called by tests/_battery_static.sh.
# Everything happens in a throwaway sandbox, so the real bench tree and the
# real PYTHONPATH are never touched.
set -u

fails=0
ok()  { echo "  ok   $1"; }
bad() { echo "  FAIL $1"; fails=$((fails + 1)); }

SHIM_SRC=/usr/local/bin/productix-apps.sh
if [ ! -f "$SHIM_SRC" ]; then
    echo "  FAIL module shim is not mounted at $SHIM_SRC"
    exit 1
fi

SANDBOX=$(mktemp -d)
trap 'rm -rf "$SANDBOX"' EXIT

SRC="$SANDBOX/src"
BENCH="$SANDBOX/bench"
SITE_PACKAGES="$BENCH/env/lib/python3.11/site-packages"
mkdir -p "$SRC/productix_alpha/productix_alpha"
mkdir -p "$SRC/productix_odd_name"   # still a module folder, whatever it is called
mkdir -p "$SRC/not_a_module"         # must be ignored
mkdir -p "$BENCH/apps"
# stand-in for the image's virtualenv, so the .pth step has somewhere to write
mkdir -p "$SITE_PACKAGES"

tr -d '\r' < "$SHIM_SRC" > "$SANDBOX/shim.sh"

run_shim() {
    PRODUCTIX_HOST_APPS="$1"
    BENCH_DIR="$2"
    # shellcheck disable=SC1090
    . "$SANDBOX/shim.sh"
}

run_shim "$SRC" "$BENCH"
FIRST_PYTHONPATH="${PYTHONPATH:-}"

# --- links every module folder found, under its own name -------------------
if [ -L "$BENCH/apps/productix_alpha" ] &&
   [ "$(readlink "$BENCH/apps/productix_alpha")" = "$SRC/productix_alpha" ]; then
    ok "links every module folder found in the source tree"
else
    bad "links every module folder found in the source tree"
fi

if [ -L "$BENCH/apps/productix_odd_name" ] &&
   [ "$(readlink "$BENCH/apps/productix_odd_name")" = "$SRC/productix_odd_name" ]; then
    ok "links a folder regardless of its exact name (no hard-coded list)"
else
    bad "links a folder regardless of its exact name (no hard-coded list)"
fi

# --- leaves non-module folders alone ---------------------------------------
if [ -e "$BENCH/apps/not_a_module" ]; then
    bad "ignores folders that are not modules"
else
    ok "ignores folders that are not modules"
fi

# --- PYTHONPATH covers exactly what was linked ------------------------------
case ":${PYTHONPATH:-}:" in
    *":$BENCH/apps/productix_alpha:"*) ok "exports PYTHONPATH for each linked module" ;;
    *)                                 bad "exports PYTHONPATH for each linked module" ;;
esac
case ":${PYTHONPATH:-}:" in
    *":$BENCH/apps/productix_odd_name:"*) ok "exports PYTHONPATH for every name" ;;
    *)                                    bad "exports PYTHONPATH for every name" ;;
esac
case ":${PYTHONPATH:-}:" in
    *":not_a_module:"*) bad "never adds a non-module folder to PYTHONPATH" ;;
    *)                  ok "never adds a non-module folder to PYTHONPATH" ;;
esac

# --- idempotent --------------------------------------------------------------
run_shim "$SRC" "$BENCH"
if [ "${PYTHONPATH:-}" = "$FIRST_PYTHONPATH" ]; then
    ok "is idempotent (second run leaves PYTHONPATH unchanged)"
else
    bad "is idempotent (second run leaves PYTHONPATH unchanged)"
fi

# --- publishes the modules to `docker exec` shells too -----------------------
# PYTHONPATH never reaches those (they get the image environment, not PID 1's),
# so the shim writes a .pth entry - the same mechanism the image uses for
# frappe.pth / erpnext.pth.
PTH="$SITE_PACKAGES/productix-modules.pth"
if [ -f "$PTH" ]; then
    ok "writes a .pth so exec'd shells can import the modules"
else
    bad "writes a .pth so exec'd shells can import the modules"
fi
if [ "$(grep -c . "$PTH" 2>/dev/null)" = "2" ]; then
    ok "lists each module exactly once (rewritten, never appended)"
else
    bad "lists each module exactly once (rewritten, never appended)"
fi
if grep -q "not_a_module" "$PTH" 2>/dev/null; then
    bad "keeps non-module folders out of the .pth"
else
    ok "keeps non-module folders out of the .pth"
fi
if grep -q "$BENCH/apps/productix_odd_name" "$PTH" 2>/dev/null; then
    ok "the .pth entries are importable parent directories"
else
    bad "the .pth entries are importable parent directories"
fi

# --- sourced into set -eu shells (every entrypoint uses one) ----------------
if ( set -eu; run_shim "$SRC" "$BENCH" ) 2>/dev/null; then
    ok "is safe to source under set -eu"
else
    bad "is safe to source under set -eu"
fi

if ( set -eu; run_shim "$SANDBOX/does-not-exist" "$BENCH" ) 2>/dev/null; then
    ok "tolerates a missing source tree under set -eu"
else
    bad "tolerates a missing source tree under set -eu"
fi

if [ "$fails" -eq 0 ]; then
    echo "  module shim: all checks passed"
    exit 0
fi
echo "  module shim: $fails check(s) failed" >&2
exit 1
