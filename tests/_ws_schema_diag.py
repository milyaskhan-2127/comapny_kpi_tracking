# Workspace child-field storage + live row key sets per site — raw python.
# env/bin/python tests/_ws_schema_diag.py <site>
import json
import os
import sys

import frappe

site = sys.argv[1]
os.makedirs(os.path.join(os.path.expanduser("~"), "logs"), exist_ok=True)
for d in (
    os.path.join(os.path.abspath("sites"), site, "logs"),
    os.path.join(os.path.dirname(os.path.abspath("sites")), site, "logs"),
):
    os.makedirs(d, exist_ok=True)
frappe.init(site=site, sites_path=os.path.abspath("sites"))
frappe.connect()
frappe.set_user("Administrator")

meta = frappe.get_meta("Workspace")
fields = {
    df.fieldname: {"fieldtype": df.fieldtype, "options": df.options}
    for df in meta.fields
    if df.fieldname in ("links", "shortcuts", "charts", "number_cards", "content_blocks")
}
ws = frappe.get_doc("Workspace", "Recipe Management").as_dict(no_nulls=False)
live = {}
for k in ("links", "shortcuts", "charts", "number_cards"):
    v = ws.get(k)
    info = {"type": type(v).__name__}
    if isinstance(v, list):
        info["count"] = len(v)
        if v:
            info["row0_keys"] = sorted(v[0].keys())
    elif isinstance(v, str):
        info["str_head"] = v[:120]
    live[k] = info
print("WS_SCHEMA_DIAG", json.dumps({"site": site, "meta_fields": fields, "live": live}))
