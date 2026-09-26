#!/bin/sh
# ============================================================================
# tests/frontend_gate_check.sh — behavioural check for the two layers that
# stop a backend which is not listening from looking like a broken proxy
# (docs/deployment.md §4.2).
#
#   layer 1  docker/frontend-entrypoint.sh  holds nginx back until the
#            backend answers, then starts anyway on timeout
#   layer 2  nginx.conf.template            answers 503 + Retry-After with a
#            self-reloading page instead of 502
#
# This needs its own throwaway container: it starts and stops nginx, binds
# :8080 and points the entrypoint at addresses where nothing listens. It runs
# as the image's DEFAULT uid, so the writable-path fallback is exercised under
# the same permissions the real frontend gets. The permanent, in-stack guard is
# tests/_battery_static.sh group 4b (structure); this one is behaviour.
#
# Usage, from the repo root (host needs only docker):
#
#   docker run --rm \
#     -v "$PWD/nginx.conf.template:/etc/nginx/conf.d/frappe.conf.template:ro" \
#     -v "$PWD/docker/frontend-entrypoint.sh:/usr/local/bin/fe.sh:ro" \
#     -v "$PWD:/w:ro" \
#     frappe/erpnext:v15.121.3 sh /w/tests/frontend_gate_check.sh
#
# Exit code 0 = every check passed.
# ============================================================================
set -u

FE=/usr/local/bin/fe.sh
TPL=/etc/nginx/conf.d/frappe.conf.template
CONF=/etc/nginx/conf.d/frappe.conf
PASS=0
FAIL=0
ok()  { PASS=$((PASS + 1)); echo "  ok   $1"; }
bad() { FAIL=$((FAIL + 1)); echo "  FAIL $1"; }
stop_nginx() {
    _pidfile=$(awk '/^pid/ {print $2; exit}' /etc/nginx/nginx.conf 2>/dev/null)
    for _p in "$_pidfile" /run/nginx.pid /var/run/nginx.pid /tmp/nginx.pid; do
        if [ -n "${_p:-}" ] && [ -f "$_p" ]; then
            kill "$(cat "$_p")" 2>/dev/null
        fi
    done
    if command -v pkill >/dev/null 2>&1; then
        pkill -TERM nginx 2>/dev/null
    fi
    # wait until :8080 really is free, or the next phase would talk to the
    # nginx of the PREVIOUS phase and read its backend address
    _i=0
    while [ "$_i" -lt 8 ]; do
        if ! curl -s -o /dev/null -m 1 http://127.0.0.1:8080/ 2>/dev/null; then
            break
        fi
        sleep 1
        _i=$((_i + 1))
    done
    return 0
}

# ---------------------------------------------------------------- 1. hard fails
BACKEND= SOCKETIO=websocket:9000 NGINX_SITE_NAME=x.local sh "$FE" >/tmp/o1 2>&1
if [ $? -eq 1 ] && grep -qF 'BACKEND is not set' /tmp/o1; then
    ok "empty BACKEND is a hard, explanatory failure"
else
    bad "empty BACKEND"; cat /tmp/o1
fi

BACKEND=backend:8000 SOCKETIO= NGINX_SITE_NAME=x.local sh "$FE" >/tmp/o2 2>&1
if [ $? -eq 1 ] && grep -qF 'SOCKETIO is not set' /tmp/o2; then
    ok "empty SOCKETIO is a hard, explanatory failure"
else
    bad "empty SOCKETIO"; cat /tmp/o2
fi

# --------------------------------------------- 2. render + writable fallback
stop_nginx
BACKEND=127.0.0.1:9999 SOCKETIO=127.0.0.1:9998 NGINX_SITE_NAME=x.local \
    FRONTEND_BACKEND_WAIT_SECONDS=0 \
    FRONTEND_WARMING_DIR=/proc/definitely-not-writable \
    sh "$FE" >/tmp/o3 2>&1 &
BG=$!
sleep 3

if nginx -t >/tmp/nt 2>&1; then
    ok "nginx -t passes on the rendered config"
else
    bad "nginx -t"; cat /tmp/nt
fi
if grep -qE '__[A-Z][A-Z0-9_]*__' "$CONF"; then
    bad "a placeholder survived substitution"
else
    ok "no placeholder survives substitution"
fi
grep -qF 'set $backend_upstream 127.0.0.1:9999;' "$CONF" \
    && ok "backend upstream came from the BACKEND env var" \
    || bad "backend upstream not injected"
grep -qF 'set $socketio_upstream 127.0.0.1:9998;' "$CONF" \
    && ok "socketio upstream came from the SOCKETIO env var" \
    || bad "socketio upstream not injected"
grep -qF 'server_name x.local _;' "$CONF" \
    && ok "site name rendered" || bad "site name"
grep -qF 'error_page 502 504 =503 /_warming_up;' "$CONF" \
    && ok "502/504 are mapped to 503" || bad "error_page mapping missing"
grep -qF 'root /proc/definitely-not-writable;' "$CONF" 2>/dev/null \
    && bad "an unwritable warming dir was used anyway" \
    || ok "unwritable FRONTEND_WARMING_DIR was not used"
grep -qF 'falling back' /tmp/o3 \
    && ok "the fallback was announced loudly" || bad "fallback was silent"
