#!/bin/sh
# ============================================================================
# Productix ERP - backend container entrypoint
#
#   1. VERIFY on every start: the selected modules really exist, MariaDB
#      really accepts the credentials, and the site's database really answers.
#   2. INSTALL only when the verdict says so - never because a file happens
#      to exist.
#   3. ALWAYS hand over to the image's start.sh (gunicorn), and only after
#      the site has been re-verified.
#
# Why this no longer says `if [ -f site_config.json ]`:
#   `bench new-site` writes that file BEFORE it touches MariaDB. A refused
#   root password therefore produced a half-created site - config present,
#   no database, no tables - and every later restart dutifully "skipped"
#   setup, then booted gunicorn against a database that did not exist. The
#   result was 1045 Access denied on every request (HTTP 500, and 502 while
#   gunicorn was still coming up) and restarting never healed it.
#   The file is now one input among several: `site_verdict` looks at the
#   actual database and returns one of
#
#     fresh          nothing to install into yet          -> install
#     ok             config + database + tables + the site's own
#                    credentials all authenticate         -> decide (below)
#     reinstall      half-created site: config exists but the schema has
#                    zero tables, or the database was never created
#                                                       -> reinstall
#     fatal:<reason> cannot proceed safely                -> stop, with an
#                    actionable message; gunicorn never starts
#
# "The database works" and "the install finished" are NOT the same question.
# A setup that died after `bench new-site` left a working database, so the
# verdict alone said `ok` and setup was skipped forever - which is how a
# .env asking for recipe+core ended up running KPI instead. Two marker files
# in sites/ answer the second question, so every start resolves to a mode:
#
#     fresh    no site yet, or a half-created one   -> full install
#     resume   started marker, no completion marker -> the install never
#              finished; finish it (additive: install what is missing,
#              migrate, build). post_install hooks are safe to run here
#              because the site was never declared usable.
#     sync     completed, or predates the markers   -> never install
#              blindly: compare the selection with what the database says
#              is installed and install exactly the difference. Never runs
#              a post_install hook (see below), never uninstalls.
#
# Everything below is module-agnostic. The selection rules live in
# docker/productix-selection.sh, which setup_site.sh and deploy.sh source as
# well, so this file never names an application and any combination of
# modules installs the same way on every path.
#
# POSIX sh only - compose runs this with `sh`, so no bashisms and no
# `pipefail`. Compose strips CR before exec, so a Windows checkout cannot
# break this either.
# ============================================================================
set -eu

BENCH_DIR=/home/frappe/frappe-bench
SITE="${SITE_NAME:-productix.local}"
ENV_PIP="$BENCH_DIR/env/bin/pip"
SITE_CONFIG="$BENCH_DIR/sites/$SITE/site_config.json"
DB_HOST="${DB_HOST:-mariadb}"
DB_PORT="${DB_PORT:-3306}"
MYSQL_ERR=/tmp/productix-mysql.err

cd "$BENCH_DIR"

# Link every module found under the source tree and build PYTHONPATH.
# Generic: docker/productix-apps.sh globs ./apps, so this file names no
# modules. Applied here as well as in the queue/scheduler entrypoint so the
# `bench` CLI, gunicorn and every worker see an identical import path.
if [ -f /usr/local/bin/productix-apps.sh ]; then
    tr -d '\r' < /usr/local/bin/productix-apps.sh > /tmp/productix-apps.sh
    # shellcheck disable=SC1091
    . /tmp/productix-apps.sh
fi

# ===========================================================================
# helpers
# ===========================================================================

# json_get <file> <key> - print one value from a JSON object. Uses python3
# (always present in this image) rather than sed, which cannot be trusted on
# a file written by a process that may have died mid-write.
json_get() {
    python3 - "$1" "$2" <<'PY'
import json, sys
try:
    with open(sys.argv[1]) as fh:
        data = json.load(fh)
except Exception:
    sys.exit(1)
value = data.get(sys.argv[2])
if value is None or value == "":
    sys.exit(1)
sys.stdout.write(str(value))
PY
}

site_config_get() {
    json_get "$SITE_CONFIG" "$1"
}

# sql_escape <value> - escape a value for a single-quoted SQL literal.
sql_escape() {
    printf '%s' "$1" | sed "s/'/''/g"
}

# mysql_run <user> <password> <database-or-empty> <sql>
# Non-zero on failure; never exits the script - the caller decides.
mysql_run() {
    _mu=$1
    _mp=$2
    _md=$3
    _ms=$4
    if [ -n "$_md" ]; then
        MYSQL_PWD="$_mp" mysql -h "$DB_HOST" -P "$DB_PORT" -u "$_mu" -D "$_md" \
            --connect-timeout=10 --batch --skip-column-names \
            -e "$_ms" 2>"$MYSQL_ERR"
    else
        MYSQL_PWD="$_mp" mysql -h "$DB_HOST" -P "$DB_PORT" -u "$_mu" \
            --connect-timeout=10 --batch --skip-column-names \
            -e "$_ms" 2>"$MYSQL_ERR"
    fi
}

mysql_error() {
    cat "$MYSQL_ERR" 2>/dev/null || true
}

