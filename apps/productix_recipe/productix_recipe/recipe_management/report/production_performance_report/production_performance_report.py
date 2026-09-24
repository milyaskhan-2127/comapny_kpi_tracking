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
        {"label": _("Production Order"), "fieldname": "name", "fieldtype": "Link", "options": "Production Order", "width": 160},
        {"label": _("Recipe"), "fieldname": "recipe_name", "fieldtype": "Data", "width": 180},
        {"label": _("Quantity"), "fieldname": "quantity", "fieldtype": "Int", "width": 90},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 110},
        {"label": _("Production Date"), "fieldname": "production_date", "fieldtype": "Datetime", "width": 160},
        {"label": _("Base Cost"), "fieldname": "base_cost", "fieldtype": "Currency", "width": 120},
        {"label": _("Extras Cost"), "fieldname": "extras_cost", "fieldtype": "Currency", "width": 120},
        {"label": _("Total Cost"), "fieldname": "total_cost", "fieldtype": "Currency", "width": 120},
    ]


def get_data(filters):
    conditions = "WHERE po.docstatus < 2"
    if filters:
        if filters.get("from_date"):
            conditions += " AND DATE(po.production_date) >= %(from_date)s"
        if filters.get("to_date"):
            conditions += " AND DATE(po.production_date) <= %(to_date)s"
        if filters.get("status"):
            conditions += " AND po.status = %(status)s"

    return frappe.db.sql(f"""
        SELECT
            po.name,
            po.recipe_name,
            po.quantity,
            po.status,
            po.production_date,
            po.base_cost,
            po.extras_cost,
            po.total_cost
        FROM `tabProduction Order` po
        {conditions}
        ORDER BY po.production_date DESC
    """, filters or {}, as_dict=True)


def get_chart(data):
    if not data:
        return None
    from collections import Counter
    status_count = Counter(d["status"] for d in data)
    return {
        "data": {
            "labels": list(status_count.keys()),
            "datasets": [{"values": list(status_count.values())}],
        },
        "type": "donut",
        "title": _("Production Orders by Status"),
        "colors": ["#27ae60", "#3498db", "#f39c12", "#e74c3c"],
    }


def get_summary(data):
    total_value = sum(flt(d["total_cost"]) for d in data)
    completed = sum(1 for d in data if d["status"] == "Completed")
    in_progress = sum(1 for d in data if d["status"] == "In Progress")
    return [
        {"label": _("Total Orders"), "value": len(data), "datatype": "Int", "indicator": "blue"},
        {"label": _("Completed"), "value": completed, "datatype": "Int", "indicator": "green"},
        {"label": _("In Progress"), "value": in_progress, "datatype": "Int", "indicator": "blue"},
        {"label": _("Total Production Value"), "value": total_value, "datatype": "Currency", "indicator": "green"},
    ]