if [ -s /tmp/productix-warming/index.html ]; then
    ok "warming page written to a path that is genuinely writable"
else
    bad "warming page missing"
fi
grep -qF 'http-equiv="refresh"' /tmp/productix-warming/index.html \
    && ok "warming page reloads itself" || bad "warming page does not reload"
grep -qF 'starting nginx' /tmp/o3 && ok "nginx was started after the gate" \
    || { bad "nginx was not reached"; sed -n '1,40p' /tmp/o3; }

# ------------------------------------------------------ 3. the 503 net, live
# backend is 127.0.0.1:9999 = nothing is listening
curl -s -o /dev/null -H 'Host: x.local' http://127.0.0.1:8080/ || {
    bad "nginx is not answering at all"; sed -n '1,40p' /tmp/o3
}
for _u in / /login /app; do
    _h=$(curl -s -o /tmp/body -D /tmp/hdr -H 'Host: x.local' "http://127.0.0.1:8080$_u")
    _c=$(head -n1 /tmp/hdr | cut -d' ' -f2)
    if [ "$_c" = "503" ] && grep -qi '^Retry-After: 5' /tmp/hdr; then
        ok "$_u -> 503 + Retry-After: 5 (was 502)"
    else
        bad "$_u -> status $_c $(grep -i '^Retry-After' /tmp/hdr)"
    fi
done
grep -qi '^Cache-Control: no-store' /tmp/hdr \
    && ok "warming response is not cacheable" || bad "missing Cache-Control"
if grep -qi 'Starting up' /tmp/body; then
    ok "the warming body is the self-reloading page"
else
    bad "unexpected warming body: $(head -c 120 /tmp/body)"
fi
stop_nginx

# --------------------------------------------------- 4. gate waits, then gives up
_t0=$(date +%s)
_up=0
BACKEND=127.0.0.1:9997 SOCKETIO=127.0.0.1:9996 NGINX_SITE_NAME=x.local \
    FRONTEND_BACKEND_WAIT_SECONDS=4 FRONTEND_BACKEND_PROBE_INTERVAL=1 \
    sh "$FE" >/tmp/o4 2>&1 &
BG2=$!
_t1=$_t0
while [ $((_t1 - _t0)) -lt 20 ]; do
    if curl -s -o /dev/null -H 'Host: x.local' http://127.0.0.1:8080/ 2>/dev/null; then
        _up=1
        _t1=$(date +%s)
        break
    fi
    sleep 1
    _t1=$(date +%s)
done
_el=$((_t1 - _t0))
if [ "$_up" -eq 0 ]; then
    bad "nginx never came up during the timeout test"; sed -n '1,40p' /tmp/o4
elif [ "$_el" -ge 4 ]; then
    ok "nginx was held back for the full window (started after ${_el}s, not instantly)"
else
    bad "gate did not wait (nginx reachable after ${_el}s)"
fi
grep -qF 'did not answer within 4s' /tmp/o4 \
    && ok "the timeout was reported loudly" || bad "no timeout warning"
grep -qF 'Starting nginx anyway' /tmp/o4 \
    && ok "nginx started anyway instead of blocking" || bad "gate blocked the boot"
stop_nginx

# ------------------------------------------------------ 5. gate releases fast
mkdir -p /tmp/py/api/method
: >/tmp/py/api/method/ping
if command -v python3 >/dev/null 2>&1; then _py=python3; else _py=python; fi
(cd /tmp/py && "$_py" -m http.server 8000 >/dev/null 2>&1) &
sleep 2
_t0=$(date +%s)
_up=0
BACKEND=127.0.0.1:8000 SOCKETIO=127.0.0.1:9995 NGINX_SITE_NAME=x.local \
    FRONTEND_BACKEND_WAIT_SECONDS=30 FRONTEND_BACKEND_PROBE_INTERVAL=1 \
    sh "$FE" >/tmp/o5 2>&1 &
BG3=$!
_t1=$_t0
while [ $((_t1 - _t0)) -lt 30 ]; do
    if curl -s -o /dev/null -H 'Host: x.local' http://127.0.0.1:8080/api/method/ping 2>/dev/null; then
        _up=1
        _t1=$(date +%s)
        break
    fi
    sleep 1
    _t1=$(date +%s)
done
_el=$((_t1 - _t0))
if [ "$_up" -eq 0 ]; then
    bad "nginx never came up against a serving backend"; sed -n '1,40p' /tmp/o5
elif [ "$_el" -lt 10 ]; then
    ok "a serving backend releases nginx immediately (after ${_el}s, window was 30)"
else
    bad "gate kept nginx back although the backend answered (${_el}s)"
fi
grep -qF 'backend is serving' /tmp/o5 \
    && ok "release is logged" || bad "release not logged"
_c=$(curl -s -o /dev/null -w '%{http_code}' -H 'Host: x.local' http://127.0.0.1:8080/api/method/ping)
[ "$_c" = "200" ] && ok "requests proxy through (200)" || bad "proxy returned $_c"
stop_nginx
pkill -f 'http.server 8000' 2>/dev/null
kill "$BG" "$BG2" "$BG3" 2>/dev/null

echo "RESULT PASS=$PASS FAIL=$FAIL"
[ "$FAIL" -eq 0 ]