# root_sql <sql> - run as MariaDB root. Fails when root cannot authenticate.
root_sql() {
    [ -n "${MARIADB_ROOT_PASSWORD:-}" ] || return 1
    mysql_run root "$MARIADB_ROOT_PASSWORD" "" "$1"
}

# root_state - prints one of: ok | auth | connect
#
# Telling the two failure modes apart matters. A REFUSED password is a
# configuration error the operator has to fix, so it is reported at once and
# never as something else. An unreachable server is frequently just MariaDB
# still initialising on a first boot (its temporary server answers over the
# unix socket while still listening with `port: 0`, so `healthy` precedes a
# reachable 3306), so it is retried before being called a failure.
root_state() {
    [ -n "${MARIADB_ROOT_PASSWORD:-}" ] || {
        echo "auth"
        return 0
    }
    _rs_try=0
    while [ "$_rs_try" -lt 6 ]; do
        if mysql_run root "$MARIADB_ROOT_PASSWORD" "" "SELECT 1" >/dev/null 2>&1; then
            echo "ok"
            return 0
        fi
        case "$(mysql_error)" in
        *"Access denied"*)
            echo "auth"
            return 0
            ;;
        esac
        _rs_try=$((_rs_try + 1))
        if [ "$_rs_try" -lt 6 ]; then
            sleep 5
        fi
    done
    echo "connect"
    return 0
}

# db_exists <name>
db_exists() {
    _de=$(root_sql "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA \
                    WHERE SCHEMA_NAME='$(sql_escape "$1")'" 2>/dev/null || true)
    [ -n "$_de" ]
}

# table_count <db> - prints an integer, or nothing when it could not be read.
table_count() {
    root_sql "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES \
              WHERE TABLE_SCHEMA='$(sql_escape "$1")'" 2>/dev/null || true
}

