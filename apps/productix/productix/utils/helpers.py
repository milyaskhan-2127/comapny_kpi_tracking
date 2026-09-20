import frappe
from frappe.utils import flt, getdate, today


def get_usable_stock(item_code, warehouse=None):
    """Helper: usable stock for an item excluding expired batches."""
    today_date = getdate(today())

    conditions = "AND sle.is_cancelled = 0 AND b.disabled = 0"
    conditions += " AND (b.expiry_date IS NULL OR b.expiry_date > %s)"

    args = [item_code, str(today_date)]

    if warehouse:
        is_group = frappe.db.get_value("Warehouse", warehouse, "is_group")
        if not is_group:
            conditions += " AND sle.warehouse = %s"
            args.append(warehouse)

    result = frappe.db.sql(f"""
        SELECT IFNULL(SUM(sle.actual_qty), 0)
        FROM `tabStock Ledger Entry` sle
        JOIN `tabBatch` b ON b.name = sle.batch_no
        WHERE sle.item_code = %s {conditions}
    """, tuple(args))

    stock_qty = flt(result[0][0]) if result else 0.0
    if stock_qty <= 0:
        b_res = frappe.db.sql(f"""
            SELECT IFNULL(SUM(batch_qty), 0)
            FROM `tabBatch`
            WHERE item = %s AND disabled = 0 AND (expiry_date IS NULL OR expiry_date > %s)
        """, (item_code, str(today_date)))
        stock_qty = flt(b_res[0][0]) if b_res else 0.0

    return stock_qty


def get_batch_status_label(batch_name):
    """Return human-readable status for a batch."""
    batch = frappe.db.get_value("Batch", batch_name, ["expiry_date", "disabled", "batch_qty"], as_dict=True)
    if not batch:
        return "Unknown"
    if batch.disabled:
        return "Disabled"
    if batch.expiry_date and getdate(batch.expiry_date) <= getdate(today()):
        return "Expired"
    if not batch.batch_qty or flt(batch.batch_qty) <= 0:
        return "Depleted"
    return "Active"
