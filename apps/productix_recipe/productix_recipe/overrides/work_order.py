"""
Productix override for Work Order.
Minimal — most production logic lives in the custom Production Order DocType.
"""
import frappe

try:
    from erpnext.manufacturing.doctype.work_order.work_order import WorkOrder
    BASE_CLASS = WorkOrder
except Exception:
    from frappe.model.document import Document
    BASE_CLASS = Document


class ProductixWorkOrder(BASE_CLASS):
    pass
