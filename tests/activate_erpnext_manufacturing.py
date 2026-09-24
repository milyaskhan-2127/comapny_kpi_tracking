# -*- coding: utf-8 -*-
"""
tests/activate_erpnext_manufacturing.py — verify/activate the ERPNext
Manufacturing module for a site (the "placeholder Manufacturing" used by
combo C / matrix M).

Frappe v15 dropped the `hidden` flag on Module Def; a module is active when
its Module Def row exists with the right app, its settings single exists, and
its workspace is present. This helper is idempotent:

  1. Creates the `Manufacturing Settings` single if missing.
  2. Verifies Module Def `Manufacturing` exists and belongs to erpnext.
  3. Verifies the `Manufacturing` workspace is present.

Usage (inside the bench container):
  cd /home/frappe/frappe-bench
  bench --site <site> console < tests/activate_erpnext_manufacturing.py
"""
import frappe


def _report(ok, name, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}: {name} {detail}")


def main():
    print("=== Activate/verify ERPNext Manufacturing (placeholder) ===")

    # 1) Manufacturing Settings single must exist
    doctype_ok = bool(frappe.db.exists("DocType", "Manufacturing Settings"))
    _report(doctype_ok, "Manufacturing Settings doctype present")
    if not doctype_ok:
        print("  FAIL: Manufacturing Settings doctype missing; is erpnext installed?")
        return

    singles = frappe.db.sql(
        "SELECT COUNT(*) FROM `tabSingles` WHERE doctype=%s", "Manufacturing Settings"
    )[0][0]
    if singles == 0:
        doc = frappe.get_doc("Manufacturing Settings")
        doc.flags.ignore_permissions = True
        doc.flags.ignore_mandatory = True
        doc.flags.ignore_links = True
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        print("  INFO: created Manufacturing Settings single")
    _report(singles > 0, "Manufacturing Settings single present", f"(fields={singles})")

    # 2) Module Def Manufacturing
    md = frappe.db.get_value("Module Def", "Manufacturing", ["app_name", "custom"], as_dict=True)
    _report(bool(md), "Module Def 'Manufacturing' exists")
    if md:
        _report(md.get("app_name") == "erpnext" and not md.get("custom"),
                "Module Def owned by erpnext", f"(app_name={md.get('app_name')!r}, custom={md.get('custom')})")

    # 3) Manufacturing workspace present
    ws = frappe.db.sql("SELECT name FROM `tabWorkspace` WHERE name=%s", "Manufacturing")
    _report(bool(ws), "Workspace 'Manufacturing' present")

    print("=== Manufacturing placeholder verified/active ===")


main()