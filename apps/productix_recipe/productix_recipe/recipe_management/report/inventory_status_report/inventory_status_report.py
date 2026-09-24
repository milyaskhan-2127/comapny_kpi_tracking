import frappe
from frappe import _
from frappe.utils import flt, getdate, today, add_days


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart(data)
    summary = get_summary(data)
    return columns, data, None, chart, summary


def get_columns():
    return [
        {"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
        {"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 200},
        {"label": _("Category"), "fieldname": "item_group", "fieldtype": "Data", "width": 120},
        {"label": _("UOM"), "fieldname": "uom", "fieldtype": "Data", "width": 80},
        {"label": _("Usable Stock"), "fieldname": "usable_stock", "fieldtype": "Float", "width": 120},
        {"label": _("Min Stock"), "fieldname": "min_stock_qty", "fieldtype": "Float", "width": 100},
        {"label": _("Status"), "fieldname": "stock_status", "fieldtype": "Data", "width": 110},
        {"label": _("Unit Cost"), "fieldname": "unit_cost", "fieldtype": "Currency", "width": 110},
        {"label": _("Stock Value"), "fieldname": "stock_value", "fieldtype": "Currency", "width": 130},
        {"label": _("Active Batches"), "fieldname": "active_batches", "fieldtype": "Int", "width": 120},
        {"label": _("Expiring ≤7d"), "fieldname": "expiring_soon", "fieldtype": "Int", "width": 120},
        {"label": _("Expired Batches"), "fieldname": "expired_batches", "fieldtype": "Int", "width": 130},
    ]


def get_data(filters):
    today_date = getdate(today())
    alert_window = add_days(today_date, 7)

    items = frappe.get_all("Item", filters={"has_batch_no": 1, "disabled": 0},
        fields=["name", "item_name", "item_group", "stock_uom", "min_stock_qty", "valuation_rate"])

    data = []
    for item in items:
        if filters and filters.get("item_group") and item.item_group != filters["item_group"]:
            continue

        # Usable stock = sum of non-expired batch quantities
        usable = frappe.db.sql("""
            SELECT IFNULL(SUM(sle.actual_qty), 0)
            FROM `tabStock Ledger Entry` sle
            JOIN `tabBatch` b ON b.name = sle.batch_no
            WHERE sle.item_code = %s
              AND sle.is_cancelled = 0
              AND (b.expiry_date IS NULL OR b.expiry_date > %s)
              AND b.disabled = 0
        """, (item.name, str(today_date)))[0][0] or 0.0

        active_batches = frappe.db.count("Batch", {"item": item.name, "disabled": 0})
        expiring = frappe.db.count("Batch", {
            "item": item.name, "disabled": 0,
            "expiry_date": ["between", [str(today_date), str(alert_window)]]
        })
        expired = frappe.db.count("Batch", {
            "item": item.name,
            "expiry_date": ["<", str(today_date)]
        })

        min_qty = flt(item.min_stock_qty)
        if usable == 0:
            status = "🔴 Out of Stock"
        elif min_qty > 0 and usable < min_qty:
            status = "🟠 Low Stock"
        elif expiring > 0:
            status = "🟡 Expiring Soon"
        else:
            status = "🟢 OK"

        unit_cost = flt(item.valuation_rate)
        stock_value = usable * unit_cost

        data.append({
            "item_code": item.name,
            "item_name": item.item_name,
            "item_group": item.item_group,
            "uom": item.stock_uom,
            "usable_stock": usable,
            "min_stock_qty": min_qty,
            "stock_status": status,
            "unit_cost": unit_cost,
            "stock_value": stock_value,
            "active_batches": active_batches,
            "expiring_soon": expiring,
            "expired_batches": expired,
        })

    return data


def get_chart(data):
    if not data:
        return None
    top = sorted(data, key=lambda x: x["usable_stock"])[:10]
    return {
        "data": {
            "labels": [d["item_name"] for d in top],
            "datasets": [
                {"name": _("Usable Stock"), "values": [flt(d["usable_stock"]) for d in top]},
                {"name": _("Min Stock"), "values": [flt(d["min_stock_qty"]) for d in top]},
            ],
        },
        "type": "bar",
        "title": _("Stock vs Minimum — Bottom 10"),
        "colors": ["#3498db", "#e74c3c"],
    }


def get_summary(data):
    total_value = sum(flt(d["stock_value"]) for d in data)
    low_count = sum(1 for d in data if "Low" in d["stock_status"] or "Out" in d["stock_status"])
    expiry_count = sum(flt(d["expiring_soon"]) for d in data)
    return [
        {"label": _("Total Items"), "value": len(data), "datatype": "Int", "indicator": "blue"},
        {"label": _("Low / Out of Stock"), "value": low_count, "datatype": "Int", "indicator": "red" if low_count else "green"},
        {"label": _("Expiring ≤7 Days"), "value": int(expiry_count), "datatype": "Int", "indicator": "orange" if expiry_count else "green"},
        {"label": _("Total Stock Value"), "value": total_value, "datatype": "Currency", "indicator": "blue"},
    ]
