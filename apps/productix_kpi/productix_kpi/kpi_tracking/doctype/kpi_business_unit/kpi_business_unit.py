import frappe
from frappe.model.document import Document
import re

class KPIBusinessUnit(Document):
    def validate(self):
        self.unit_code = self.unit_code.upper().strip().replace(" ", "_")
        if not re.match(r'^[A-Z][A-Z0-9_-]*$', self.unit_code):
            frappe.throw("Unit Code must start with a letter and contain only uppercase letters, numbers, underscores, and hyphens")
