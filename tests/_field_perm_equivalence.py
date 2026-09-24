#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Field/perm equivalence between two sites over the SHIPPED doctype set.

Walks every doctype JSON shipped by the four modular apps (no hard-coded
names), then for each site records DocField/DocPerm row counts for doctypes
present in that site's DocType table. Compares:

  * shared doctypes must match EXACTLY on field AND perm counts
  * doctypes present on one side only are reported (expected for subset
    combos, e.g. B = core+kpi lacks recipe/instruction doctypes)

Usage (from bench root inside the backend container):
  env/bin/python tests/_field_perm_equivalence.py <siteA> <siteB>

Expected historical results (tests/ACCEPTANCE_EVIDENCE.md §10):
  productix-b.local productix-c.local -> SHARED=35 MISMATCH=0 (8 NOT_IN_DB)
  productix.local   productix-c.local -> SHARED=43 MISMATCH=0

Exit 0 = every shared doctype matches (EQUIVALENT), 1 = mismatch.
"""
import glob
import json
import os
import sys

import frappe

APPS = ["productix_core", "productix_recipe", "productix_kpi",
        "productix_instruction"]
SITES_PATH = os.path.abspath("sites")


def shipped_doctypes():
    names = set()
    for app in APPS:
        pkg = os.path.join("apps", app, app)
        for p in glob.glob(os.path.join(pkg, "**", "doctype", "*", "*.json"),
                           recursive=True):
            stem = os.path.basename(p)[:-5]
            if os.path.basename(os.path.dirname(p)) != stem:
                continue  # not a doctype definition file (e.g. boilerplate)
            try:
                data = json.load(open(p, encoding="utf-8"))
            except Exception:
                continue
            if data.get("doctype") != "DocType":
                continue
            nm = data.get("name")
            if nm:
                names.add(nm)
    return names


def site_snapshot(site):
    for d in (os.path.join(SITES_PATH, site, "logs"),
              os.path.join(os.path.dirname(SITES_PATH), site, "logs")):
        os.makedirs(d, exist_ok=True)
    frappe.init(site=site, sites_path=SITES_PATH)
    frappe.connect()
    frappe.set_user("Administrator")
    # direct SQL: raw-python context has no user/permission plumbing and
    # frappe.get_all can return empty outside a full request
    present = {r[0] for r in frappe.db.sql("SELECT name FROM `tabDocType`")}
    snap, missing = {}, []
    for dt in sorted(shipped_doctypes()):
        if dt not in present:
            missing.append(dt)
            continue
        nf = frappe.db.sql(
            "SELECT COUNT(*) FROM `tabDocField` WHERE parent=%s", (dt,))[0][0]
        np = frappe.db.sql(
            "SELECT COUNT(*) FROM `tabDocPerm` WHERE parent=%s", (dt,))[0][0]
        snap[dt] = (nf, np)
    frappe.destroy()
    return snap, sorted(missing)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    site_a, site_b = sys.argv[1], sys.argv[2]
    shipped = sorted(shipped_doctypes())
    a, miss_a = site_snapshot(site_a)
    frappe.destroy()
    b, miss_b = site_snapshot(site_b)

    shared = sorted(set(a) & set(b))
    mismatches = [dt for dt in shared if a[dt] != b[dt]]
    print(f"shipped doctypes: {len(shipped)}")
    print(f"siteA {site_a}: present={len(a)} NOT_IN_DB={len(miss_a)} "
          f"{miss_a if len(miss_a) <= 10 else miss_a[:10] + ['...']}")
    print(f"siteB {site_b}: present={len(b)} NOT_IN_DB={len(miss_b)} "
          f"{miss_b if len(miss_b) <= 10 else miss_b[:10] + ['...']}")
    for dt in mismatches:
        print(f"MISMATCH {dt}: {site_a}={a[dt]} {site_b}={b[dt]}")
    verdict = "EQUIVALENT" if not mismatches else "NOT_EQUIVALENT"
    print(f"SHARED={len(shared)} MISMATCH={len(mismatches)} {verdict}")
    return 0 if not mismatches else 1


if __name__ == "__main__":
    sys.exit(main())
