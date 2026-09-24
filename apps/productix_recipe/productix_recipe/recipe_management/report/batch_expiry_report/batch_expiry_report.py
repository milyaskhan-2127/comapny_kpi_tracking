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
        {"label": _("Batch"), "fieldname": "batch_no", "fieldtype": "Link", "options": "Batch", "width": 160},
        {"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
        {"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 180},
        {"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 160},
        {"label": _("Expiry Date"), "fieldname": "expiry_date", "fieldtype": "Date", "width": 120},
        {"label": _("Days Remaining"), "fieldname": "days_left", "fieldtype": "Int", "width": 130},
        {"label": _("Batch Status"), "fieldname": "batch_status", "fieldtype": "Data", "width": 130},
        {"label": _("Certificate"), "fieldname": "certificate_html", "fieldtype": "Data", "width": 130},
        {"label": _("Qty Remaining"), "fieldname": "batch_qty", "fieldtype": "Float", "width": 130},
        {"label": _("Unit Cost"), "fieldname": "unit_cost", "fieldtype": "Currency", "width": 110},
        {"label": _("Batch Value"), "fieldname": "batch_value", "fieldtype": "Currency", "width": 120},
    ]


def get_data(filters):
    today_date = getdate(today())
    show_filter = (filters or {}).get("show", "Expiring Soon")

    batches = frappe.get_all("Batch", filters={"disabled": 0},
        fields=["name", "item", "expiry_date", "batch_qty", "supplier", "certificate_file", "certificate_url", "has_expiry"])

    data = []
    for b in batches:
        if not b.expiry_date:
            if show_filter == "No Expiry":
                data.append(_build_row(b, today_date))
            continue

        exp_date = getdate(b.expiry_date)
        days_left = (exp_date - today_date).days

        if show_filter == "Expiring Soon" and not (0 <= days_left <= 7):
            continue
        if show_filter == "Expired" and days_left >= 0:
            continue
        if show_filter == "Healthy" and days_left <= 7:
            continue

        data.append(_build_row(b, today_date))

    data.sort(key=lambda x: (x.get("days_left") or 9999))
    return data


def _build_row(b, today_date):
    item = frappe.get_cached_doc("Item", b.item) if b.item else None
    unit_cost = flt(item.valuation_rate) if item else 0
    qty = flt(b.batch_qty)
    exp_date = getdate(b.expiry_date) if b.expiry_date else None
    days_left = (exp_date - today_date).days if exp_date else None
    cert_file = b.get("certificate_file") or b.get("certificate_url")

    if cert_file:
        cert_html = f'<a href="{cert_file}" target="_blank" class="badge" style="background:#dbeafe;color:#1e40af;padding:3px 8px;border-radius:4px;text-decoration:none;font-weight:600;">📄 View COA</a>'
    else:
        cert_html = '<span style="color:#94a3b8;">—</span>'

    if exp_date is None:
        status = "No Expiry"
    elif days_left < 0:
        status = "🔴 Expired"
    elif days_left <= 7:
        status = f"🟠 Expiring ({days_left}d)"
    else:
        status = "🟢 Healthy"

    return {
        "batch_no": b.name,
        "item_code": b.item,
        "item_name": item.item_name if item else "",
        "supplier": b.supplier,
        "expiry_date": b.expiry_date,
        "days_left": days_left,
        "batch_status": status,
        "certificate_html": cert_html,
        "certificate_file": cert_file,
        "batch_qty": qty,
        "unit_cost": unit_cost,
        "batch_value": qty * unit_cost,
    }


def get_chart(data):
    if not data:
        return None
    expired = sum(1 for d in data if "Expired" in str(d.get("batch_status", "")))
    expiring = sum(1 for d in data if "Expiring" in str(d.get("batch_status", "")))
    healthy = sum(1 for d in data if d.get("batch_status") == "🟢 Healthy")
    no_expiry = sum(1 for d in data if d.get("batch_status") == "No Expiry")
    return {
        "data": {
            "labels": [_("Expired"), _("Expiring Soon"), _("Healthy"), _("No Expiry")],
            "datasets": [{"values": [expired, expiring, healthy, no_expiry]}],
        },
        "type": "pie",
        "title": _("Batch Status Distribution"),
        "colors": ["#e74c3c", "#f39c12", "#27ae60", "#95a5a6"],
    }


def get_summary(data):
    expired = sum(1 for d in data if "Expired" in str(d.get("batch_status", "")))
    expiring = sum(1 for d in data if "Expiring" in str(d.get("batch_status", "")))
    waste_value = sum(flt(d["batch_value"]) for d in data if "Expired" in str(d.get("batch_status", "")))
    return [
        {"label": _("Total Batches Shown"), "value": len(data), "datatype": "Int", "indicator": "blue"},
        {"label": _("Expired"), "value": expired, "datatype": "Int", "indicator": "red" if expired else "green"},
        {"label": _("Expiring ≤7d"), "value": expiring, "datatype": "Int", "indicator": "orange" if expiring else "green"},
        {"label": _("Expired Waste Value"), "value": waste_value, "datatype": "Currency", "indicator": "red" if waste_value else "green"},
    ]
