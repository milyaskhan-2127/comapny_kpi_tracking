#!/bin/sh
# ============================================================================
# Productix ERP - frontend container entrypoint
#
# Renders the parametrized nginx template (no hard-coded site names and no
# hard-coded upstream addresses), waits until the backend can actually SERVE,
# then starts nginx.
#
# POSIX sh only: compose runs this with `sh`, and compose also strips CR
# before exec so a Windows checkout cannot break it either.
# ============================================================================
set -eu

TEMPLATE=/etc/nginx/conf.d/frappe.conf.template
CONF=/etc/nginx/conf.d/frappe.conf
SITE_NAME="${NGINX_SITE_NAME:-${FRAPPE_SITE_NAME_HEADER:-productix.local}}"

# ---------------------------------------------------------------------------
# Upstreams come from compose's environment, never from a literal in the
# template. BACKEND is also what the readiness gate below probes, so the
# address nginx proxies to and the address we wait on are the same string and
# cannot drift apart.
# ---------------------------------------------------------------------------
BACKEND="${BACKEND:-}"
SOCKETIO="${SOCKETIO:-}"

if [ -z "$BACKEND" ]; then
    echo "[frontend] ERROR: BACKEND is not set (expected e.g. 'backend:8000')." >&2
    echo "[frontend]        nginx would proxy to a blank upstream; refusing to" >&2
    echo "[frontend]        start rather than serve a broken proxy." >&2
    exit 1
fi
if [ -z "$SOCKETIO" ]; then
    echo "[frontend] ERROR: SOCKETIO is not set (expected e.g. 'websocket:9000')." >&2
    echo "[frontend]        Same reason as BACKEND - no blank proxy target." >&2
    exit 1
fi

if [ ! -f "$TEMPLATE" ]; then
    echo "[frontend] ERROR: nginx template $TEMPLATE is missing (docker-compose.yml mount)." >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# The warming page: what nginx serves while nothing is listening upstream.
#
# It must live somewhere this container can genuinely write. The image runs as
# uid 1000, not root, so the obvious system paths (/opt, /usr/share/nginx) are
# read-only and mkdir there fails - try the explicit override first, then
# locations that are writable by construction. An unwritable override falls
# back instead of crash-looping.
# ---------------------------------------------------------------------------
warming_dir=""
if [ -n "${FRONTEND_WARMING_DIR:-}" ]; then
    if mkdir -p "$FRONTEND_WARMING_DIR" 2>/dev/null && [ -w "$FRONTEND_WARMING_DIR" ]; then
        warming_dir="$FRONTEND_WARMING_DIR"
    else
        echo "[frontend] WARNING: FRONTEND_WARMING_DIR=$FRONTEND_WARMING_DIR is not" >&2
        echo "[frontend]          writable - falling back to a location that is." >&2
    fi
fi
if [ -z "$warming_dir" ]; then
    for _cand in /tmp/productix-warming "${HOME:-/tmp}/productix-warming"; do
        if mkdir -p "$_cand" 2>/dev/null && [ -w "$_cand" ]; then
            warming_dir="$_cand"
            break
        fi
    done
fi
if [ -z "$warming_dir" ]; then
    echo "[frontend] ERROR: no writable directory for the warming page." >&2
    echo "[frontend]        Tried FRONTEND_WARMING_DIR, /tmp and \$HOME." >&2
    exit 1
fi

# printf rather than a heredoc: this file is run by `sh -c` through compose,
# and every line is an argument - no shell expansion happens inside them.
{
    printf '%s\n' \
        '<!doctype html>' \
        '<html lang="en">' \
        '<head>' \
        '<meta charset="utf-8">' \
        '<meta http-equiv="refresh" content="5">' \
        '<meta name="viewport" content="width=device-width,initial-scale=1">' \
        '<title>Starting up</title>' \
        '<style>' \
        ':root{color-scheme:light dark}' \
        'body{margin:0;min-height:100vh;display:grid;place-items:center;' \
        'font:16px/1.6 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#0f172a;color:#e2e8f0}' \
        'main{max-width:34rem;padding:2rem;text-align:center}' \
        'h1{margin:0 0 .5rem;font-size:1.5rem;font-weight:600}' \
        'p{margin:0 0 1.5rem;color:#94a3b8}' \
        '.bar{height:4px;border-radius:2px;background:#1e293b;overflow:hidden}' \
        '.bar span{display:block;height:100%;width:40%;background:#38bdf8;' \
        'animation:slide 1.2s ease-in-out infinite}' \
        '@keyframes slide{0%{transform:translateX(-100%)}100%{transform:translateX(350%)}}' \
        '</style>' \
        '</head>' \
        '<body>' \
        '<main>' \
        '<h1>Starting up&hellip;</h1>' \
        '<p>The application is still preparing itself. This page reloads every' \
        '5 seconds on its own.</p>' \
        '<div class="bar"><span></span></div>' \
        '</main>' \
        '</body>' \
        '</html>'
} > "$warming_dir/index.html"

