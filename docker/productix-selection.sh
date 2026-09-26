# shellcheck shell=sh
# ============================================================================
# Productix ERP - module selection (SINGLE SOURCE OF TRUTH)
# ============================================================================
# This file answers exactly one question: "which modules does THIS
# deployment install?"  It is SOURCED - never executed - by
#
#     docker/backend-entrypoint.sh    POSIX sh, inside the backend container
#     setup_site.sh                   bash, on the host
#     deploy.sh                       bash, on the host
#
# so the automatic Docker bootstrap, a manual setup and an update can no
# longer resolve PRODUCTIX_APPS to three different lists (they used to, which
# is why choosing a subset in .env installed something else).  setup_site.ps1
# and deploy.ps1 mirror the same algorithm for Windows hosts - PowerShell
# cannot source a shell file - so keep the two in step.
#
# Nothing here names a module.  Apps are discovered by globbing
#
#     <root>/productix_*/productix_*/productix_module.json
#
# and the only two inputs are that glob and the operator's PRODUCTIX_APPS.
# Adding a module = dropping a folder under apps/; no edit here, no edit to
# any entrypoint, no edit to docker-compose.yml.
#
# POSIX sh only, and sourced into `set -eu` shells, therefore:
#   * never touch `set`,
#   * never abort the caller on a missing or odd manifest - degrade to
#     "no value" instead, and record it in PX_DEP_GAPS / PX_UNAVAILABLE,
#   * leave every PX_* variable defined (empty, if unknown).
#
# It also carries productix_load_dotenv(), which is what makes .env the single
# input for the HOST scripts (docker compose reads it for the container path,
# but a manual setup used to ignore it completely - see that function).
# ============================================================================

