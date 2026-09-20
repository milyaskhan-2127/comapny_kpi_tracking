import frappe
from frappe import _
from frappe.utils import flt, getdate, today


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart(data)
    summary = get_summary(data)
    return columns, data, None, chart, summary


def get_columns():
    return [
        {"label": _("Batch"), "fieldname": "batch_no", "fieldtype": "Link", "options": "Batch", "width": 160},
        {"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
        {"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 180},
        {"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 160},
        {"label": _("Expiry Date"), "fieldname": "expiry_date", "fieldtype": "Date", "width": 120},
        {"label": _("Expired Qty"), "fieldname": "expired_qty", "fieldtype": "Float", "width": 120},
        {"label": _("Unit Cost"), "fieldname": "unit_cost", "fieldtype": "Currency", "width": 110},
        {"label": _("Financial Loss"), "fieldname": "loss_value", "fieldtype": "Currency", "width": 130},
        {"label": _("Status"), "fieldname": "batch_status", "fieldtype": "Data", "width": 120},
    ]


def get_data(filters):
    today_date = getdate(today())
    alert_window_str = str(today_date)

    # Get all batches that are expired
    batches = frappe.get_all("Batch",
        filters={"expiry_date": ["<", alert_window_str]},
        fields=["name", "item", "expiry_date", "batch_qty", "supplier", "disabled"])

    data = []
    for b in batches:
        if not b.item:
            continue
        item = frappe.get_cached_doc("Item", b.item)
        unit_cost = flt(item.valuation_rate)
        qty = flt(b.batch_qty)

        # Get actual remaining stock in warehouse for this batch
        actual_qty = frappe.db.sql("""
            SELECT IFNULL(SUM(actual_qty), 0)
            FROM `tabStock Ledger Entry`
            WHERE item_code = %s AND batch_no = %s AND is_cancelled = 0
        """, (b.item, b.name))[0][0] or 0.0

        if actual_qty <= 0 and not filters:
            # Only show batches with remaining stock (waste that could have been avoided)
            # Or show all expired for audit
            pass

        data.append({
            "batch_no": b.name,
            "item_code": b.item,
            "item_name": item.item_name,
            "supplier": b.supplier,
            "expiry_date": b.expiry_date,
            "expired_qty": actual_qty,
            "unit_cost": unit_cost,
            "loss_value": actual_qty * unit_cost,
            "batch_status": "🔴 Expired" if not b.disabled else "🔴 Expired (Disabled)",
        })

    return data


def get_chart(data):
    if not data:
        return None
    top = sorted(data, key=lambda x: -x["loss_value"])[:8]
    return {
        "data": {
            "labels": [d["item_name"] for d in top],
            "datasets": [{"name": _("Financial Loss"), "values": [flt(d["loss_value"]) for d in top]}],
        },
        "type": "bar",
        "title": _("Top Waste by Financial Loss"),
        "colors": ["#e74c3c"],
    }


def get_summary(data):
    total_loss = sum(flt(d["loss_value"]) for d in data)
    total_qty = sum(flt(d["expired_qty"]) for d in data)
    return [
        {"label": _("Expired Batches"), "value": len(data), "datatype": "Int", "indicator": "red" if data else "green"},
        {"label": _("Total Expired Qty"), "value": total_qty, "datatype": "Float", "indicator": "red" if total_qty else "green"},
        {"label": _("Total Financial Loss"), "value": total_loss, "datatype": "Currency", "indicator": "red" if total_loss else "green"},
    ]
