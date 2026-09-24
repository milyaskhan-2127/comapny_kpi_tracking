import frappe
from frappe import _
from frappe.utils import flt, getdate, today


def execute(filters=None):
    if not filters or not filters.get("production_order"):
        return get_columns(), []

    columns = get_columns()
    data = get_data(filters)
    summary = get_summary(data)
    return columns, data, None, None, summary


def get_columns():
    return [
        {"label": _("Ingredient"), "fieldname": "ingredient", "fieldtype": "Link", "options": "Item", "width": 180},
        {"label": _("Ingredient Name"), "fieldname": "ingredient_name", "fieldtype": "Data", "width": 200},
        {"label": _("Required Qty"), "fieldname": "required_qty", "fieldtype": "Float", "width": 130},
        {"label": _("UOM"), "fieldname": "uom", "fieldtype": "Data", "width": 80},
        {"label": _("Usable Stock"), "fieldname": "usable_stock", "fieldtype": "Float", "width": 130},
        {"label": _("Shortage"), "fieldname": "shortage", "fieldtype": "Float", "width": 120},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 130},
        {"label": _("Base Qty"), "fieldname": "base_qty", "fieldtype": "Float", "width": 110},
        {"label": _("Extras Qty"), "fieldname": "extras_qty", "fieldtype": "Float", "width": 110},
    ]


def get_data(filters):
    po_name = filters.get("production_order")
    order = frappe.get_doc("Production Order", po_name)
    recipe = frappe.get_doc("Recipe", order.recipe)
    multiplier = order.quantity or 1
    today_date = getdate(today())

    ingredient_map = {}

    # BOM items
    for item in recipe.items:
        ing = item.ingredient
        if ing not in ingredient_map:
            ingredient_map[ing] = {"base_qty": 0, "extras_qty": 0, "ingredient": ing}
        ingredient_map[ing]["base_qty"] += (item.quantity or 0) * multiplier

    # Extras
    for extra in order.order_extras:
        if extra.ingredient:
            ing = extra.ingredient
            if ing not in ingredient_map:
                ingredient_map[ing] = {"base_qty": 0, "extras_qty": 0, "ingredient": ing}
            ingredient_map[ing]["extras_qty"] += (extra.quantity or 0) * multiplier

    data = []
    for ing, vals in ingredient_map.items():
        required = vals["base_qty"] + vals["extras_qty"]

        # Usable stock (non-expired)
        usable = frappe.db.sql("""
            SELECT IFNULL(SUM(sle.actual_qty), 0)
            FROM `tabStock Ledger Entry` sle
            JOIN `tabBatch` b ON b.name = sle.batch_no
            WHERE sle.item_code = %s
              AND sle.is_cancelled = 0
              AND (b.expiry_date IS NULL OR b.expiry_date > %s)
              AND b.disabled = 0
        """, (ing, str(today_date)))[0][0] or 0.0

        shortage = max(0, required - usable)
        item_doc = frappe.get_cached_doc("Item", ing)

        if shortage > 0:
            status = f"🔴 SHORT by {shortage:.2f}"
        else:
            status = "🟢 Available"

        data.append({
            "ingredient": ing,
            "ingredient_name": item_doc.item_name,
            "required_qty": required,
            "uom": item_doc.stock_uom,
            "usable_stock": usable,
            "shortage": shortage,
            "status": status,
            "base_qty": vals["base_qty"],
            "extras_qty": vals["extras_qty"],
        })

    return data


def get_summary(data):
    shortages = sum(1 for d in data if d["shortage"] > 0)
    return [
        {"label": _("Total Ingredients"), "value": len(data), "datatype": "Int", "indicator": "blue"},
        {"label": _("Shortages"), "value": shortages, "datatype": "Int", "indicator": "red" if shortages else "green"},
        {"label": _("Ready to Produce"), "value": "Yes" if shortages == 0 else "No", "datatype": "Data", "indicator": "green" if shortages == 0 else "red"},
    ]