# ---------------------------------------------------------------------------
# productix_load_dotenv [<file>]
#
# Read KEY=VALUE lines out of .env WITHOUT overriding anything that is already
# in the environment. Precedence, highest first:
#
#     1. an explicitly exported variable      PRODUCTIX_APPS=core ./setup_site.sh
#     2. the .env file
#
# That order is the whole point: .env is the deployment's configuration, so a
# manual setup must install what it says, yet an operator must still be able
# to override one value for a single run without editing the file.
#
# Deliberately not `set -a; . ./.env`: that would let the file win over an
# explicit export, would execute anything the file happens to contain, and
# would abort the caller when a line is malformed.
#
# Blank lines, comments and CRLF line endings (a Windows checkout) are
# tolerated; surrounding quotes are stripped so MAIL_DEFAULT_SENDER="..." and
# MAIL_DEFAULT_SENDER=... behave the same way as they do for compose.
# ---------------------------------------------------------------------------
productix_load_dotenv() {
    _pld_file="${1:-.env}"
    [ -f "$_pld_file" ] || return 0
    while IFS= read -r _pld_line || [ -n "$_pld_line" ]; do
        case "$_pld_line" in
        '' | '#'*) continue ;;
        esac
        case "$_pld_line" in
        *=*) ;;
        *) continue ;;
        esac
        _pld_key=$(printf '%s' "${_pld_line%%=*}" | tr -d '[:space:]')
        # A Windows checkout gives every line a CR. Remove it from the VALUE
        # (that is where it lands, read having eaten only the LF) before the
        # quote handling below, which needs to see a real closing quote.
        # tr rather than ${var%$'\r'}, so this file also parses as plain
        # POSIX sh - the entrypoint sources it under `sh`, and `sh -n` runs
        # over it in the battery.
        _pld_val=$(printf '%s' "${_pld_line#*=}" | tr -d '\r')
        # Only a name the shell could actually export, so a stray line in .env
        # can never reach the assignment below.
        case "$_pld_key" in
        '' | [0-9]* | *[!A-Za-z0-9_]*) continue ;;
        esac
        # printenv, not ${VAR+x}: the name only exists at runtime, and a value
        # that is already in the environment - even an empty one - must keep
        # winning over the file.
        if printenv "$_pld_key" >/dev/null 2>&1; then
            continue
        fi
        case "$_pld_val" in
        \"*\")
            _pld_val=${_pld_val#\"}
            _pld_val=${_pld_val%\"}
            ;;
        \'*\')
            _pld_val=${_pld_val#\'}
            _pld_val=${_pld_val%\'}
            ;;
        esac
        export "${_pld_key}=${_pld_val}"
    done < "$_pld_file"
    unset _pld_file _pld_line _pld_key _pld_val
    return 0
}

# ---------------------------------------------------------------------------
# list helpers - space-separated words, order preserved, no duplicates
# ---------------------------------------------------------------------------

# px_list_has <list> <item> - succeeds when <item> is a word of <list>
px_list_has() {
    case " ${1:-} " in
    *" ${2:-} "*) return 0 ;;
    esac
    return 1
}

# px_list_add <list> <item> - prints <list> with <item> appended, if new
px_list_add() {
    if px_list_has "${1:-}" "${2:-}"; then
        printf '%s' "${1:-}"
    elif [ -z "${1:-}" ]; then
        printf '%s' "${2:-}"
    else
        printf '%s %s' "${1:-}" "${2:-}"
    fi
}

# px_list_dedupe <list> - prints <list> without repeats, order unchanged
px_list_dedupe() {
    _pxld_out=""
    for _pxld_item in ${1:-}; do
        _pxld_out=$(px_list_add "$_pxld_out" "$_pxld_item")
    done
    printf '%s' "$_pxld_out"
}

# px_list_missing <wanted> <have> - the words of <wanted> absent from <have>.
# This is the whole drift check: selection minus installed.
px_list_missing() {
    _pxlm_out=""
    for _pxlm_item in ${1:-}; do
        if ! px_list_has "${2:-}" "$_pxlm_item"; then
            _pxlm_out=$(px_list_add "$_pxlm_out" "$_pxlm_item")
        fi
    done
    printf '%s' "$_pxlm_out"
}

# ---------------------------------------------------------------------------
# manifest readers
#
# sed/grep only - deliberately.  These run on a Windows host (Git Bash) as
# well as in the container, where python is not guaranteed to be on PATH, and
# a manifest must never be able to abort an install.
# ---------------------------------------------------------------------------

# px_manifest_list <manifest.json> <key> - a JSON array of strings printed as
# space-separated words.  The file is flattened first, so the array may span
# lines.  Unreadable file, wrong shape or no such key -> nothing at all.
px_manifest_list() {
    [ -f "${1:-}" ] || return 0
    tr -d '\r' < "$1" | tr '\n' ' ' |
        sed -n "s/.*\"${2:-}\"[[:space:]]*:[[:space:]]*\[\([^]]*\)\].*/\1/p" |
        tr -d '"' | tr -d "'" | tr ',' ' ' | tr -s ' ' |
        sed -e 's/^ *//' -e 's/ *$//'
    return 0
}

# px_manifest_get <manifest.json> <key> - one JSON string value (or nothing).
px_manifest_get() {
    [ -f "${1:-}" ] || return 0
    sed -n "s/.*\"${2:-}\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" "$1" |
        tr -d '\r' | sed -n '1p'
    return 0
}

# px_manifest_flag <manifest.json> <key> - succeeds when the key is `true`.
px_manifest_flag() {
    [ -f "${1:-}" ] || return 1
    grep -qE "\"${2:-}\"[[:space:]]*:[[:space:]]*true" "$1"
}

# ---------------------------------------------------------------------------
# app classification
# ---------------------------------------------------------------------------

# px_is_module <app> - succeeds when the app ships its own
# productix_module.json.  This is how a *module* is told apart from the bench
# base (frappe, erpnext): those two are installed unconditionally by every
# site and are therefore never part of a module selection.
px_is_module() {
    for _pxim_manifest in "$PX_APPS_ROOT/${1:-}"/*/productix_module.json; do
        if [ -f "$_pxim_manifest" ]; then
            return 0
        fi
    done
    return 1
}

# ---------------------------------------------------------------------------
# dependency resolution
# ---------------------------------------------------------------------------

# The bench base: what a Frappe site has whether or not any module is
# selected (new-site installs frappe, the install path installs erpnext - see
# the entrypoint and setup_site.sh). Two consequences that matter here:
#
#   * they are never part of a MODULE selection, because they are not modules
#     - they have no productix_module.json, and px_is_module says so;
#   * a `requires` entry naming one of them is satisfied by definition, not
#     by a folder under the apps root. A host checkout only carries the
#     productix apps, so without this a `requires: ["erpnext", ...]` would
#     report a missing dependency on EVERY manual setup run - a warning that
#     is false, and would teach people to ignore the real ones.
PX_BENCH_BASE="${PX_BENCH_BASE:-frappe erpnext}"

# px_visit_deps <app> <seen> - depth first, so a dependency is always emitted
# before the module that needs it.  <seen> makes a circular `requires` stop
# instead of recursing forever.
#
# A required module that is missing from the checkout is recorded in
# PX_DEP_GAPS so the caller can say so out loud; a required bench-base app is
# not, because nothing is missing in that case.
px_visit_deps() {
    case " ${2:-} " in
    *" $1 "*) return 0 ;;
    esac
    for _pxvd_manifest in "$PX_APPS_ROOT/$1"/*/productix_module.json; do
        [ -f "$_pxvd_manifest" ] || continue
        for _pxvd_dep in $(px_manifest_list "$_pxvd_manifest" requires); do
            if [ ! -d "$PX_APPS_ROOT/$_pxvd_dep" ]; then
                case " $PX_BENCH_BASE " in
                *" $_pxvd_dep "*) ;;
                *)
                    PX_DEP_GAPS=$(px_list_add "$PX_DEP_GAPS" "$_pxvd_dep")
                    ;;
                esac
                continue
            fi
            px_is_module "$_pxvd_dep" || continue
            px_visit_deps "$_pxvd_dep" "${2:-} $1"
        done
    done
    PX_ORDERED=$(px_list_add "$PX_ORDERED" "$1")
}