# ---------------------------------------------------------------------------
# Render the template. Anything still carrying a placeholder afterwards is a
# bug in THIS script or in the template, and would mean nginx silently
# proxying to a literal "__BACKEND_UPSTREAM__" - so fail loudly instead.
# ---------------------------------------------------------------------------
# shellcheck disable=SC2016
sed -e "s|__SITE_NAME__|${SITE_NAME}|g" \
    -e "s|__BACKEND_UPSTREAM__|${BACKEND}|g" \
    -e "s|__SOCKETIO_UPSTREAM__|${SOCKETIO}|g" \
    -e "s|__WARMING_DIR__|${warming_dir}|g" \
    "$TEMPLATE" > "$CONF"

if grep -qE '__[A-Z][A-Z0-9_]*__' "$CONF"; then
    echo "[frontend] ERROR: unsubstituted placeholder(s) in the rendered config:" >&2
    grep -oE '__[A-Z][A-Z0-9_]*__' "$CONF" | sort -u >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Readiness gate: do not hand traffic to an upstream that is not there yet.
#
# compose's short-form `depends_on` waits only for the backend CONTAINER to
# start, and the backend deliberately spends minutes on new-site / build /
# migrate before gunicorn binds :8000. Releasing nginx at that moment turns
# the entire boot into 502s that look exactly like a broken proxy - and like
# the two other 502 causes this repo already fixed (a stale container IP, a
# half-created site), which is what makes them so expensive to chase.
#
# The probe is deliberately the SAME request the compose healthcheck makes:
# ping WITH a Host header, because frappe resolves the site from that header.
# Without it a perfectly healthy backend answers 404 and reads as dead.
#
# On timeout nginx starts anyway, loudly: a slow first boot is delayed, never
# blocked.
# ---------------------------------------------------------------------------
WAIT_SECONDS="${FRONTEND_BACKEND_WAIT_SECONDS:-300}"
PROBE_PATH="${FRONTEND_BACKEND_PROBE_PATH:-/api/method/ping}"
PROBE_INTERVAL="${FRONTEND_BACKEND_PROBE_INTERVAL:-2}"

case "$WAIT_SECONDS" in
    ''|*[!0-9]*)
        echo "[frontend] WARNING: FRONTEND_BACKEND_WAIT_SECONDS='$WAIT_SECONDS' is not a" >&2
        echo "[frontend]          number - starting nginx with no readiness gate." >&2
        WAIT_SECONDS=0
        ;;
esac
case "$PROBE_INTERVAL" in
    ''|*[!0-9]*) PROBE_INTERVAL=2 ;;
esac
if [ "$PROBE_INTERVAL" -eq 0 ]; then
    PROBE_INTERVAL=1
fi

if ! command -v curl >/dev/null 2>&1; then
    echo "[frontend] WARNING: curl is unavailable - cannot probe the backend." >&2
    echo "[frontend]          Starting nginx without a readiness gate." >&2
    WAIT_SECONDS=0
fi

if [ "$WAIT_SECONDS" -gt 0 ]; then
    echo "[frontend] waiting up to ${WAIT_SECONDS}s for http://${BACKEND}${PROBE_PATH}"
    _elapsed=0
    _ready=0
    while [ "$_elapsed" -lt "$WAIT_SECONDS" ]; do
        if curl -fsS -m 5 -H "Host: ${SITE_NAME}" \
            "http://${BACKEND}${PROBE_PATH}" >/dev/null 2>&1; then
            _ready=1
            break
        fi
        sleep "$PROBE_INTERVAL"
        _elapsed=$((_elapsed + PROBE_INTERVAL))
    done
    if [ "$_ready" -eq 1 ]; then
        echo "[frontend] backend is serving (after ${_elapsed}s) - starting nginx"
    else
        echo "[frontend] WARNING: backend did not answer within ${WAIT_SECONDS}s." >&2
        echo "[frontend]          Starting nginx anyway: it will answer 503 with" >&2
        echo "[frontend]          Retry-After and a self-reloading page until the" >&2
        echo "[frontend]          backend comes up." >&2
    fi
fi

echo "[frontend] starting nginx (site=$SITE_NAME, backend=$BACKEND, socketio=$SOCKETIO, warming=$warming_dir)"
exec nginx -g 'daemon off;'
