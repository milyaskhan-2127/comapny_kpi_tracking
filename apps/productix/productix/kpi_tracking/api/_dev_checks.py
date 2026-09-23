# -*- coding: utf-8 -*-
"""Development-time verification helpers for the KPI Tracking rebuild.

Invoke via:
  bench --site productix.local execute productix.kpi_tracking.api._dev_checks.verify_state
  bench --site productix.local execute productix.kpi_tracking.api._dev_checks.run_acceptance
  bench --site productix.local execute productix.kpi_tracking.api._dev_checks.cleanse_test_data clear=1

None of these functions are whitelisted; they are dev/debug only.
"""
import json

import frappe


def _p(line=""):
    print(line)


def sync_workspace_from_json():
    """Push the workspace JSON (source of truth) into the live site document.

    bench migrate does not overwrite existing Workspace docs, so run this once
    after editing kpi_tracking/workspace/company_tracking_system/company_tracking_system.json.
    """
    import json as json_mod

    path = "/home/frappe/frappe-bench/apps/productix/productix/kpi_tracking/workspace/company_tracking_system/company_tracking_system.json"
    data = json_mod.load(open(path))
    ws = frappe.get_doc("Workspace", "Company Tracking System")

    ws.links = []
    for l in data.get("links", []):
        ws.append("links", {
            "label": l.get("label"),
            "link_to": l.get("link_to"),
            "link_type": l.get("link_type"),
            "link_count": l.get("link_count", 0),
            "is_query_report": l.get("is_query_report", 0),
            "hidden": l.get("hidden", 0),
            "onboard": l.get("onboard", 0),
            "type": l.get("type"),
        })

    ws.shortcuts = []
    for s in data.get("shortcuts", []):
        ws.append("shortcuts", {
            "label": s.get("label"),
            "link_to": s.get("link_to"),
            "type": s.get("type"),
            "doc_view": s.get("doc_view", ""),
            "color": s.get("color", "Grey"),
        })

    ws.roles = []
    for r in data.get("roles", []):
        ws.append("roles", {"role": r.get("role")})

    ws.content = data.get("content", ws.content)
    ws.icon = data.get("icon", ws.icon)
    ws.indicator_color = data.get("indicator_color", ws.indicator_color)
    ws.label = data.get("label", ws.label)
    ws.title = data.get("title", ws.title)
    ws.public = data.get("public", ws.public)

    ws.save(ignore_permissions=True)
    frappe.db.commit()
    _p("Workspace synced from JSON: links={} shortcuts={} roles={}".format(
        len(ws.links), len(ws.shortcuts), len(ws.roles)))


def rename_110_debug():
    """Repeat the 110->HOME rename manually with full error output."""
    from productix.kpi_tracking.doctype.kpi_department.kpi_department import _normalize_code

    _p("=== Error Log (canonicalization) ===")
    try:
        for r in frappe.db.sql(
            "SELECT name, method, error, creation FROM `tabError Log` ORDER BY creation DESC LIMIT 3"
        ):
            _p("  {} | {} | created {} | {}".format(r.name, r.method, r.creation, (r.error or "")[:500]))
    except Exception as e:
        _p("  (could not read error log: {})".format(e))

    _p("")
    _p("=== Manual rename attempt ===")
    _p("  _normalize_code('Home') = " + str(_normalize_code("Home")))
    _p("  exists HOME: " + str(frappe.db.exists("KPI Department", "HOME")))
    _p("  exists 110: " + str(bool(frappe.db.exists("KPI Department", "110"))))
    try:
        frappe.rename_doc("KPI Department", "110", "HOME", force=True, ignore_permissions=True)
        frappe.db.set_value("KPI Department", "HOME", "department_code", "HOME", update_modified=False)
        frappe.db.commit()
        _p("  RENAME OK -> HOME exists now: " + str(frappe.db.exists("KPI Department", "HOME")))
    except Exception as e:
        import traceback

        _p("  RENAME FAILED: {}".format(e))
        _p(traceback.format_exc())


def reset_patch_log():
    """Delete the 0001 patch log entry so the (fixed) patch re-runs on migrate."""
    patch = "productix.migrations.productix.fix_kpi_department_records"
    n = frappe.db.delete("Patch Log", {"patch": patch})
    frappe.db.commit()
    _p("Deleted {} Patch Log entries for {}".format(n, patch))


