#!/usr/bin/env python3
"""Human-readable summary of a snapshot JSON (pure stdlib, no frappe).

Usage: python tests/_snap_summary.py <snap.json>
"""
import json
import sys

d = json.load(open(sys.argv[1], encoding="utf-8"))
print("site:", d.get("site"))
print("installed:", d.get("installed_apps"))
print("reg_keys:", d.get("reg_keys"))
print("entitlement_rows:", str(d.get("entitlement_rows"))[:200])
print(
    "legacy_owned_modules:",
    [m for m, a in d.get("module_app_map", {}).items() if a == "productix"],
)
print("docfield_total:", d.get("docfield_total"), "| doctypes:", len(d["doctype_counts"]))
print("key business counts:")
for k in (
    "Recipe", "Recipe Item", "Consumption Log", "Production Order",
    "KPI Definition", "KPI Data Entry", "KPI Data Entry Value",
    "KPI Department", "KPI Alert", "Machine", "Machine Reading",
    "Instruction Message", "Message Notification", "AI Agent Log",
    "Item", "Purchase Receipt", "Batch", "Supplier", "Work Order",
    "Productix License", "DefaultValue", "DocType", "Module Def",
):
    print(f"  {k}: {d['doctype_counts'].get(k)}")