# px_order <list> - sets PX_ORDERED: <list> plus everything it transitively
# `requires`, dependency-first, platform first, deduplicated.
px_order() {
    PX_ORDERED=""
    for _pxo_app in ${1:-}; do
        px_visit_deps "$_pxo_app" ""
    done
    PX_ORDERED=$(px_list_dedupe "$PX_ORDERED")
}

# ---------------------------------------------------------------------------
# px_select <apps-root> <raw PRODUCTIX_APPS>
#
#   <apps-root>     directory holding the app checkouts: the bench's apps/,
#                   or ./apps when run from the repo root.
#   <raw>           the operator's PRODUCTIX_APPS - commas and/or spaces -
#                   or "" to mean "every module discovered".
#
# Sets:
#   PX_APPS_ROOT      as passed in
#   PX_PLATFORM_APP   the always_enabled manifest, or "" (may not exist)
#   PX_DISCOVERED     every module found that is not the platform app
#   PX_SELECTION      the final list: platform first, then dependencies,
#                     then the rest - ready to install in that order
#   PX_REQUESTED      the operator's choice, normalised ("" = discovery mode)
#   PX_UNAVAILABLE    requested modules with no folder under <apps-root>
#   PX_DEP_GAPS       modules a `requires` refers to that are not on disk
# ---------------------------------------------------------------------------
px_select() {
    PX_APPS_ROOT="${1:-apps}"
    PX_PLATFORM_APP=""
    PX_DISCOVERED=""
    PX_SELECTION=""
    PX_REQUESTED=""
    PX_UNAVAILABLE=""
    PX_DEP_GAPS=""
    PX_ORDERED=""

    # ---- discovery: read only the manifests that are there --------------
    for _pxs_manifest in "$PX_APPS_ROOT"/productix_*/productix_*/productix_module.json; do
        [ -f "$_pxs_manifest" ] || continue
        _pxs_app=$(basename "$(dirname "$(dirname "$_pxs_manifest")")")
        if px_manifest_flag "$_pxs_manifest" always_enabled; then
            PX_PLATFORM_APP="$_pxs_app"
        else
            PX_DISCOVERED=$(px_list_add "$PX_DISCOVERED" "$_pxs_app")
        fi
    done

    # ---- what was asked for, or everything when nothing was -------------
    if [ -n "${2:-}" ]; then
        PX_REQUESTED=$(px_list_dedupe "$(printf '%s' "$2" | tr ',' ' ')")
        PX_SELECTION=$PX_REQUESTED
    else
        PX_SELECTION=$PX_DISCOVERED
    fi

    # ---- dependencies of that choice, in install order ------------------
    px_order "$PX_SELECTION"

    # ---- the platform app always leads, whatever the resolution did -----
    if [ -n "$PX_PLATFORM_APP" ]; then
        PX_SELECTION=$(px_list_dedupe "$PX_PLATFORM_APP $PX_ORDERED")
    else
        PX_SELECTION=$PX_ORDERED
    fi

    # ---- modules that were named but do not exist here ------------------
    for _pxs_app in $PX_REQUESTED; do
        if [ ! -d "$PX_APPS_ROOT/$_pxs_app" ]; then
            PX_UNAVAILABLE=$(px_list_add "$PX_UNAVAILABLE" "$_pxs_app")
        fi
    done

    return 0
}

# ---------------------------------------------------------------------------
# px_modules_installed <installed-app-list> - the subset of an `installed_apps`
# list that this platform recognises as modules.  Everything else (frappe,
# erpnext, a third-party app) is not part of a module comparison, so it can
# never be mistaken for "an extra module".
# ---------------------------------------------------------------------------
px_modules_installed() {
    _pxmi_out=""
    for _pxmi_app in ${1:-}; do
        if px_is_module "$_pxmi_app"; then
            _pxmi_out=$(px_list_add "$_pxmi_out" "$_pxmi_app")
        fi
    done
    printf '%s' "$_pxmi_out"
}
