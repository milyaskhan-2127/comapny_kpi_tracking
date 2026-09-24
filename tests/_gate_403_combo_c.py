# -*- coding: utf-8 -*-
# Gate 403 web-level evidence on the FULL-STACK combo site (productix-c.local).
# Runs inside the backend container as plain python3 (no bench context);
# hits gunicorn on localhost:8000 with the X-Frappe-Site-Name header.
# http.client/urllib avoid the MSYS curl double-slash quirk.
import json
import http.cookiejar
import urllib.request

HOST = "localhost:8000"
SITE = "productix-c.local"
BASE = "http://localhost:8000"

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

MODULES = [
    ("recipe", "productix_recipe.api.inventory.get_user_role_context"),
    ("kpi", "productix_kpi.kpi_tracking.api.machine.get_machines"),
    (
        "instruction",
        "productix_instruction.instruction_room.doctype.instruction_message.instruction_message.get_unread_count",
    ),
]

out = []


def call(path, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={
            "X-Frappe-Site-Name": SITE,
            "Content-Type": "application/json",
        },
    )
    try:
        with opener.open(req, timeout=30) as r:
            return r.status, r.read().decode()[:300]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]


st, body = call("/api/method/ping")
out.append(("PLATFORM_PING", st, body))

st, body = call(
    "/api/method/login", method="POST", body={"usr": "Administrator", "pwd": "Admin@123"}
)
out.append(("LOGIN", st, body))

# Non-installed productix app must NEVER be 403'd (registry-gated only).
st, body = call("/api/method/productix_ghost.smoke")
out.append(("GHOST_APP_CALL", st, body))

for module, method in MODULES:
    out.append(("== MODULE " + module + " ==", 0, ""))
    st, body = call("/api/method/" + method)
    out.append((module.upper() + "_BASELINE", st, body))

    st, body = call(
        "/api/method/productix_core.modules.entitlement.set_entitlement",
        method="POST",
        body={"module_key": module, "enabled": 0},
    )
    out.append(("DISABLE_" + module.upper(), st, body))

    st, body = call("/api/method/" + method)
    out.append((module.upper() + "_DISABLED_CALL", st, body))

    st, body = call("/api/method/ping")
    out.append(("PLATFORM_PING_WHILE_" + module.upper() + "_DISABLED", st, body))

    st, body = call(
        "/api/method/productix_core.modules.entitlement.set_entitlement",
        method="POST",
        body={"module_key": module, "enabled": 1},
    )
    out.append(("REENABLE_" + module.upper(), st, body))

    st, body = call("/api/method/" + method)
    out.append((module.upper() + "_REENABLED_CALL", st, body))

with open("/tmp/_gate_403_combo_c.txt", "w") as f:
    for name, code, b in out:
        f.write(f"{name} | HTTP {code} | {b}\n")
print("WROTE /tmp/_gate_403_combo_c.txt")