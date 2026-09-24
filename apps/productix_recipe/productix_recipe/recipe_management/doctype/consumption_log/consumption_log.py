import frappe
from frappe.model.document import Document
from frappe.utils import flt


class ConsumptionLog(Document):

    def before_save(self):
        self.difference = flt(self.planned_quantity) - flt(self.actual_quantity)