def backup_roundtrip():
    """Export -> preview -> (reject unconfirmed restore) -> confirmed restore."""
    from productix.api.backup import (
        export_kpi_json_backup,
        preview_backup_file,
        restore_backup_file,
    )

    _p("=== Export KPI JSON backup ===")
    exp = export_kpi_json_backup()
    _p("  message: " + str(exp.get("message")))
    filename = exp.get("filename")
    _p("  filename: " + str(filename))

    _p("")
    _p("=== Preview (dry-run, must not touch DB) ===")
    prev = preview_backup_file(filename)
    _p("  kind: " + str(prev.get("kind")))
    _p("  total_records: " + str(prev.get("total_records")))
    _p("  doctype_counts: " + json.dumps(prev.get("doctype_counts"), default=str)[:600])

    _p("")
    _p("=== Restore without confirm=1 (must be rejected) ===")
    try:
        restore_backup_file(filename, confirm=0)
        _p("  UNEXPECTED: restore without confirm succeeded!")
    except Exception as e:
        _p("  rejected as expected: " + str(e)[:150])

    _p("")
    _p("=== Restore with confirm=1 ===")
    try:
        res = restore_backup_file(filename, confirm=1)
        _p("  restore result: " + json.dumps(res, default=str)[:400])
    except Exception as e:
        import traceback

        _p("  RESTORE FAILED: {}".format(e))
        _p(traceback.format_exc())


def page_script_check():
    """Compare roles of key pages as stored in the DB."""
    for name in ("kpi-company-overview", "backups", "machine-health", "kpi-data-entry-page", "kpi-setup-wizard", "kpi-action-center", "kpi-department-dashboard"):
        row = frappe.db.get_value(
            "Page",
            name,
            ["name", "standard"],
            as_dict=True,
        )
        if not row:
            _p("{} -> MISSING".format(name))
            continue
        _p("{} -> standard={}".format(name, row.standard))
        _p("   roles: {}".format([r.role for r in frappe.get_all(
            "Has Role", filters={"parent": name, "parenttype": "Page"}, fields=["role"])]))


def sync_pages_from_json(target=None, remove_stale=1):
    """Re-apply Page roles from each page's JSON so DB matches source-of-truth.

    Frappe's migrate does not overwrite existing Page rows, so tightening roles
    in a JSON file never reaches the DB. This pushes the JSON roles back down.
    Usage: ... execute productix.kpi_tracking.api._dev_checks.sync_pages_from_json
    """
    import os
    import json as json_mod

    base = "/home/frappe/frappe-bench/apps/productix/productix/kpi_tracking/page"
    names = []
    if target:
        names = [target]
    else:
        for d in sorted(os.listdir(base)):
            if os.path.isdir(os.path.join(base, d)):
                names.append(d)

    for name in names:
        json_path = os.path.join(base, name, name + ".json")
        if not os.path.exists(json_path):
            _p("{} -> no JSON, skipped".format(name))
            continue
        doc = json_mod.load(open(json_path))
        if doc.get("doctype") != "Page":
            continue
        ptr = doc.get("name")
        if not frappe.db.exists("Page", ptr):
            _p("{} -> page not in DB, skipped".format(ptr))
            continue
        pg = frappe.get_doc("Page", ptr)
        expect = [r.get("role") for r in doc.get("roles") or []]
        pg.roles = []
        for role in expect:
            pg.append("roles", {"role": role})
        pg.flags.ignore_permissions = True
        pg.save(ignore_permissions=True)
        frappe.db.commit()
        _p("{} -> roles set to {}".format(ptr, expect))


def table_columns():
    """Print columns of KPI Alert / Machine Reading / Machine Health Log."""
    for tbl in ("KPI Alert", "Machine Reading", "Machine Health Log"):
        _p(tbl + ": " + ",".join(frappe.db.get_table_columns(tbl)))