# repair_site_grants <db> <user> <password>
# Brings the SITE's own database accounts back into agreement with
# site_config.json. Accounts only - never a table - so this is always safe
# to run against a database that holds data. This is the self-heal: a
# mismatched or rotated password used to be permanent, because the only
# alternative on offer was to reinstall the site.
repair_site_grants() {
    _rg_db=$(sql_escape "$1")
    _rg_user=$(sql_escape "$2")
    _rg_pwd=$(sql_escape "$3")
    root_sql "CREATE USER IF NOT EXISTS '$_rg_user'@'%' IDENTIFIED BY '$_rg_pwd';
              ALTER USER          '$_rg_user'@'%' IDENTIFIED BY '$_rg_pwd';
              CREATE USER IF NOT EXISTS '$_rg_user'@'localhost' IDENTIFIED BY '$_rg_pwd';
              ALTER USER          '$_rg_user'@'localhost' IDENTIFIED BY '$_rg_pwd';
              GRANT ALL PRIVILEGES ON \`$_rg_db\`.* TO '$_rg_user'@'%';
              GRANT ALL PRIVILEGES ON \`$_rg_db\`.* TO '$_rg_user'@'localhost';
              FLUSH PRIVILEGES;"
}

# report_fatal <reason> - one readable, actionable message per failure mode.
report_fatal() {
    echo "" >&2
    echo "[backend] ==================== FATAL ====================" >&2
    case "$1" in
    no-credentials)
        echo "[backend] The site '$SITE' still needs to be created and" >&2
        echo "[backend] MARIADB_ROOT_PASSWORD / ADMIN_PASSWORD are not set." >&2
        echo "[backend] Fix: copy .env.example to .env, fill both in, then" >&2
        echo "[backend]      run 'docker compose up -d' again." >&2
        ;;
    root-auth)
        echo "[backend] MariaDB rejected MARIADB_ROOT_PASSWORD." >&2
        echo "[backend] The db-data volume keeps the password it was created" >&2
        echo "[backend] with, so editing .env alone does not change it -" >&2
        echo "[backend] .env and that volume now disagree." >&2
        echo "[backend] Fix: set MARIADB_ROOT_PASSWORD in .env to the password" >&2
        echo "[backend]      the volume already uses. On a host whose data you" >&2
        echo "[backend]      may discard, 'docker compose down -v' instead -" >&2
        echo "[backend]      that DESTROYS the database." >&2
        ;;
    root-connect)
        echo "[backend] MariaDB at $DB_HOST:$DB_PORT did not become reachable." >&2
        echo "[backend] This is a connection problem, not a password problem." >&2
        echo "[backend] Fix: check 'docker compose ps' and" >&2
        echo "[backend]      'docker compose logs mariadb'." >&2
        echo "[backend] gunicorn was NOT started." >&2
        ;;
    site-config-unreadable)
        echo "[backend] '$SITE_CONFIG' exists but does not name a database." >&2
        echo "[backend] The site cannot be verified or repaired from it." >&2
        echo "[backend] Fix: remove sites/$SITE to let the site be rebuilt" >&2
        echo "[backend]      (loses data), or restore site_config.json from a backup." >&2
        ;;
    site-auth)
        echo "[backend] The database '$SITE' holds data, but the credentials" >&2
        echo "[backend] in its own site_config.json were refused by MariaDB" >&2
        echo "[backend] even after the accounts were repaired." >&2
        echo "[backend] Last error: $(mysql_error)" >&2
        echo "[backend] Fix: check sites/$SITE/site_config.json (db_name /" >&2
        echo "[backend] db_password) against the volume, or restore from backup." >&2
        echo "[backend] gunicorn was NOT started - starting it would serve 500s." >&2
        ;;
    verify-failed)
        echo "[backend] Setup finished but the site did not re-verify." >&2
        echo "[backend] Last error: $(mysql_error)" >&2
        echo "[backend] gunicorn was NOT started - starting it would serve 500s." >&2
        echo "[backend] Run 'docker compose logs backend' for the full install log." >&2
        ;;
    install-failed)
        echo "[backend] Creating the site failed - the reason is in the log" >&2
        echo "[backend] above (this line is only the summary)." >&2
        echo "[backend] gunicorn was NOT started." >&2
        ;;
    *)
        echo "[backend] $1" >&2
        ;;
    esac
    echo "[backend] =================================================" >&2
    echo "" >&2
}

# ---------------------------------------------------------------------------
# site_verdict - prints exactly one verdict line on stdout; diagnostics go
# to stderr so `$(site_verdict)` captures nothing else.
# ---------------------------------------------------------------------------
site_verdict() {
    if [ -z "${MARIADB_ROOT_PASSWORD:-}" ]; then
        echo "fatal:no-credentials"
        return 0
    fi

    # Nothing below is trustworthy until root itself works - and "does not
    # work" has two very different meanings (see root_state).
    case "$(root_state)" in
    ok) ;;
    auth)
        echo "fatal:root-auth"
        return 0
        ;;
    *)
        echo "fatal:root-connect"
        return 0
        ;;
    esac

    if [ ! -f "$SITE_CONFIG" ]; then
        echo "fresh"
        return 0
    fi

    _sv_db=$(site_config_get db_name || true)
    if [ -z "$_sv_db" ]; then
        echo "fatal:site-config-unreadable"
        return 0
    fi

    if ! db_exists "$_sv_db"; then
        # `bench new-site` wrote the config, then died before creating the
        # database. Nothing was created, so nothing can be lost.
        echo "reinstall"
        return 0
    fi

    _sv_tables=$(table_count "$_sv_db")
    if [ -z "$_sv_tables" ]; then
        echo "fatal:root-auth"
        return 0
    fi
    if [ "$_sv_tables" -eq 0 ]; then
        # Config present, schema empty: a half-created site. Safe to redo.
        echo "reinstall"
        return 0
    fi

    # There IS data. Can the site's own credentials read it?
    _sv_user=$(site_config_get db_name || true)
    _sv_pass=$(site_config_get db_password || true)
    if [ -z "$_sv_user" ] || [ -z "$_sv_pass" ]; then
        echo "fatal:site-config-unreadable"
        return 0
    fi

    if mysql_run "$_sv_user" "$_sv_pass" "$_sv_db" "SELECT 1" >/dev/null 2>&1; then
        echo "ok"
        return 0
    fi

    # Refused but recoverable: only the accounts are wrong, and repairing
    # them never touches a table.
    echo "[backend] database '$_sv_db' has data but its own account was refused" >&2
    echo "[backend] - repairing the site's grants (accounts only, no data touched)" >&2
    if repair_site_grants "$_sv_db" "$_sv_user" "$_sv_pass" >/dev/null 2>&1; then
        if mysql_run "$_sv_user" "$_sv_pass" "$_sv_db" "SELECT 1" >/dev/null 2>&1; then
            echo "[backend] grants repaired - the site's credentials now match" >&2
            echo "ok"
            return 0
        fi
    fi

    echo "fatal:site-auth"
    return 0
}

# ---------------------------------------------------------------------------
# orphan_guard - databases left behind with no site_config referencing them.
#
# Such a database means the site directory went away but its data survived.
# Installing on top of it would be destructive, so stop and say how to
# proceed. A leftover database with ZERO tables is simply dropped: nothing
# can be lost and `bench new-site` cannot create a name that is taken.
# Databases referenced by any site under sites/ are left alone, so a stack
# hosting more than one site is unaffected.
# ---------------------------------------------------------------------------
orphan_guard() {
    _og_ref=""
    for _og_cfg in "$BENCH_DIR"/sites/*/site_config.json; do
        [ -f "$_og_cfg" ] || continue
        _og_d=$(json_get "$_og_cfg" db_name 2>/dev/null || true)
        [ -n "$_og_d" ] && _og_ref="$_og_ref $_og_d"
    done

    _og_all=$(root_sql "SELECT TABLE_SCHEMA FROM INFORMATION_SCHEMA.SCHEMATA \
        WHERE TABLE_SCHEMA NOT IN ('information_schema','mysql','performance_schema','sys')" \
        2>/dev/null || true)
    [ -n "$_og_all" ] || return 0

    for _og_db in $_og_all; do
        case " $_og_ref " in
        *" $_og_db "*) continue ;;
        esac
        _og_t=$(table_count "$_og_db")
        _og_t=${_og_t:-0}
        if [ "$_og_t" -gt 0 ] 2>/dev/null; then
            echo "[backend] FATAL: database '$_og_db' still has $_og_t table(s)," >&2
            echo "[backend] but no site under sites/ references it." >&2
            echo "[backend] The site directory was removed while its data survived." >&2
            echo "[backend] Fix: restore sites/<site>/site_config.json, or start over" >&2
            echo "[backend]      with 'docker compose down -v' (DESTROYS the data)." >&2
            return 1
        fi
        echo "[backend] dropping empty leftover database '$_og_db' (0 tables)"
        if ! root_sql "DROP DATABASE \`$_og_db\`" >/dev/null 2>&1; then
            if db_exists "$_og_db"; then
                echo "[backend] FATAL: could not drop the empty leftover database '$_og_db'" >&2
                echo "[backend] $(mysql_error)" >&2
                return 1
            fi
            echo "[backend] leftover database '$_og_db' was already gone"
        fi
    done
    return 0
}

# ===========================================================================
# install-state helpers
#
# Two marker files record whether a SETUP finished - something `site_verdict`
# structurally cannot answer, because a setup that died after `bench
# new-site` still leaves behind a perfectly working database:
#
#   sites/.productix_started.<site>          written before the first step
#                                            that can die
#   sites/<site>/.productix_install_complete written only after every step
#                                            AND every post_install hook
#                                            succeeded
#
# The completion marker lives inside the site directory on purpose: removing
# sites/<site> to rebuild the site removes it too, so a rebuilt site cannot
# inherit the old one's "finished" state. The started flag sits beside it in
# sites/ because it has to exist before the site directory does.
#
# Absence of BOTH markers means the site predates this scheme (it was created
# by an older checkout). Such a site is adopted as complete rather than
# re-provisioned, because re-running its post_install hooks would re-seed -
# i.e. delete - data that may already matter.
# ===========================================================================
STARTED_FLAG="$BENCH_DIR/sites/.productix_started.$SITE"
COMPLETE_FLAG="$BENCH_DIR/sites/$SITE/.productix_install_complete"
HOOKS_DONE="$BENCH_DIR/sites/$SITE/.productix_hooks_done"

# installed_apps - the space-separated contents of the site's `installed_apps`
# DB global (tabDefaultValue): what the DATABASE says is installed, not what a
# file claims. Read directly instead of through `bench list-apps`, because it
# is the same value and does not pay for a python start-up on every boot.
installed_apps() {
    _ia_db=$(site_config_get db_name 2>/dev/null || true)
    if [ -z "$_ia_db" ]; then
        return 0
    fi
    _ia_raw=$(root_sql "SELECT defvalue FROM \`$_ia_db\`.\`tabDefaultValue\`
                        WHERE defkey='installed_apps'" 2>/dev/null || true)
    if [ -z "$_ia_raw" ]; then
        return 0
    fi
    _ia_out=$(printf '%s' "$_ia_raw" | python3 -c '
import json, sys
try:
    apps = json.loads(sys.stdin.read().strip())
    if isinstance(apps, list):
        sys.stdout.write(" ".join(str(a) for a in apps))
except Exception:
    pass
' 2>/dev/null || true)
    printf '%s' "$_ia_out"
}

mark_install_started() {
    mkdir -p "$BENCH_DIR/sites" 2>/dev/null || true
    {
        echo "site=$SITE"
        echo "started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date)"
    } > "$STARTED_FLAG" 2>/dev/null ||
        echo "[backend] warning: could not write $STARTED_FLAG" >&2
    return 0
}

# mark_install_complete - the only thing that ever retires the started flag.
# Written as one redirect, so a half-written file can never pass for a
# finished install.
mark_install_complete() {
    if {
        echo "site=$SITE"
        echo "modules=$PRODUCTIX_APPS_LIST"
        echo "completed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date)"
    } > "$COMPLETE_FLAG" 2>/dev/null; then
        rm -f "$STARTED_FLAG" 2>/dev/null || true
    else
        echo "[backend] warning: could not write $COMPLETE_FLAG" >&2
    fi
    return 0
}

# sync_apps_txt - sites/apps.txt is what makes `bench install-app` accept an
# app at all (frappe refuses anything not listed there), so it has to contain
# every module this run may install. It is rewritten as a UNION with whatever
# is already listed: dropping a line would break a module that is installed
# but no longer selected, and nothing here ever uninstalls anything.
sync_apps_txt() {
    _sat_tmp="$BENCH_DIR/sites/apps.txt.tmp"
    {
        printf 'frappe\nerpnext\n'
        [ -f "$BENCH_DIR/sites/apps.txt" ] && cat "$BENCH_DIR/sites/apps.txt"
        for _sat_app in "$@"; do
            printf '%s\n' "$_sat_app"
        done
    } | awk 'NF && !seen[$0]++' > "$_sat_tmp" 2>/dev/null || true
    if [ -s "$_sat_tmp" ]; then
        mv -f "$_sat_tmp" "$BENCH_DIR/sites/apps.txt"
    fi
    rm -f "$_sat_tmp" 2>/dev/null || true
    return 0
}

pip_install_app() {
    [ -d "$BENCH_DIR/apps/$1" ] || return 0
    if ! "$ENV_PIP" install -e "$BENCH_DIR/apps/$1" --quiet; then
        report_fatal "pip install -e apps/$1 failed"
        return 1
    fi
    return 0
}

# install_app_if_missing <app> - the reconcile primitive.
#
# An app the database already reports as installed is skipped; anything else
# is installed. The skip is what makes this idempotent - frappe's install_app
# would happily redo an installed app's whole setup if we let it reach that
# code - and it is checked HERE rather than relying on install_app's own
# `if not force and name in installed_apps` guard, because we deliberately do
# pass --force.
#
# --force is required, not cosmetic: when a site's installed_apps row no longer
# lists an app but that app's rows still exist (the state after a setup died
# part way, or after a module was removed from the row only), frappe's
# add_module_defs() inserts the app's Module Def and blows up with
# `Duplicate entry '<Module>' for key 'PRIMARY'` unless ignore_if_duplicate is
# set - which is exactly what force does. It also re-syncs the app's doctype
# JSON. What it does NOT do is drop anything: tables and documents are never
# touched by install_app, and the destructive re-seed lives in our own
# post_install hook runner, which force does not reach (see
# run_post_install_hooks). tests/README.md section 2 documents the same
# --force for installing a module onto a site whose tables already exist.
install_app_if_missing() {
    if px_list_has "$INSTALLED_APPS" "$1"; then
        echo "[backend] $1 is already installed - skipping"
        return 0
    fi
    echo "[backend] installing $1"
    if ! bench --site "$SITE" install-app "$1" --force; then
        report_fatal "install-app failed for '$1' - the reason is in the log above"
        return 1
    fi
    INSTALLED_APPS=$(px_list_add "$INSTALLED_APPS" "$1")
    INSTALLED_NEW=$(px_list_add "$INSTALLED_NEW" "$1")
    INSTALLED_ANY=1
    return 0
}

# run_post_install_hooks <app>...
#
# Optional per-module seed, declared by the module itself:
#     "post_install": "<dotted.path.callable>"
# Generic by design - any module (present or future) seeds data by adding one
# field to its own manifest; this script never names an app. Hooks run in
# install order (platform app first), one per module.
#
# It only ever runs while a site is being PROVISIONED (fresh/resume), i.e.
# before the completion marker exists. That is deliberate: a post_install is a
# RE-SEED - it can delete transactional rows - so executing one on a site that
# already finished installing would destroy data. A module added to a
# completed site is installed by the reconcile step instead, and its hook is
# announced but never executed (announce_pending_seed).
#
# A hook that fails does NOT abort the boot: the site itself has verified, and
# exiting would only trade one readable error for an endless restart loop. The
# failure is recorded instead, which keeps the completion marker unwritten, so
# the next start retries it and says so again.
run_post_install_hooks() {
    for _rph_app in "$@"; do
        for _rph_manifest in "$BENCH_DIR/apps/$_rph_app"/*/productix_module.json; do
            [ -f "$_rph_manifest" ] || continue
            _rph_hook=$(px_manifest_get "$_rph_manifest" post_install)
            [ -n "$_rph_hook" ] || continue
            if [ -f "$HOOKS_DONE" ] && grep -Fqx "$_rph_app=$_rph_hook" "$HOOKS_DONE" 2>/dev/null; then
                echo "[backend] post_install for $_rph_app already ran - skipping"
                continue
            fi
            echo "[backend] running post_install hook for $_rph_app: $_rph_hook"
            if bench --site "$SITE" execute "$_rph_hook"; then
                printf '%s=%s\n' "$_rph_app" "$_rph_hook" >> "$HOOKS_DONE" 2>/dev/null || true
            else
                HOOK_FAILURES=$(px_list_add "$HOOK_FAILURES" "$_rph_app")
                echo "[backend] !! post_install FAILED for $_rph_app ($_rph_hook)" >&2
                echo "[backend] !! The site itself is fine and still serves, but the" >&2
                echo "[backend] !! install is NOT complete: no completion marker is" >&2
                echo "[backend] !! written, so the next start runs this hook again." >&2
            fi
        done
    done
    return 0
}

# announce_pending_seed <app>... - a module installed on a site that has
# FINISHED installing. Its post_install is not run automatically (it would
# re-seed a live site), so say exactly that, with the command, once - this
# only ever fires on the boot that did the install.
announce_pending_seed() {
    for _aps_app in "$@"; do
        for _aps_manifest in "$BENCH_DIR/apps/$_aps_app"/*/productix_module.json; do
            [ -f "$_aps_manifest" ] || continue
            _aps_hook=$(px_manifest_get "$_aps_manifest" post_install)
            [ -n "$_aps_hook" ] || continue
            echo "[backend]" >&2
            echo "[backend] NOTE: $_aps_app was installed on a site that had already" >&2
            echo "[backend] finished its setup, so its post_install was NOT run:" >&2
            echo "[backend]   $_aps_hook" >&2
            echo "[backend] post_install re-seeds data and is only ever executed while" >&2
            echo "[backend] a site is being created. Seed this module yourself with:" >&2
            echo "[backend]" >&2
            echo "[backend]   docker compose exec backend bash -c 'cd /home/frappe/frappe-bench && bench --site $SITE execute $_aps_hook'" >&2
            echo "[backend]" >&2
        done
    done
    return 0
}

# report_module_status - printed on EVERY start, just before gunicorn. It is
# the one place that answers "did I actually get the modules I asked for?",
# which used to be recoverable only from the log of a container that had
# already exited - which is exactly how a .env asking for recipe+core was
# seen running KPI without anyone noticing.
report_module_status() {
    _rms_installed=$(installed_apps)
    _rms_missing=$(px_list_missing "$PRODUCTIX_APPS_LIST" "$_rms_installed")
    _rms_modules=$(px_modules_installed "$_rms_installed")
    _rms_extra=$(px_list_missing "$_rms_modules" "$PRODUCTIX_APPS_LIST")

    echo "[backend] ------------------- module status -------------------"
    echo "[backend] selected : $PRODUCTIX_APPS_LIST"
    echo "[backend] installed: ${_rms_installed:-<none>}"
    if [ -n "$_rms_missing" ]; then
        echo "[backend] MISSING  : $_rms_missing <- selected in .env, NOT installed"
    else
        echo "[backend] missing  : (none)"
    fi
    if [ -n "$_rms_extra" ]; then
        echo "[backend] extra    : $_rms_extra <- installed, no longer selected."
        echo "[backend]            Left in place: uninstalling would DROP ITS TABLES."
        echo "[backend]            Remove it by hand if that is really wanted:"
        echo "[backend]              bench --site $SITE uninstall-app <module>"
    else
        echo "[backend] extra    : (none)"
    fi
    echo "[backend] -----------------------------------------------------"
    return 0
}

# ===========================================================================
# 1. module selection and validation - runs on EVERY start
#
# The rules are NOT here: they live in docker/productix-selection.sh, which
# setup_site.sh and deploy.sh source too. One implementation means the
# Docker bootstrap, a manual setup and an update cannot resolve the same
# PRODUCTIX_APPS to three different lists. Moved out of the install branch on
# purpose: a bad PRODUCTIX_APPS now fails fast whether or not the site
# already exists.
# ===========================================================================
if [ ! -f /usr/local/bin/productix-selection.sh ]; then
    echo "[backend] FATAL: docker/productix-selection.sh is not mounted at" >&2
    echo "           /usr/local/bin/productix-selection.sh - the module" >&2
    echo "           selection cannot be resolved, so nothing can be installed." >&2
    exit 1
fi
tr -d '\r' < /usr/local/bin/productix-selection.sh > /tmp/productix-selection.sh
# shellcheck disable=SC1091
. /tmp/productix-selection.sh

# explicit selection from .env - see the module-selection block in
# .env.example for the format and for examples of every valid shape.
# Empty means "every module discovered", never "no modules".
px_select "$BENCH_DIR/apps" "${PRODUCTIX_APPS:-}"
PRODUCTIX_APPS_LIST="$PX_SELECTION"

# shellcheck disable=SC2086
set -- $PRODUCTIX_APPS_LIST
if [ "$#" -eq 0 ]; then
    echo "[backend] ERROR: no productix apps discovered under $BENCH_DIR/apps" >&2
    echo "           and PRODUCTIX_APPS is empty." >&2
    exit 1
fi

# A selection that is not on this host must fail HERE, listing what IS
# available, rather than deep inside `pip install` on a half-built site.
if [ -n "$PX_UNAVAILABLE" ]; then
    echo "[backend] ERROR: PRODUCTIX_APPS selected modules that are not present:$PX_UNAVAILABLE" >&2
    echo "           Modules available under $BENCH_DIR/apps:" >&2
    for candidate in "$BENCH_DIR"/apps/productix_*; do
        [ -d "$candidate" ] || continue
        echo "             ${candidate##*/}" >&2
    done
    echo "           Fix PRODUCTIX_APPS in .env, or drop the missing folder into apps/." >&2
    exit 1
fi

# A manifest can point at a module this checkout does not carry. That is a
# broken dependency, not a broken selection, so it is loud but not fatal -
# stopping here would take down a site that is otherwise fine.
if [ -n "$PX_DEP_GAPS" ]; then
    echo "[backend] WARNING: a module declares 'requires' an app that is not in apps/:$PX_DEP_GAPS" >&2
    echo "           The missing module will not be available at runtime." >&2
fi

echo "[backend] selected modules:$PRODUCTIX_APPS_LIST"

# ===========================================================================
# 2. decide what has to happen
#
# site_verdict only ever answers "is there a working database?". The two
# marker files answer the other question - "did the SETUP that created this
# database finish?" - and only between them do they say whether the selection
# in .env was really applied.
# ===========================================================================
VERDICT=$(site_verdict)
echo "[backend] site verdict: $VERDICT"

HOOK_FAILURES=""
INSTALLED_APPS=""
INSTALLED_NEW=""
INSTALLED_ANY=0
MODE=sync
LEGACY=0

case "$VERDICT" in
ok)
    if [ -f "$STARTED_FLAG" ] && [ ! -f "$COMPLETE_FLAG" ]; then
        MODE=resume
        echo "[backend] site '$SITE' has an unfinished install: its completion" >&2
        echo "[backend] marker was never written, so the previous setup died" >&2
        echo "[backend] part way through. Finishing it now." >&2
    elif [ ! -f "$COMPLETE_FLAG" ]; then
        MODE=sync
        LEGACY=1
        echo "[backend] site '$SITE' verified; it predates install tracking, so" >&2
        echo "[backend] it is adopted as complete. No post_install hook is ever" >&2
        echo "[backend] re-run on an adopted site - re-seeding could delete" >&2
        echo "[backend] data this deployment already depends on." >&2
    else
        MODE=sync
        echo "[backend] site '$SITE' verified - comparing the selection with the site"
    fi
    ;;
fresh)
    MODE=fresh
    ;;
reinstall)
    echo "[backend] site '$SITE' is half-created (config without a usable" >&2
    echo "[backend] database) - rebuilding it. Existing rows: 0, so nothing" >&2
    echo "[backend] can be lost." >&2
    MODE=fresh
    ;;
