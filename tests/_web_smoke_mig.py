# -*- coding: utf-8 -*-
# Web-level gate + module smoke on the MIGRATED site (productix-mig.local).
# Runs inside the backend container as plain python3 (no bench context).
# URL note: http.client is used (avoids the MSYS curl double-slash quirk).
import json
import http.client
import http.cookiejar
import urllib.request

HOST = "localhost:8000"
SITE = "productix-mig.local"
BASE = "http://localhost:8000"

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


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


out = []
st, body = call("/api/method/ping")
out.append(("PING", st, body))

st, body = call(
    "/api/method/login", method="POST", body={"usr": "Administrator", "pwd": "Admin@123"}
)
out.append(("LOGIN", st, body))

# --- enabled modules pass through (no 403) ---
st, body = call("/api/method/productix_recipe.api.inventory.get_user_role_context")
out.append(("RECIPE_ENABLED_CALL", st, body))

st, body = call("/api/method/productix_kpi.kpi_tracking.api.machine.get_machines")
out.append(("KPI_ENABLED_CALL", st, body))

st, body = call(
    "/api/method/productix_instruction.instruction_room.doctype.instruction_message.instruction_message.get_unread_count"
)
out.append(("INSTRUCTION_ENABLED_CALL", st, body))

# --- non-installed productix app must NOT be 403'd ---
st, body = call("/api/method/productix_ghost.smoke")
out.append(("GHOST_APP_CALL", st, body))

# --- gate enforcement: disable recipe -> expect 403, then restore -> 200 ---
st, body = call(
    "/api/method/productix_core.modules.entitlement.set_entitlement",
    method="POST",
    body={"module_key": "recipe", "enabled": 0},
)
out.append(("DISABLE_RECIPE", st, body))

st, body = call("/api/method/productix_recipe.api.inventory.get_user_role_context")
out.append(("RECIPE_DISABLED_CALL", st, body))

st, body = call(
    "/api/method/productix_core.modules.entitlement.set_entitlement",
    method="POST",
    body={"module_key": "recipe", "enabled": 1},
)
out.append(("REENABLE_RECIPE", st, body))

st, body = call("/api/method/productix_recipe.api.inventory.get_user_role_context")
out.append(("RECIPE_REENABLED_CALL", st, body))

with open("/tmp/_web_smoke_mig.txt", "w") as f:
    for name, code, b in out:
        f.write(f"{name} | HTTP {code} | {b}\n")
print("WROTE /tmp/_web_smoke_mig.txt")