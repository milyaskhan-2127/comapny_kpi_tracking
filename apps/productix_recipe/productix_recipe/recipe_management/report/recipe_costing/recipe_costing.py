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
        {"label": _("Recipe"), "fieldname": "recipe_name", "fieldtype": "Link", "options": "Recipe", "width": 200},
        {"label": _("Category"), "fieldname": "category", "fieldtype": "Data", "width": 120},
        {"label": _("Serving Size"), "fieldname": "serving_size", "fieldtype": "Float", "width": 100},
        {"label": _("Unit"), "fieldname": "unit", "fieldtype": "Data", "width": 80},
        {"label": _("BOM Cost"), "fieldname": "bom_cost", "fieldtype": "Currency", "width": 130},
        {"label": _("Cost Per Serving"), "fieldname": "cost_per_serving", "fieldtype": "Currency", "width": 140},
        {"label": _("Ingredients Count"), "fieldname": "ingredient_count", "fieldtype": "Int", "width": 130},
    ]


def get_data(filters):
    conditions = ""
    if filters and filters.get("category"):
        conditions += " AND r.category = %(category)s"

    data = frappe.db.sql(f"""
        SELECT
            r.name AS recipe_name,
            r.category,
            r.serving_size,
            r.unit,
            r.bom_cost,
            CASE WHEN r.serving_size > 0 THEN r.bom_cost / r.serving_size ELSE 0 END AS cost_per_serving,
            COUNT(ri.name) AS ingredient_count
        FROM `tabRecipe` r
        LEFT JOIN `tabRecipe Item` ri ON ri.parent = r.name
        WHERE r.docstatus < 2
        {conditions}
        GROUP BY r.name
        ORDER BY r.bom_cost DESC
    """, filters or {}, as_dict=True)

    return data


def get_chart(data):
    if not data:
        return None

    top = data[:10]
    return {
        "data": {
            "labels": [d["recipe_name"] for d in top],
            "datasets": [
                {"name": _("BOM Cost"), "values": [flt(d["bom_cost"]) for d in top]},
                {"name": _("Cost/Serving"), "values": [flt(d["cost_per_serving"]) for d in top]},
            ],
        },
        "type": "bar",
        "title": _("Recipe Costing — Top 10"),
        "colors": ["#e74c3c", "#3498db"],
    }


def get_summary(data):
    if not data:
        return []
    costs = [flt(d["bom_cost"]) for d in data]
    serving_costs = [flt(d["cost_per_serving"]) for d in data]
    highest = max(data, key=lambda x: x["bom_cost"]) if data else {}
    return [
        {"label": _("Total Recipes"), "value": len(data), "datatype": "Int", "indicator": "blue"},
        {"label": _("Avg BOM Cost"), "value": sum(costs) / len(costs) if costs else 0, "datatype": "Currency", "indicator": "green"},
        {"label": _("Avg Cost/Serving"), "value": sum(serving_costs) / len(serving_costs) if serving_costs else 0, "datatype": "Currency", "indicator": "green"},
        {"label": _("Highest Cost Recipe"), "value": highest.get("recipe_name", "—"), "datatype": "Data", "indicator": "orange"},
    ]