fatal:*)
    report_fatal "${VERDICT#fatal:}"
    exit 1
    ;;
*)
    report_fatal "unrecognised verdict '$VERDICT'"
    exit 1
    ;;
esac

if [ "$MODE" = "fresh" ] || [ "$MODE" = "resume" ]; then
    # -----------------------------------------------------------------------
    # credentials
    #
    # Only creating a site needs the administrator password. A resume never
    # runs `bench new-site`, so it must be able to finish an install that
    # died before someone had filled the whole of .env in.
    # -----------------------------------------------------------------------
    if [ -z "${MARIADB_ROOT_PASSWORD:-}" ]; then
        report_fatal no-credentials
        exit 1
    fi
    if [ "$MODE" = "fresh" ] && [ -z "${ADMIN_PASSWORD:-}" ]; then
        report_fatal no-credentials
        exit 1
    fi

    # Re-read the verdict now that we know we are about to touch data, and
    # refuse to start if root cannot authenticate.
    case "$(root_state)" in
    ok) ;;
    auth)
        report_fatal root-auth
        exit 1
        ;;
    *)
        report_fatal root-connect
        exit 1
        ;;
    esac

    if ! orphan_guard; then
        exit 1
    fi

    # -----------------------------------------------------------------------
    # wipe a half-created site before rebuilding it
    # -----------------------------------------------------------------------
    if [ "$VERDICT" = "reinstall" ]; then
        _half_db=$(site_config_get db_name || true)
        if [ -n "$_half_db" ] && db_exists "$_half_db"; then
            _half_t=$(table_count "$_half_db")
            if [ "${_half_t:-0}" -gt 0 ] 2>/dev/null; then
                report_fatal "refusing to drop '$_half_db': it holds $_half_t table(s)"
                exit 1
            fi
            echo "[backend] dropping empty half-created database '$_half_db'"
            if ! root_sql "DROP DATABASE \`$_half_db\`" >/dev/null 2>&1; then
                # Already gone is fine - it held nothing. Still present means
                # the drop itself failed, which must stop the boot rather
                # than let `bench new-site` collide with the name.
                if db_exists "$_half_db"; then
                    report_fatal "could not drop the empty half-created database '$_half_db': $(mysql_error)"
                    exit 1
                fi
                echo "[backend] database '$_half_db' was already gone"
            fi
        fi
        echo "[backend] removing the half-created site directory sites/$SITE"
        rm -rf "$BENCH_DIR/sites/$SITE"
    fi

    # Every step below can die. Flag it FIRST, so that the next start resumes
    # here instead of looking at a working database and concluding that
    # nothing was left to do.
    mark_install_started

    echo "[backend] ========================================"
    echo "[backend] mode: $MODE"
    echo "[backend] installing:$PRODUCTIX_APPS_LIST"
    echo "[backend] ========================================"

    # bench resolves apps through sites/apps.txt - write it before new-site,
    # exactly like setup_site.sh does.
    sync_apps_txt "$@"

    for app in "$@"; do
        pip_install_app "$app"
    done

    if [ "$MODE" = "fresh" ]; then
        echo "[backend] creating site '$SITE'"
        if ! bench new-site "$SITE" \
            --mariadb-root-password "$MARIADB_ROOT_PASSWORD" \
            --admin-password "$ADMIN_PASSWORD" \
            --no-mariadb-socket \
            --force; then
            report_fatal install-failed
            exit 1
        fi
    else
        echo "[backend] resuming the unfinished setup of '$SITE'"
    fi

    # What the database actually holds right now - this is what makes the
    # loop below a reconcile rather than a blind reinstall. `bench new-site`
    # has just put frappe there, or, on a resume, whatever the previous run
    # managed to finish.
    INSTALLED_APPS=$(installed_apps)

    install_app_if_missing erpnext
    for app in "$@"; do
        install_app_if_missing "$app"
    done

    # `bench build` must materialise a REAL directory at sites/assets/<app>.
    # A symlink left behind by an older layout would send the bundles back
    # into the bind-mounted source tree instead of the shared assets volume.
    for app in "$@"; do
        if [ -L "$BENCH_DIR/sites/assets/$app" ]; then
            rm -f "$BENCH_DIR/sites/assets/$app"
        fi
    done

    # Always run while provisioning, even when nothing new was installed: a
    # resume may have stopped before this point, and `migrate` is idempotent.
    echo "[backend] migrating and building assets"
    # developer_mode is OFF, and set here (not only in section 3) so that the
    # migrate and the post_install hooks below already run with it off.
    bench --site "$SITE" set-config developer_mode 0
    bench --site "$SITE" migrate
    bench --site "$SITE" clear-cache
    bench build --hard-link

    run_post_install_hooks "$@"

    if [ -n "$HOOK_FAILURES" ]; then
        echo "[backend] !! setup did NOT finish: post_install failed for$HOOK_FAILURES" >&2
        echo "[backend] !! No completion marker was written, so the next start" >&2
        echo "[backend] !! tries again. The site itself verified and still serves." >&2
    else
        mark_install_complete
        echo "[backend] initial setup complete"
    fi

