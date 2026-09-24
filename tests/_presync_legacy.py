# -*- coding: utf-8 -*-
# tests/_presync_legacy.py — pre-sync legacy productix app schema ahead of the
# pre_model_sync legacy patch (fix_kpi_department_records needs synced columns).
import frappe
import frappe.model.sync  # noqa: F401  (ensures the module attribute is loaded)

frappe.model.sync.sync_for("productix", force=1)
frappe.db.commit()
print("PRESYNC_OK columns:", end=" ")
import pymysql
cur = frappe.db.sql("SHOW COLUMNS FROM `tabKPI Department` LIKE 'location'", as_list=True)
print(cur)
print("PRESYNC_RC:", 0 if cur else 1)