def patch_status():
    """Show applied state of the 0001 migration and the module import path."""
    _p("=== Patch Log (productix 0001) ===")
    rows = frappe.db.sql(
        "SELECT patch FROM `tabPatch Log` WHERE patch LIKE %s ORDER BY patch",
        ("%productix%",),
    )
    for r in rows or []:
        _p("  " + r[0])
    _p("")
    _p("=== Import path check ===")
    try:
        from productix.kpi_tracking.doctype.kpi_department.kpi_department import _normalize_code as nc

        _p("  kpi_department._normalize_code imports OK")
        _p("  _normalize_code('Home') = " + str(nc("Home")))
        _p("  _normalize_code('110') = " + str(nc("110")))
    except Exception as e:
        _p("  IMPORT ERROR: {}".format(e))


def verify_state():
    """Sanity-check the canonical records, pages, workspace and registry."""
    _p("=== KPI Department records ===")
    for r in frappe.db.sql(
        "SELECT name, department_name, is_active FROM `tabKPI Department` ORDER BY department_name",
        as_dict=True,
    ):
        _p("  {:<24} | {} | active: {}".format(r.name, r.department_name, r.is_active))

    _p("")
    _p("=== KPI Definition referencing 110/home ===")
    k = frappe.db.sql(
        "SELECT name, kpi_name, department FROM `tabKPI Definition` WHERE department LIKE '%110%' OR department='home'",
        as_dict=True,
    )
    _p("  " + str(k))

    _p("")
    _p("=== KPI CEO Access rows ===")
    for r in frappe.db.sql(
        "SELECT name, user, access_scope, is_active FROM `tabKPI CEO Access`", as_dict=True
    ):
        _p("  {} | {} | {} | active: {}".format(r.name, r.user, r.access_scope, r.is_active))

    _p("")
    _p("=== Pages machine-health / backups ===")
    for r in frappe.db.sql(
        "SELECT name, title, standard FROM `tabPage` WHERE name IN ('machine-health','backups')",
        as_dict=True,
    ):
        _p("  {} | {} | {}".format(r.name, r.title, r.standard))

    _p("")
    _p("=== Workspace Company Tracking System ===")
    ws = frappe.get_doc("Workspace", "Company Tracking System")
    for l in ws.links:
        if "Backup" in l.label or "Machine Health" in l.label or "Company Overview" in l.label:
            _p("  LINK: {} -> {} ({})".format(l.label, l.link_to, l.link_type))
    _p("  roles: " + ",".join(sorted({r.role for r in ws.roles})))

    _p("")
    _p("=== Registry ===")
    try:
        from productix.kpi_tracking.services import registry

        registry.invalidate_cache(None, None)
        depts = registry.get_departments()
        _p("  registry departments: {}".format(len(depts)))
        for d in depts[:6]:
            _p("    - {} | {}".format(d.get("name"), d.get("department_name")))
    except Exception as e:
        _p("  registry error: {}".format(e))


def cleanse_test_data(clear=0):
    """Remove records created by the acceptance test run (safe cleanup).

    Usage: bench ... execute ...cleanse_test_data clear=1
    """
    if not int(clear):
        _p("Dry run - pass clear=1 to actually delete test records.")
        return
    prefixes = ("TST-", "TSTK-", "TSTM-", "TSTMT-", "KPI-CEO-TST")
    depts = frappe.db.get_all("KPI Department", filters={"name": ["like", "%TST%"]}, pluck="name")
    kpis = frappe.db.get_all("KPI Definition", filters={"name": ["like", "%TST%"]}, pluck="name")
    machines = frappe.db.get_all("Machine", filters={"name": ["like", "%TST%"]}, pluck="name")
    mtypes = frappe.db.get_all("Machine Type", filters={"name": ["like", "%TST%"]}, pluck="name")
    ceos = frappe.db.get_all("KPI CEO Access", filters={"name": ["like", "%TST%"]}, pluck="name")
    users = frappe.db.get_all("User", filters={"email": ["like", "%tst%"]}, pluck="name")

    _p("Deleting test docs: depts={} kpis={} machines={} mtypes={} ceos={} users={}".format(
        len(depts), len(kpis), len(machines), len(mtypes), len(ceos), len(users)))

    for name in ceos:
        try:
            frappe.delete_doc("KPI CEO Access", name, force=1)
        except Exception as e:
            _p("  ceo delete fail {}: {}".format(name, e))
    for name in mtypes:
        try:
            frappe.delete_doc("Machine Type", name, force=1)
        except Exception as e:
            _p("  mtype delete fail {}: {}".format(name, e))
    for name in machines:
        try:
            frappe.delete_doc("Machine", name, force=1)
        except Exception as e:
            _p("  machine delete fail {}: {}".format(name, e))
    for name in kpis:
        try:
            frappe.delete_doc("KPI Definition", name, force=1)
        except Exception as e:
            _p("  kpi delete fail {}: {}".format(name, e))
    for name in depts:
        try:
            frappe.delete_doc("KPI Department", name, force=1)
        except Exception as e:
            _p("  dept delete fail {}: {}".format(name, e))
    for email in users:
        if email == "Administrator":
            continue
        try:
            u = frappe.get_doc("User", email)
            if u.enabled:
                u.enabled = 0
                u.flags.ignore_permissions = True
                u.save(ignore_permissions=True)
        except Exception as e:
            _p("  user disable fail {}: {}".format(email, e))
    frappe.db.commit()
    _p("Cleanup complete.")


