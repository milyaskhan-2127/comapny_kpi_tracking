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
#                    credentials all authenticate         -> skip install
#     reinstall      half-created site: config exists but the schema has
#                    zero tables, or the database was never created
#                                                       -> reinstall
#     fatal:<reason> cannot proceed safely                -> stop, with an
#                    actionable message; gunicorn never starts
#
# Everything below is module-agnostic: apps are discovered by globbing
# `apps/productix_*/productix_*/productix_module.json`, so this file never
# names an application and any combination of modules installs the same way.
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
# 1. module discovery and validation - runs on EVERY start
#
# Moved out of the install branch on purpose: a bad PRODUCTIX_APPS now fails
# fast whether or not the site already exists, and it is the same code path
# for every combination, because it only ever reads the manifests it finds.
# ===========================================================================
PLATFORM_APP=""
DISCOVERED_APPS=""
for manifest in "$BENCH_DIR"/apps/productix_*/productix_*/productix_module.json; do
    [ -f "$manifest" ] || continue
    app=$(basename "$(dirname "$(dirname "$manifest")")")
    if grep -qE '"always_enabled"[[:space:]]*:[[:space:]]*true' "$manifest"; then
        PLATFORM_APP="$app"
    else
        DISCOVERED_APPS="$DISCOVERED_APPS $app"
    fi
done

if [ -n "${PRODUCTIX_APPS:-}" ]; then
    # explicit selection from .env - see the module-selection block in
    # .env.example for the format and for examples of every valid shape
    PRODUCTIX_APPS_LIST=$(printf '%s' "$PRODUCTIX_APPS" | tr ',' ' ')
else
    PRODUCTIX_APPS_LIST="$DISCOVERED_APPS"
fi

# the platform app (manifest flagged always_enabled) is never optional
if [ -n "$PLATFORM_APP" ]; then
    case " $PRODUCTIX_APPS_LIST " in
    *" $PLATFORM_APP "*) ;;
    *) PRODUCTIX_APPS_LIST="$PLATFORM_APP $PRODUCTIX_APPS_LIST" ;;
    esac
fi

# shellcheck disable=SC2086
set -- $PRODUCTIX_APPS_LIST
if [ "$#" -eq 0 ]; then
    echo "[backend] ERROR: no productix apps discovered under $BENCH_DIR/apps" >&2
    echo "           and PRODUCTIX_APPS is empty." >&2
    exit 1
fi

# A selection that is not on this host must fail HERE, listing what IS
# available, rather than deep inside `pip install` on a half-built site.
PRODUCTIX_MISSING=""
for app in "$@"; do
    [ -d "$BENCH_DIR/apps/$app" ] || PRODUCTIX_MISSING="$PRODUCTIX_MISSING $app"
done
if [ -n "$PRODUCTIX_MISSING" ]; then
    echo "[backend] ERROR: PRODUCTIX_APPS selected modules that are not present:$PRODUCTIX_MISSING" >&2
    echo "           Modules available under $BENCH_DIR/apps:" >&2
    for candidate in "$BENCH_DIR"/apps/productix_*; do
        [ -d "$candidate" ] || continue
        echo "             ${candidate##*/}" >&2
    done
    echo "           Fix PRODUCTIX_APPS in .env, or drop the missing folder into apps/." >&2
    exit 1
fi

echo "[backend] selected modules:$PRODUCTIX_APPS_LIST"

# ===========================================================================
# 2. decide what has to happen
# ===========================================================================
VERDICT=$(site_verdict)
echo "[backend] site verdict: $VERDICT"

INSTALL=0
case "$VERDICT" in
ok)
    echo "[backend] site '$SITE' verified - skipping setup"
    ;;
fresh)
    INSTALL=1
    ;;
reinstall)
    echo "[backend] site '$SITE' is half-created (config without a usable" >&2
    echo "[backend] database) - rebuilding it. Existing rows: 0, so nothing" >&2
    echo "[backend] can be lost." >&2
    INSTALL=1
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

if [ "$INSTALL" = "1" ]; then
    # -----------------------------------------------------------------------
    # credentials: without them `bench new-site` cannot run
    # -----------------------------------------------------------------------
    if [ -z "${MARIADB_ROOT_PASSWORD:-}" ] || [ -z "${ADMIN_PASSWORD:-}" ]; then
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

    echo "[backend] ========================================"
    echo "[backend] installing:$PRODUCTIX_APPS_LIST"
    echo "[backend] ========================================"

    # bench resolves apps through sites/apps.txt - write it before new-site,
    # exactly like setup_site.sh does.
    {
        printf 'frappe\nerpnext\n'
        for app in "$@"; do printf '%s\n' "$app"; done
    } > "$BENCH_DIR/sites/apps.txt"

    for app in "$@"; do
        "$ENV_PIP" install -e "$BENCH_DIR/apps/$app" --quiet
    done

    echo "[backend] creating site '$SITE'"
    if ! bench new-site "$SITE" \
        --mariadb-root-password "$MARIADB_ROOT_PASSWORD" \
        --admin-password "$ADMIN_PASSWORD" \
        --no-mariadb-socket \
        --force; then
        report_fatal install-failed
        exit 1
    fi

    echo "[backend] installing erpnext"
    bench --site "$SITE" install-app erpnext

    for app in "$@"; do
        echo "[backend] installing $app"
        bench --site "$SITE" install-app "$app" --force
    done

    # `bench build` must materialise a REAL directory at sites/assets/<app>.
    # A symlink left behind by an older layout would send the bundles back
    # into the bind-mounted source tree instead of the shared assets volume.
    for app in "$@"; do
        if [ -L "$BENCH_DIR/sites/assets/$app" ]; then
            rm -f "$BENCH_DIR/sites/assets/$app"
        fi
    done

    echo "[backend] migrating and building assets"
    # developer_mode is OFF, and set here (not only in section 3) so that the
    # migrate and the post_install hooks below already run with it off.
    bench --site "$SITE" set-config developer_mode 0
    bench --site "$SITE" migrate
    bench --site "$SITE" clear-cache
    bench build --hard-link

    # -----------------------------------------------------------------------
    # Optional per-module post-install hook, declared by the module itself:
    #     "post_install": "<dotted.path.callable>"
    # Generic by design - any module (present or future) can seed data by
    # adding one field to its own manifest. This script never names an app.
    # Hooks run in install order (platform app first), one per module.
    # -----------------------------------------------------------------------
    for app in "$@"; do
        for manifest in "$BENCH_DIR"/apps/"$app"/*/productix_module.json; do
            [ -f "$manifest" ] || continue
            hook=$(sed -n 's/^[[:space:]]*"post_install"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$manifest")
            [ -n "$hook" ] || continue
            echo "[backend] running post_install hook for $app: $hook"
            bench --site "$SITE" execute "$hook"
        done
    done

    echo "[backend] initial setup complete"
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

# Hand over to the image's default backend process (gunicorn).
echo "[backend] starting gunicorn"
exec /usr/local/bin/start.sh