elif [ "$MODE" = "sync" ]; then
    # -----------------------------------------------------------------------
    # A site that is already usable. The selection in .env may have changed
    # since it was created - which is exactly how a deployment asking for
    # recipe+core ended up running KPI. Install the difference, and ONLY the
    # difference: nothing is ever uninstalled automatically, because dropping
    # a module drops its tables with it.
    # -----------------------------------------------------------------------
    INSTALLED_APPS=$(installed_apps)
    MISSING_MODULES=$(px_list_missing "$PRODUCTIX_APPS_LIST" "$INSTALLED_APPS")

    if [ -n "$MISSING_MODULES" ]; then
        echo "[backend] ========================================"
        echo "[backend] the selection and the site disagree."
        echo "[backend] selected :$PRODUCTIX_APPS_LIST"
        echo "[backend] installed: $INSTALLED_APPS"
        echo "[backend] installing only:$MISSING_MODULES"
        echo "[backend] ========================================"

        for app in $MISSING_MODULES; do
            if [ ! -d "$BENCH_DIR/apps/$app" ]; then
                report_fatal "selected module '$app' has no folder under $BENCH_DIR/apps"
                exit 1
            fi
        done

        sync_apps_txt "$@"
        for app in $MISSING_MODULES; do
            pip_install_app "$app"
            install_app_if_missing "$app"
        done

        # This site is NOT being provisioned, so its post_install hooks stay
        # untouched - running one would re-seed (delete) data that exists.
        # shellcheck disable=SC2086
        announce_pending_seed $INSTALLED_NEW

        echo "[backend] migrating and building assets"
        bench --site "$SITE" set-config developer_mode 0
        bench --site "$SITE" migrate
        bench --site "$SITE" clear-cache
        bench build --hard-link
    else
        echo "[backend] the site already has every selected module"
    fi

    if [ "$LEGACY" = "1" ]; then
        mark_install_complete
        echo "[backend] site '$SITE' adopted as complete (modules: $PRODUCTIX_APPS_LIST)"
    fi