def run_acceptance():
    """Exercise the full sync chain the same way the UI does:

    create dept -> kpi -> machine(type+linked) -> machine kpi -> 2 CEOs w/ different access
    then verify CEO isolation and context endpoints.
    """
    from productix.kpi_tracking.security.permissions import (
        get_ceo_authorized_departments,
        get_ceo_authorized_kpis,
        get_user_role,
    )
    from productix.kpi_tracking.api.user_management import save_user
    from productix.kpi_tracking.api import dashboard as dashboard_api
    from productix.kpi_tracking.api import machine as machine_api

    admin = frappe.session.user
    frappe.set_user("Administrator")

    _p("=== 1) Create Department TST-DEPT ===")
    dept = frappe.get_doc(
        {
            "doctype": "KPI Department",
            "name": "TST-DEPT",
            "department_name": "Test Dept Alpha",
            "department_code": "TSTD",
            "is_active": 1,
        }
    )
    try:
        dept.insert(ignore_permissions=True)
    except frappe.DuplicateEntryError:
        frappe.db.rollback()
        dept = frappe.get_doc("KPI Department", "TSTD")
    _p("   dept -> " + dept.name)

    _p("=== 2) Create KPI TSTK-01 (dept TST-DEPT) ===")
    kpi = frappe.get_doc(
        {
            "doctype": "KPI Definition",
            "name": "TSTK-01",
            "kpi_name": "Test KPI Alpha",
            "kpi_code": "TSTKA",
            "department": dept.name,
            "is_active": 1,
            "unit": "Count",
            "threshold_type": "Higher is better",
        }
    )
    try:
        kpi.insert(ignore_permissions=True)
    except frappe.DuplicateEntryError:
        frappe.db.rollback()
        kpi = frappe.get_doc("KPI Definition", "TSTKA")
    _p("   kpi -> " + kpi.name + " dept=" + kpi.department)

    _p("=== 3) Create Machine Type (with parameters) ===")
    mtype = frappe.get_doc(
        {
            "doctype": "Machine Type",
            "type_code": "TSTMT1",
            "type_name": "Test Machine Type One",
            "department": dept.name,
            "is_active": 1,
            "parameters": [
                {
                    "parameter_name": "Temperature",
                    "parameter_code": "TEMP",
                    "parameter_category": "Temperature",
                    "unit": "C",
                    "weight": 1.0,
                    "normal_min": 20,
                    "normal_max": 80,
                    "warning_max": 90,
                    "critical_max": 100,
                },
            ],
        }
    )
    try:
        mtype.insert(ignore_permissions=True)
    except frappe.DuplicateEntryError:
        frappe.db.rollback()
        mtype = frappe.get_doc("Machine Type", "TSTMT1")
    _p("   mtype -> " + mtype.name)

    _p("=== 4) Create Machine linked to KPI ===")
    machine = frappe.get_doc(
        {
            "doctype": "Machine",
            "machine_code": "TSTM01",
            "machine_name": "Test Machine Alpha",
            "department": dept.name,
            "machine_type": mtype.name,
            "is_active": 1,
            "status": "Active",
            "linked_kpis": [{"kpi": kpi.name}],
        }
    )
    try:
        machine.insert(ignore_permissions=True)
    except frappe.DuplicateEntryError:
        frappe.db.rollback()
        machine = frappe.get_doc("Machine", "TSTM01")
        if not [x for x in machine.get("linked_kpis") or [] if x.kpi == kpi.name]:
            machine.append("linked_kpis", {"kpi": kpi.name})
            machine.save(ignore_permissions=True)
    _p("   machine -> " + machine.name + " type=" + machine.machine_type)
    _p("   linked kpis: " + str([x.kpi for x in machine.get("linked_kpis") or []]))

    _p("=== 5) Create 2 CEO users with different access (via save_user API) ===")
    c1 = _make_ceo_via_api("tst-ceo1@productix.local", "CEO One", dept.name, kpi.name, specific=True)
    c2 = _make_ceo_via_api("tst-ceo2@productix.local", "CEO Two", dept.name, kpi.name, specific=False)
    _p("   ceo1 -> " + c1 + " (Selected Departments Only / View Specific KPIs)")
    _p("   ceo2 -> " + c2 + " (All Departments / View All KPIs)")

    frappe.db.commit()

    _p("")
    _p("=== 6) CEO isolation checks ===")
    for user in ("tst-ceo1@productix.local", "tst-ceo2@productix.local"):
        _p("   -- " + user)
        _p("      role: " + get_user_role(user))
        depts = get_ceo_authorized_departments(user)
        kpis = get_ceo_authorized_kpis(user, department=dept.name)
        _p("      authorized departments: " + str(depts))
        _p("      authorized KPIs in TST-DEPT: " + str(kpis))

    _p("")
    _p("=== 7) get_user_context for each CEO (as that user) ===")
    for user in ("tst-ceo1@productix.local", "tst-ceo2@productix.local"):
        frappe.set_user(user)
        try:
            ctx = dashboard_api.get_user_context()
            _p("   {} -> role={} is_ceo={} ceo_config={}".format(
                user, ctx.get("role"), ctx.get("is_ceo"), json.dumps(ctx.get("ceo_config"))))
        except Exception as e:
            _p("   {} -> ERROR: {}".format(user, e))
        finally:
            frappe.set_user(admin)

    _p("")
    _p("=== 8) Machine endpoints ===")
    frappe.set_user(admin)
    try:
        detail = machine_api.get_machine_detail("TSTM01")
        _p("   get_machine_detail keys: " + ",".join(sorted(detail.keys())))
        _p("   linked_kpis: " + json.dumps(detail.get("linked_kpis")))
        _p("   machine_type_name: " + str(detail.get("machine_type_name")))
    except Exception as e:
        _p("   get_machine_detail ERROR: {}".format(e))

    _p("")
    _p("=== 9) get_users shows both CEOs with configs ===")
    try:
        users = _users_internal()
        for u in users:
            if u.get("user") in ("tst-ceo1@productix.local", "tst-ceo2@productix.local"):
                _p("   {} -> role={} active={} ceo_config_present={}".format(
                    u.get("user"), u.get("role"), u.get("is_active"), bool(u.get("ceo_config"))))
    except Exception as e:
        _p("   get_users ERROR: {}".format(e))

    _p("")
    _p("DONE - acceptance chain exercised.")


def _users_internal():
    from productix.kpi_tracking.api.user_management import get_users

    return get_users().get("users") or []


def _make_ceo_via_api(email, full_name, dept_name, kpi_name, specific):
    from productix.kpi_tracking.api.user_management import save_user

    ceo_access = {
        "access_scope": "Selected Departments Only" if specific else "All Departments",
        "can_view_company_overview": 1,
        "can_view_machines": 1,
        "departments": [
            {
                "department": dept_name,
                "access_level": "View Specific KPIs" if specific else "View All KPIs",
            }
        ],
        "kpis": [{"department": dept_name, "kpi": kpi_name}] if specific else [],
    }
    res = save_user(
        email=email,
        full_name=full_name,
        role="CEO",
        ceo_access=json.dumps(ceo_access),
        new_password="Test@1234",
        is_active=1,
    )
    return res["user"]