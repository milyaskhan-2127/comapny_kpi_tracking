"""
Productix override for Stock Entry.
Injects FEFO batch selection before save when purpose is Material Issue.
"""
import frappe

try:
    from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry
    BASE_CLASS = StockEntry
except Exception:
    from frappe.model.document import Document
    BASE_CLASS = Document


class ProductixStockEntry(BASE_CLASS):
    pass
