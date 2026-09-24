# Residual diff between the Recipe workspace on two sources (normalized to
# ignore frappe system/metadata keys) — raw python.
# env/bin/python tests/_ws_diff_detail.py <siteA> <siteB|path.json>
# Each source: a site name, or a path ending in .json (fixture file, taking
# element [0] when it is a list). Prints up to 30 differing JSON paths.
import json
import os
import sys

import frappe

SYS = {"creation", "modified", "modified_by", "owner", "idx", "parent", "docstatus"}


def load(src):
    if src.endswith(".json") or os.path.isfile(src):
        with open(src, encoding="utf-8") as f:
            text = f.read()
        if "WS_JSON " in text:  # _ws_dump.py output file (SHA line + JSON line)
            text = text.split("WS_JSON ", 1)[1]
        data = json.loads(text)
        return data[0] if isinstance(data, list) else data
    os.makedirs(os.path.join(os.path.expanduser("~"), "logs"), exist_ok=True)
    for d in (
        os.path.join(os.path.abspath("sites"), src, "logs"),
        os.path.join(os.path.dirname(os.path.abspath("sites")), src, "logs"),
    ):
        os.makedirs(d, exist_ok=True)
    frappe.init(site=src, sites_path=os.path.abspath("sites"))
    frappe.connect()
    frappe.set_user("Administrator")
    doc = frappe.get_doc("Workspace", "Recipe Management").as_dict(no_nulls=False)
    frappe.destroy()
    return doc


def walk(a, b, path, out, limit=500):
    if len(out) >= limit:
        return
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k in SYS:
                continue
            # child-row `name` values are frappe-generated hashes that change on
            # every fixture re-import; keep only the parent doc's own name.
            if k == "name" and path != "$":
                continue
            if k not in a:
                out.append(f"{path}.{k}: ABSENT_A vs {json.dumps(b[k])[:60]}")
            elif k not in b:
                out.append(f"{path}.{k}: {json.dumps(a[k])[:60]} vs ABSENT_B")
            else:
                walk(a[k], b[k], f"{path}.{k}", out, limit)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{path}: len {len(a)}!={len(b)}")
            return
        for i, (x, y) in enumerate(zip(a, b)):
            walk(x, y, f"{path}[{i}]", out, limit)
    elif type(a) is not type(b) or a != b:
        out.append(f"{path}: {json.dumps(a, default=str)[:60]} != {json.dumps(b, default=str)[:60]}")


src_a, src_b = sys.argv[1], sys.argv[2]
A, B = load(src_a), load(src_b)
diffs = []
walk(A, B, "$", diffs)
# collapse per-index noise into unique patterns with counts
import re
from collections import Counter

patterns = Counter(re.sub(r"\[\d+\]", "[N]", d) for d in diffs)
print(
    "WS_DIFF_DETAIL",
    json.dumps(
        {
            "a": src_a,
            "b": src_b,
            "equal_modulo_system_fields": not diffs,
            "total_diffs": len(diffs),
            "patterns": dict(patterns),
        }
    ),
)
