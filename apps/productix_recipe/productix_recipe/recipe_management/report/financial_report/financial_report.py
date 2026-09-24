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
        {"label": _("Cost/Serving"), "fieldname": "cost_per_serving", "fieldtype": "Currency", "width": 130},
        {"label": _("Production Orders"), "fieldname": "order_count", "fieldtype": "Int", "width": 140},
        {"label": _("Completed Orders"), "fieldname": "completed_count", "fieldtype": "Int", "width": 140},
        {"label": _("Total Revenue"), "fieldname": "total_revenue", "fieldtype": "Currency", "width": 140},
    ]


def get_data(filters):
    conditions = "WHERE r.docstatus < 2"
    if filters and filters.get("category"):
        conditions += " AND r.category = %(category)s"

    rows = frappe.db.sql(f"""
        SELECT
            r.name AS recipe_name,
            r.category,
            r.serving_size,
            r.unit,
            r.bom_cost,
            CASE WHEN r.serving_size > 0 THEN r.bom_cost / r.serving_size ELSE 0 END AS cost_per_serving,
            COUNT(po.name) AS order_count,
            SUM(CASE WHEN po.status = 'Completed' THEN 1 ELSE 0 END) AS completed_count,
            SUM(CASE WHEN po.status = 'Completed' THEN po.total_cost ELSE 0 END) AS total_revenue
        FROM `tabRecipe` r
        LEFT JOIN `tabProduction Order` po ON po.recipe = r.name
        {conditions}
        GROUP BY r.name
        ORDER BY r.bom_cost DESC
    """, filters or {}, as_dict=True)

    return rows


def get_chart(data):
    if not data:
        return None
    top = data[:8]
    return {
        "data": {
            "labels": [d["recipe_name"] for d in top],
            "datasets": [
                {"name": _("BOM Cost"), "values": [flt(d["bom_cost"]) for d in top]},
                {"name": _("Cost/Serving"), "values": [flt(d["cost_per_serving"]) for d in top]},
            ],
        },
        "type": "bar",
        "title": _("Recipe Cost Analysis"),
        "colors": ["#e74c3c", "#3498db"],
    }


def get_summary(data):
    if not data:
        return []
    costs = [flt(d["bom_cost"]) for d in data if d["bom_cost"]]
    servings = [flt(d["cost_per_serving"]) for d in data if d["cost_per_serving"]]
    total_rev = sum(flt(d["total_revenue"]) for d in data)
    highest = max(data, key=lambda x: flt(x["bom_cost"]), default={})
    return [
        {"label": _("Recipes"), "value": len(data), "datatype": "Int", "indicator": "blue"},
        {"label": _("Avg BOM Cost"), "value": sum(costs)/len(costs) if costs else 0, "datatype": "Currency", "indicator": "green"},
        {"label": _("Avg Cost/Serving"), "value": sum(servings)/len(servings) if servings else 0, "datatype": "Currency", "indicator": "green"},
        {"label": _("Total Production Revenue"), "value": total_rev, "datatype": "Currency", "indicator": "blue"},
    ]
