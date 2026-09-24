# Full Workspace doc dump for byte-level before/after comparison — raw python.
# env/bin/python tests/_ws_dump.py <site> <workspace_name>
# Prints: WS_SHA256 <sha of canonical JSON> then WS_JSON <compact canonical JSON>
import hashlib
import json
import os
import sys

import frappe

site = sys.argv[1]
ws_name = sys.argv[2]
os.makedirs(os.path.join(os.path.expanduser("~"), "logs"), exist_ok=True)
for d in (
    os.path.join(os.path.abspath("sites"), site, "logs"),
    os.path.join(os.path.dirname(os.path.abspath("sites")), site, "logs"),
):
    os.makedirs(d, exist_ok=True)
frappe.init(site=site, sites_path=os.path.abspath("sites"))
frappe.connect()
frappe.set_user("Administrator")

if not frappe.db.exists("Workspace", ws_name):
    print(f"WORKSPACE_NOT_FOUND: {ws_name}")
    raise SystemExit(1)
ws = frappe.get_doc("Workspace", ws_name)
data = ws.as_dict(no_nulls=False)
canon = json.dumps(data, sort_keys=True, default=str, ensure_ascii=False)
print("WS_SHA256", hashlib.sha256(canon.encode("utf-8")).hexdigest())
print("WS_JSON", canon)
