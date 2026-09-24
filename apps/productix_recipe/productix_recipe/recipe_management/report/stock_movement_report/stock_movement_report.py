import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart(data)
    summary = get_summary(data)
    return columns, data, None, chart, summary


def get_columns():
    return [
        {"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 110},
        {"label": _("Voucher Type"), "fieldname": "voucher_type", "fieldtype": "Data", "width": 150},
        {"label": _("Voucher No"), "fieldname": "voucher_no", "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 180},
        {"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
        {"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 180},
        {"label": _("Batch"), "fieldname": "batch_no", "fieldtype": "Link", "options": "Batch", "width": 140},
        {"label": _("Qty"), "fieldname": "actual_qty", "fieldtype": "Float", "width": 100},
        {"label": _("UOM"), "fieldname": "stock_uom", "fieldtype": "Data", "width": 80},
        {"label": _("Valuation Rate"), "fieldname": "valuation_rate", "fieldtype": "Currency", "width": 130},
        {"label": _("Stock Value"), "fieldname": "stock_value_difference", "fieldtype": "Currency", "width": 130},
        {"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 150},
    ]


def get_data(filters):
    conditions = "WHERE sle.is_cancelled = 0"

    if filters:
        if filters.get("from_date"):
            conditions += " AND sle.posting_date >= %(from_date)s"
        if filters.get("to_date"):
            conditions += " AND sle.posting_date <= %(to_date)s"
        if filters.get("item_code"):
            conditions += " AND sle.item_code = %(item_code)s"
        if filters.get("voucher_type"):
            conditions += " AND sle.voucher_type = %(voucher_type)s"

    return frappe.db.sql(f"""
        SELECT
            sle.posting_date,
            sle.voucher_type,
            sle.voucher_no,
            sle.item_code,
            i.item_name,
            sle.batch_no,
            sle.actual_qty,
            sle.stock_uom,
            sle.valuation_rate,
            sle.stock_value_difference,
            sle.warehouse
        FROM `tabStock Ledger Entry` sle
        LEFT JOIN `tabItem` i ON i.name = sle.item_code
        {conditions}
        ORDER BY sle.posting_date DESC, sle.creation DESC
        LIMIT 1000
    """, filters or {}, as_dict=True)


def get_chart(data):
    if not data:
        return None
    # Daily stock flow
    from collections import defaultdict
    daily = defaultdict(float)
    for d in data:
        daily[str(d["posting_date"])] += flt(d["actual_qty"])
    dates = sorted(daily.keys())[-14:]  # last 14 days
    return {
        "data": {
            "labels": dates,
            "datasets": [{"name": _("Net Qty Change"), "values": [daily[d] for d in dates]}],
        },
        "type": "line",
        "title": _("Stock Movement — Last 14 Days"),
        "colors": ["#3498db"],
    }


def get_summary(data):
    inbound = sum(flt(d["actual_qty"]) for d in data if flt(d["actual_qty"]) > 0)
    outbound = abs(sum(flt(d["actual_qty"]) for d in data if flt(d["actual_qty"]) < 0))
    return [
        {"label": _("Total Transactions"), "value": len(data), "datatype": "Int", "indicator": "blue"},
        {"label": _("Total Inbound"), "value": inbound, "datatype": "Float", "indicator": "green"},
        {"label": _("Total Outbound"), "value": outbound, "datatype": "Float", "indicator": "red"},
    ]
