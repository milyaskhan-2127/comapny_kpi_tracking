from __future__ import unicode_literals
from frappe import _


def get_data():
    return [
        {
            "label": _("Recipe Management"),
            "items": [
                {
                    "type": "doctype",
                    "name": "Recipe",
                    "label": _("Recipes"),
                    "description": _("Manage recipes and bills of materials"),
                },
                {
                    "type": "doctype",
                    "name": "Production Order",
                    "label": _("Production Orders"),
                    "description": _("Create and track kitchen production orders"),
                },
                {
                    "type": "report",
                    "name": "Recipe Costing",
                    "label": _("Recipe Costing Report"),
                    "is_query_report": True,
                },
                {
                    "type": "report",
                    "name": "Consumption Report",
                    "label": _("Consumption Report"),
                    "is_query_report": True,
                },
            ],
        },
        {
            "label": _("Inventory"),
            "items": [
                {
                    "type": "doctype",
                    "name": "Item",
                    "label": _("Ingredients"),
                    "description": _("Manage ingredients / stock items"),
                },
                {
                    "type": "doctype",
                    "name": "Purchase Receipt",
                    "label": _("Goods Received Notes (GRN)"),
                    "description": _("Receive stock from suppliers"),
                },
                {
                    "type": "doctype",
                    "name": "Batch",
                    "label": _("Inventory Batches"),
                    "description": _("View individual batches with expiry dates"),
                },
                {
                    "type": "report",
                    "name": "Inventory Status Report",
                    "label": _("Inventory Status Report"),
                    "is_query_report": True,
                },
                {
                    "type": "report",
                    "name": "Batch Expiry Report",
                    "label": _("Batch Expiry Report"),
                    "is_query_report": True,
                },
                {
                    "type": "report",
                    "name": "Stock Movement Report",
                    "label": _("Stock Movement Report"),
                    "is_query_report": True,
                },
            ],
        },
        {
            "label": _("Suppliers"),
            "items": [
                {
                    "type": "doctype",
                    "name": "Supplier",
                    "label": _("Suppliers"),
                    "description": _("Manage suppliers"),
                },
                {
                    "type": "report",
                    "name": "Purchasing Report",
                    "label": _("Purchasing Report"),
                    "is_query_report": True,
                },
            ],
        },
        {
            "label": _("Reports"),
            "items": [
                {
                    "type": "report",
                    "name": "Financial Report",
                    "label": _("Financial Report"),
                    "is_query_report": True,
                },
                {
                    "type": "report",
                    "name": "Waste and Expiry Report",
                    "label": _("Waste & Expiry Report"),
                    "is_query_report": True,
                },
                {
                    "type": "report",
                    "name": "Production Performance Report",
                    "label": _("Production Performance Report"),
                    "is_query_report": True,
                },
            ],
        },
    ]
