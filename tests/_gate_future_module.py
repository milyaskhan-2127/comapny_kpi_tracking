# -*- coding: utf-8 -*-
"""Generic entitlement-gate proof for a FUTURE module key.

Proves gate_request is registry-resolved: productix_core has no hard-coded
knowledge of `manufacturing`, yet disabling its entitlement row must 403 the
scaffold's whitelisted method with the standard gate message, and re-enabling
must restore it. Runs inside the backend container against gunicorn :8000
with an explicit site header (tests/README.md §5).
"""
import json
import http.cookiejar
import urllib.request

SITE = "productix-c.local"
BASE = "http://localhost:8000"
METHOD = "productix_manufacturing.api.manufacturing_ping"
ENTITLE = "/api/method/productix_core.modules.entitlement.set_entitlement"

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def call(path, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"X-Frappe-Site-Name": SITE, "Content-Type": "application/json"},
    )
    try:
        with opener.open(req, timeout=30) as r:
            return r.status, r.read().decode()[:220]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:220]


results = []
st, b = call("/api/method/login", "POST",
             {"usr": "Administrator", "pwd": "Admin@123"})
results.append(("LOGIN", st))

st, b = call("/api/method/" + METHOD)
results.append(("MFG_BASELINE", st))

st, b = call(ENTITLE, "POST", {"module_key": "manufacturing", "enabled": 0})
results.append(("DISABLE", st))

st, b = call("/api/method/" + METHOD)
gate_msg = "disabled on this site" in b
results.append(("MFG_DISABLED_CALL", st, "GATE_MSG" if gate_msg else b))

st, b = call("/api/method/ping")
results.append(("CORE_PING_WHILE_MFG_DISABLED", st))

st, b = call(ENTITLE, "POST", {"module_key": "manufacturing", "enabled": 1})
results.append(("REENABLE", st))

st, b = call("/api/method/" + METHOD)
results.append(("MFG_REENABLED_CALL", st))

for row in results:
    print(" | ".join(str(x) for x in row))

expect = {
    "LOGIN": 200,
    "MFG_BASELINE": 200,
    "DISABLE": 200,
    "MFG_DISABLED_CALL": 403,
    "CORE_PING_WHILE_MFG_DISABLED": 200,
    "REENABLE": 200,
    "MFG_REENABLED_CALL": 200,
}
ok = all(st == expect.get(name, st) for name, st, *_ in [(r[0], r[1]) for r in results])
ok = ok and any(len(r) > 2 and r[2] == "GATE_MSG" for r in results)
print("FUTURE_MODULE_GATE:", "PASS" if ok else "FAIL")
raise SystemExit(0 if ok else 1)
