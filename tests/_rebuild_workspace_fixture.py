#!/usr/bin/env python3
"""Rebuild stale workspace fixtures from the pre-migration DB (zero-loss repair).

Problem: apps/productix_kpi/productix_kpi/fixtures/workspace.json is an EARLY
export that predates the Machine Health card/links, Machine Health + Backup
Manager shortcuts, and the KPI CEO role. On `bench migrate`, fixture import
runs LAST (after module-dir workspace sync), so this stale fixture overwrote
the live workspace during the modular migration (row-level evidence:
tests/ACCEPTANCE_EVIDENCE.md §12 — Workspace Link -6, Shortcut -2, Has Role -1).

Fix: reconstruct the workspace doc EXACTLY as it existed in the pre-migration
dump (restored as scratch DB `_precheck`, queried cross-schema through frappe's
own connection) and write it to BOTH representations (the fixture list and the
module-dir doc) so the two cannot diverge again.

Also prints a read-only recipe fixture-vs-module consistency check.

Usage (bench root, direct python):
    env/bin/python tests/_rebuild_workspace_fixture.py
Exit 0 = rebuilt + recipe consistent.
"""
import json
import os
import sys

import frappe

BENCH = os.getcwd()
SITE = "productix.local"
PRE_DB = "_precheck"
KPI_FIXTURE = os.path.join(
    BENCH, "apps/productix_kpi/productix_kpi/fixtures/workspace.json"
)
KPI_MODULE = os.path.join(
    BENCH,
    "apps/productix_kpi/productix_kpi/kpi_tracking/workspace/"
    "company_tracking_system/company_tracking_system.json",
)
RECIPE_FIXTURE = os.path.join(
    BENCH, "apps/productix_recipe/productix_recipe/fixtures/workspace.json"
)
RECIPE_MODULE = os.path.join(
    BENCH,
    "apps/productix_recipe/productix_recipe/recipe_management/workspace/"
    "recipe_management/recipe_management.json",
)

# bookkeeping columns not present in exported fixture children
BOOK = {
    "name", "creation", "modified", "modified_by", "owner", "docstatus", "idx",
    "_user_tags", "_comments", "_assign", "_liked_by",
}
CHILD_TABLES = {
    "links": "Workspace Link",
    "shortcuts": "Workspace Shortcut",
    "roles": "Has Role",
    "charts": "Workspace Chart",
}
WS = "Company Tracking System"

sites_path = os.path.abspath("sites")
os.makedirs(os.path.join(sites_path, SITE, "logs"), exist_ok=True)
os.makedirs(os.path.join(os.getcwd(), SITE, "logs"), exist_ok=True)
frappe.init(site=SITE, sites_path=sites_path)
frappe.connect()

tables = {
    r["name"]
    for r in frappe.db.sql(
        "SELECT table_name AS name FROM information_schema.tables "
        "WHERE table_schema=%s",
        (PRE_DB,),
        as_dict=True,
    )
}
if not tables:
    frappe.destroy()
    raise SystemExit(f"scratch DB {PRE_DB} not found — restore the pre-dump first")

row = frappe.db.sql(
    f"SELECT * FROM {PRE_DB}.`tabWorkspace` WHERE name=%s", (WS,), as_dict=True
)
if not row:
    frappe.destroy()
    raise SystemExit("workspace not found in _precheck")
row = row[0]

children = {}
for field, dt in CHILD_TABLES.items():
    t = "tab" + dt
    if t not in tables:
        children[field] = []
        continue
    rs = frappe.db.sql(
        f"SELECT * FROM {PRE_DB}.`{t}` WHERE parent=%s AND "
        f"parenttype='Workspace' ORDER BY idx",
        (WS,),
        as_dict=True,
    )
    children[field] = [
        {k: v for k, v in r.items() if k not in BOOK} for r in rs
    ]
frappe.destroy()

template = json.load(open(KPI_FIXTURE, encoding="utf-8"))
t0 = template[0] if isinstance(template, list) else template

doc = {}
for k in t0:
    if k in children:
        continue
    doc[k] = row[k] if k in row else t0[k]
for k, v in children.items():
    doc[k] = v
doc.setdefault("doctype", "Workspace")

# template says list but DB stored JSON text (or vice versa) -> normalize
for k, v in list(doc.items()):
    if isinstance(v, str) and isinstance(t0.get(k), list):
        try:
            doc[k] = json.loads(v) if v.strip() else []
        except Exception:  # noqa: BLE001
            doc[k] = t0[k]

with open(KPI_FIXTURE, "w", encoding="utf-8") as f:
    json.dump([doc], f, indent=2, ensure_ascii=False, default=str)
    f.write("\n")
with open(KPI_MODULE, "w", encoding="utf-8") as f:
    json.dump(doc, f, indent=1, ensure_ascii=False, default=str)
    f.write("\n")

print(
    "REBUILT_FIXTURE links=%d shortcuts=%d roles=%d charts=%d"
    % tuple(len(children[k]) for k in ("links", "shortcuts", "roles", "charts"))
)
print("doc keys:", sorted(doc))

# ---- read-only consistency check: recipe fixture vs module doc ----
rf = json.load(open(RECIPE_FIXTURE, encoding="utf-8"))
rm = json.load(open(RECIPE_MODULE, encoding="utf-8"))
fd = rf[0] if isinstance(rf, list) else rf
rd = rm if isinstance(rm, dict) else rm[0]


def norm(d):
    out = {}
    for k, v in d.items():
        if k in CHILD_TABLES:
            out[k] = [
                {ck: cv for ck, cv in c.items() if ck not in BOOK}
                for c in (v or [])
            ]
        else:
            out[k] = v
    return out


nfd, nrd = norm(fd), norm(rd)
rc = 0
if nfd == nrd:
    print("RECIPE_FIXTURE_VS_MODULE: EQUAL")
else:
    print("RECIPE_FIXTURE_VS_MODULE: DIVERGENT")
    rc = 1
    for k in sorted(set(nfd) | set(nrd)):
        if nfd.get(k) != nrd.get(k):
            if k in CHILD_TABLES:
                print(
                    f"  {k}: fixture={len(nfd.get(k) or [])} "
                    f"module={len(nrd.get(k) or [])}"
                )
            else:
                a = str(nfd.get(k))[:90]
                b = str(nrd.get(k))[:90]
                print(f"  {k}: fixture={a!r} module={b!r}")
print("REBUILD_OK")
sys.exit(rc)
