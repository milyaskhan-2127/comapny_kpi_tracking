# -*- coding: utf-8 -*-
"""
Productix KPI Tracking — Migration 0001.

Fixes legacy KPI Department records so the master department list is canonical:

1. Creates the `KPI CEO` role if it is missing (fixture may not be imported yet).
2. Repairs the broken `110` / `home` legacy department: renames it to `HOME`
   (canonical code derived from `Home`) and propagates the rename to every
   dependent record (KPI Definitions, machines, assignments, alerts, ...).
3. Sweeps any other department whose primary key does not match its canonical
   code and renames it, ensuring name == department_code everywhere.
"""
import frappe


def execute():
    _ensure_kpi_ceo_role()
    _canonicalize_departments()


def _ensure_kpi_ceo_role():
    if not frappe.db.exists("Role", "KPI CEO"):
        try:
            frappe.get_doc({
                "doctype": "Role",
                "role_name": "KPI CEO",
                "desk_access": 1,
            }).insert(ignore_permissions=True)
            frappe.db.commit()
        except Exception:
            frappe.db.rollback()


def _canonicalize_departments():
    from productix.kpi_tracking.doctype.kpi_department.kpi_department import _normalize_code

    all_depts = frappe.db.get_all(
        "KPI Department",
        fields=["name", "department_name", "department_code", "location"],
        order_by="creation asc",
    )
    if not all_depts:
        return

    names = {d["name"] for d in all_depts}

    for d in all_depts:
        dept_name = (d.get("department_name") or "").strip() or d["name"]
        if d["name"] == "110" and dept_name.lower() == "home":
            dept_name = "Home"

        seed = dept_name
        if d.get("location"):
            seed += f" {d['location']}"
        canonical = _normalize_code(seed)

        # Avoid primary-key collisions when canonicalizing.
        candidate = canonical
        suffix = 2
        while candidate in names and candidate != d["name"]:
            candidate = f"{canonical}_{suffix}"
            suffix += 1
        canonical = candidate

        if d["name"] != canonical:
            if frappe.db.exists("KPI Department", canonical):
                names.add(canonical)
                continue  # canonical record already exists; dependents point at the old name — merge below
            try:
                frappe.rename_doc(
                    "KPI Department", d["name"], canonical,
                    force=True,
                )
                frappe.db.set_value(
                    "KPI Department", canonical,
                    "department_code", canonical,
                    update_modified=False,
                )
                frappe.db.commit()
            except Exception as e:
                frappe.db.rollback()
                frappe.log_error(
                    title="KPI Department Canonicalization",
                    message=f"Could not rename '{d['name']}' -> '{canonical}': {e}",
                )
                continue
            names.remove(d["name"])
            names.add(canonical)
        elif (d.get("department_code") or "") != canonical:
            frappe.db.set_value(
                "KPI Department", d["name"],
                "department_code", canonical,
                update_modified=False,
            )

    # Point any stragglers (incl. merged duplicates) at the canonical name.
    _merge_dependents_onto_canonical()


def _merge_dependents_onto_canonical():
    """If a duplicate department ever remains, re-home its dependents to the
    canonical record with the same department_code."""
    dup_codes = frappe.db.sql("""
        SELECT department_code, COUNT(*) AS c
        FROM `tabKPI Department`
        WHERE department_code IS NOT NULL AND department_code != ''
        GROUP BY department_code HAVING COUNT(*) > 1
    """, as_dict=True)
    for row in dup_codes:
        depts = frappe.db.get_all(
            "KPI Department",
            filters={"department_code": row["department_code"]},
            fields=["name", "is_active", "creation"],
            order_by="creation asc",
        )
        if not depts:
            continue
        dup_depts = sorted(depts, key=lambda x: (not x.is_active, x["creation"]))
        primary = dup_depts[0]["name"]

        for dup in dup_depts[1:]:
            old = dup["name"]
            for tbl in [
                "KPI Definition", "KPI Data Entry", "KPI Alert", "KPI Prediction",
                "KPI User Assignment", "KPI Operational Table", "KPI Operational Data",
                "Machine", "KPI Business Unit", "KPI CEO Department Access", "KPI CEO KPI Access",
            ]:
                try:
                    if not frappe.db.table_exists(tbl):
                        continue
                    cols = frappe.db.get_table_columns(tbl)
                    if "department" not in cols:
                        continue
                    frappe.db.sql(
                        "UPDATE `tab{}` SET department = %s WHERE department = %s".format(tbl),
                        (primary, old),
                    )
                except Exception:
                    continue
            frappe.db.sql("DELETE FROM `tabKPI Department` WHERE name = %s", (old,))
    frappe.db.commit()