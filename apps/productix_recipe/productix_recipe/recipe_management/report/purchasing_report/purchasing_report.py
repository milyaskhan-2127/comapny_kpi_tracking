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
        {"label": _("GRN Number"), "fieldname": "name", "fieldtype": "Link", "options": "Purchase Receipt", "width": 160},
        {"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 110},
        {"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 180},
        {"label": _("Ingredient"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
        {"label": _("Ingredient Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 180},
        {"label": _("Batch Number"), "fieldname": "batch_no", "fieldtype": "Link", "options": "Batch", "width": 150},
        {"label": _("Expiry Date"), "fieldname": "expiry_date", "fieldtype": "Date", "width": 120},
        {"label": _("Certificate"), "fieldname": "certificate_html", "fieldtype": "Data", "width": 130},
        {"label": _("Qty Received"), "fieldname": "qty", "fieldtype": "Float", "width": 110},
        {"label": _("UOM"), "fieldname": "uom", "fieldtype": "Data", "width": 80},
        {"label": _("Purchase Rate"), "fieldname": "rate", "fieldtype": "Currency", "width": 110},
        {"label": _("Total Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 130},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 110},
    ]


def get_data(filters):
    conditions = "WHERE 1=1"
    if filters:
        if filters.get("from_date"):
            conditions += " AND pr.posting_date >= %(from_date)s"
        if filters.get("to_date"):
            conditions += " AND pr.posting_date <= %(to_date)s"
        if filters.get("supplier"):
            conditions += " AND pr.supplier = %(supplier)s"
        if filters.get("item_code"):
            conditions += " AND pri.item_code = %(item_code)s"
        if filters.get("batch_no"):
            conditions += " AND pri.batch_no = %(batch_no)s"

    rows = frappe.db.sql(f"""
        SELECT
            pr.name,
            pr.posting_date,
            pr.supplier,
            pri.item_code,
            pri.item_name,
            pri.batch_no,
            COALESCE(pri.expiry_date, b.expiry_date) AS expiry_date,
            COALESCE(pri.certificate_file, pr.shipment_certificate, b.certificate_file, b.certificate_url) AS certificate_file,
            pri.qty,
            pri.uom,
            pri.rate,
            pri.amount,
            pr.status
        FROM `tabPurchase Receipt` pr
        JOIN `tabPurchase Receipt Item` pri ON pri.parent = pr.name
        LEFT JOIN `tabBatch` b ON b.name = pri.batch_no
        {conditions}
        ORDER BY pr.posting_date DESC, pr.creation DESC
    """, filters or {}, as_dict=True)

    for r in rows:
        cert_file = r.get("certificate_file")
        if cert_file:
            r["certificate_html"] = f'<a href="{cert_file}" target="_blank" class="badge" style="background:#dbeafe;color:#1e40af;padding:3px 8px;border-radius:4px;text-decoration:none;font-weight:600;">📄 View COA</a>'
        else:
            r["certificate_html"] = '<span style="color:#94a3b8;">—</span>'

    return rows


def get_chart(data):
    if not data:
        return None
    from collections import defaultdict
    supplier_spend = defaultdict(float)
    for d in data:
        supplier_spend[d["supplier"] or "Unknown"] += flt(d["amount"])
    top = sorted(supplier_spend.items(), key=lambda x: -x[1])[:8]
    return {
        "data": {
            "labels": [s[0] for s in top],
            "datasets": [{"name": _("Total Spend"), "values": [s[1] for s in top]}],
        },
        "type": "bar",
        "title": _("Purchase Spend by Supplier"),
        "colors": ["#3498db"],
    }


def get_summary(data):
    total_spend = sum(flt(d["amount"]) for d in data)
    suppliers = len(set(d["supplier"] for d in data if d["supplier"]))
    grns = len(set(d["name"] for d in data if d["name"]))
    batches = len(set(d["batch_no"] for d in data if d["batch_no"]))
    return [
        {"label": _("GRN Receipts"), "value": grns, "datatype": "Int", "indicator": "blue"},
        {"label": _("Batches Received"), "value": batches, "datatype": "Int", "indicator": "blue"},
        {"label": _("Suppliers"), "value": suppliers, "datatype": "Int", "indicator": "blue"},
        {"label": _("Total Inbound Value"), "value": total_spend, "datatype": "Currency", "indicator": "green"},
    ]
