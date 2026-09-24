# Live workspace structure counts (links/shortcuts/roles) — raw python.
# env/bin/python tests/_ws_counts.py <site> <workspace_name>
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
print(
    "WS_COUNTS",
    json.dumps(
        {
            "name": ws.name,
            "links": len(ws.links or []),
            "shortcuts": len(ws.shortcuts or []),
            "roles": len(ws.roles or []),
            "number_cards": len(ws.number_cards or [])
            if hasattr(ws, "number_cards")
            else 0,
            "content_pages": len(ws.content_blocks or [])
            if hasattr(ws, "content_blocks")
            else 0,
        }
    ),
)
# deterministic fingerprints for byte-level before/after comparison
fp = {
    "links": sorted(
        f"{l.get('type','')}|{l.get('link_to','')}|{l.get('label','')}"
        for l in (ws.links or [])
    ),
    "shortcuts": sorted(
        f"{s.get('type','')}|{s.get('link_to','')}|{s.get('label','')}"
        for s in (ws.shortcuts or [])
    ),
    "roles": sorted(r.get("role", "") for r in (ws.roles or [])),
}
print("WS_FINGERPRINT", json.dumps(fp, sort_keys=True))
