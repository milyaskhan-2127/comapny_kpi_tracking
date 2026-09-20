import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": _("Production Order"), "fieldname": "production_order", "fieldtype": "Link", "options": "Production Order", "width": 160},
        {"label": _("Order Number"), "fieldname": "order_number", "fieldtype": "Data", "width": 150},
        {"label": _("Ingredient"), "fieldname": "ingredient", "fieldtype": "Link", "options": "Item", "width": 160},
        {"label": _("Batch"), "fieldname": "batch", "fieldtype": "Link", "options": "Batch", "width": 140},
        {"label": _("Planned Qty"), "fieldname": "planned_quantity", "fieldtype": "Float", "width": 120},
        {"label": _("Actual Qty"), "fieldname": "actual_quantity", "fieldtype": "Float", "width": 120},
        {"label": _("Variance"), "fieldname": "difference", "fieldtype": "Float", "width": 100},
        {"label": _("Unit"), "fieldname": "unit", "fieldtype": "Data", "width": 80},
        {"label": _("Consumed At"), "fieldname": "consumed_at", "fieldtype": "Datetime", "width": 150},
    ]


def get_data(filters):
    conditions = ""
    if filters and filters.get("production_order"):
        conditions += " AND cl.production_order = %(production_order)s"
    if filters and filters.get("from_date"):
        conditions += " AND DATE(cl.consumed_at) >= %(from_date)s"
    if filters and filters.get("to_date"):
        conditions += " AND DATE(cl.consumed_at) <= %(to_date)s"

    return frappe.db.sql(f"""
        SELECT
            cl.production_order,
            cl.order_number,
            cl.ingredient,
            cl.batch,
            cl.planned_quantity,
            cl.actual_quantity,
            cl.difference,
            cl.unit,
            cl.consumed_at
        FROM `tabConsumption Log` cl
        WHERE 1=1 {conditions}
        ORDER BY cl.consumed_at DESC
    """, filters or {}, as_dict=True)