fi

# ===========================================================================
# 3. re-verify before gunicorn - the reason a bad password used to become an
#    endless 500/502 instead of a stopped container with a readable cause.
# ===========================================================================
FINAL_VERDICT=$(site_verdict)
if [ "$FINAL_VERDICT" != "ok" ]; then
    case "$FINAL_VERDICT" in
    fatal:*)
        report_fatal "${FINAL_VERDICT#fatal:}"
        ;;
    *)
        report_fatal verify-failed
        ;;
    esac
    exit 1
fi
echo "[backend] site verified: '$SITE' is answering"

# ---------------------------------------------------------------------------
# developer_mode must be OFF in a deployment. With it on, Frappe writes
# standard documents (Number Cards, Reports, Workspaces, DocTypes ...) back
# into the bind-mounted app source tree whenever they are saved. That tree
# belongs to the host checkout and is not writable by the `frappe` user, so
# the save dies with PermissionError - which `bench execute` then re-raises
# as a misleading NameError, aborting an install mid-hook.
#
# It is re-asserted on EVERY start rather than only during install, so a site
# created before this rule existed heals itself on its next boot. This is a
# deployment, not a development checkout: docs/on-premise.md documents the
# flag as "dev only". Failure here is reported but not fatal - the site is
# already verified and must still serve.
# ---------------------------------------------------------------------------
if ! bench --site "$SITE" set-config developer_mode 0; then
    echo "[backend] warning: could not force developer_mode off" >&2
fi

# The answer to "did this deployment actually get the modules I chose?" -
# printed on EVERY start, next to the selection that was received, so a
# mismatch is visible without digging the log out of a container that has
# since exited. Recomputed here rather than reused from section 2, because
# this is the state gunicorn is about to serve.
report_module_status

# Hand over to the image's default backend process (gunicorn).
echo "[backend] starting gunicorn"
exec /usr/local/bin/start.sh
