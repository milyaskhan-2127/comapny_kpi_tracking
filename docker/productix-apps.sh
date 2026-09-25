#!/bin/sh
# ============================================================================
# Productix ERP - module discovery shim
#
# SOURCED (never executed) by every service that imports python code. It
# replaces two things that used to name each module explicitly:
#
#   * the four per-app bind mounts in docker-compose.yml
#   * the static PYTHONPATH entry (the old `x-python-apps` anchor)
#
# How it works: ./apps is mounted ONCE, at /opt/productix-apps, and this
# script, at container start, discovers whatever is actually there and:
#
#   1. links each module into the bench's apps/ tree, so `bench`, `pip
#      install -e` and `frappe.get_app_path()` find it;
#   2. exports PYTHONPATH covering those links, for the process that sources
#      this script and everything it execs;
#   3. rewrites a .pth file in the environment's site-packages, which is how
#      the image itself makes frappe/erpnext importable. This is what reaches
#      `docker exec` shells and any interpreter that never sees this script.
#
# Consequence: adding a module = dropping a folder into apps/. No edit to
# docker-compose.yml, no edit to this file, no edit to any entrypoint.
#
# "Present" and "installed" stay separate concerns: everything present here
# is importable, but only the apps selected by PRODUCTIX_APPS (or full
# discovery) get installed on a site - an uninstalled app is inert.
#
# POSIX sh, sourced into `set -eu` shells, so it must be idempotent, must not
# touch `set`, and must never abort its caller (every write is `|| true`).
# ============================================================================

PRODUCTIX_HOST_APPS="${PRODUCTIX_HOST_APPS:-/opt/productix-apps}"
PRODUCTIX_BENCH="${BENCH_DIR:-/home/frappe/frappe-bench}"
PRODUCTIX_BENCH_APPS="$PRODUCTIX_BENCH/apps"

# ---------------------------------------------------------------------------
# 1. link every module folder into the bench's apps/ tree
# ---------------------------------------------------------------------------
PRODUCTIX_PYTHONPATH="${PYTHONPATH:-}"
PRODUCTIX_LINKED=0

for PRODUCTIX_SRC_DIR in "$PRODUCTIX_HOST_APPS"/productix_*; do
    if [ ! -d "$PRODUCTIX_SRC_DIR" ]; then
        # glob did not match anything - keep POSIX sh happy, ignore it
        continue
    fi

    PRODUCTIX_APP="${PRODUCTIX_SRC_DIR##*/}"
    PRODUCTIX_TARGET="$PRODUCTIX_BENCH_APPS/$PRODUCTIX_APP"

    # A real directory here would shadow the mounted source tree. It can only
    # come from an older layout (the old compose mounted each app in place),
    # so replace it; a mount point refuses to be removed and is left alone.
    if [ -d "$PRODUCTIX_TARGET" ] && [ ! -L "$PRODUCTIX_TARGET" ]; then
        rm -rf "$PRODUCTIX_TARGET" 2>/dev/null || true
    fi
    ln -sfn "$PRODUCTIX_SRC_DIR" "$PRODUCTIX_TARGET" 2>/dev/null || true

    case ":$PRODUCTIX_PYTHONPATH:" in
        *":$PRODUCTIX_TARGET:"*) ;;
        *)
            if [ -n "$PRODUCTIX_PYTHONPATH" ]; then
                PRODUCTIX_PYTHONPATH="$PRODUCTIX_PYTHONPATH:$PRODUCTIX_TARGET"
            else
                PRODUCTIX_PYTHONPATH="$PRODUCTIX_TARGET"
            fi
            ;;
    esac
    PRODUCTIX_LINKED=$((PRODUCTIX_LINKED + 1))
done

if [ -n "$PRODUCTIX_PYTHONPATH" ]; then
    PYTHONPATH="$PRODUCTIX_PYTHONPATH"
    export PYTHONPATH
fi

# Re-exported so callers can fail fast when nothing was found (e.g. the
# source tree was not mounted).
PRODUCTIX_LINKED_MODULES="$PRODUCTIX_LINKED"

# ---------------------------------------------------------------------------
# 2. make the links visible to every interpreter in this container
# ---------------------------------------------------------------------------
# PYTHONPATH only reaches processes that inherit this script's environment,
# which excludes `docker exec` / `docker compose exec` shells - they get the
# image's environment, not PID 1's. A .pth entry in site-packages reaches
# them all, and it is the very mechanism the image already uses for frappe
# and erpnext (frappe.pth, erpnext.pth), so it needs no PATH or interpreter
# knowledge beyond finding site-packages. Written via a temp file and moved
# into place so a restart can never leave it half-written or duplicated.
for PRODUCTIX_SITE_PACKAGES in "$PRODUCTIX_BENCH"/env/lib/python3*/site-packages; do
    if [ ! -d "$PRODUCTIX_SITE_PACKAGES" ]; then
        continue
    fi

    PRODUCTIX_PTH="$PRODUCTIX_SITE_PACKAGES/productix-modules.pth"
    PRODUCTIX_PTH_TMP="$PRODUCTIX_PTH.tmp"
    PRODUCTIX_PTH_COUNT=0

    if (: > "$PRODUCTIX_PTH_TMP") 2>/dev/null; then
        for PRODUCTIX_LINK in "$PRODUCTIX_BENCH_APPS"/productix_*; do
            if [ ! -d "$PRODUCTIX_LINK" ]; then
                continue
            fi
            if printf '%s\n' "$PRODUCTIX_LINK" >> "$PRODUCTIX_PTH_TMP" 2>/dev/null; then
                PRODUCTIX_PTH_COUNT=$((PRODUCTIX_PTH_COUNT + 1))
            fi
        done

        if [ "$PRODUCTIX_PTH_COUNT" -gt 0 ]; then
            mv -f "$PRODUCTIX_PTH_TMP" "$PRODUCTIX_PTH" 2>/dev/null || true
        else
            rm -f "$PRODUCTIX_PTH_TMP" "$PRODUCTIX_PTH" 2>/dev/null || true
        fi
    fi
    break
done

unset PRODUCTIX_HOST_APPS PRODUCTIX_BENCH PRODUCTIX_BENCH_APPS
unset PRODUCTIX_SRC_DIR PRODUCTIX_APP PRODUCTIX_TARGET
unset PRODUCTIX_SITE_PACKAGES PRODUCTIX_PTH PRODUCTIX_PTH_TMP
unset PRODUCTIX_PTH_COUNT PRODUCTIX_LINK
