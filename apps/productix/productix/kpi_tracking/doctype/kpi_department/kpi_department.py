import frappe
from frappe.model.document import Document
import re

class KPIDepartment(Document):
    def validate(self):
        self.department_code = self.department_code.upper().strip().replace(" ", "_")
        if not re.match(r'^[A-Z][A-Z0-9_]*$', self.department_code):
            frappe.throw("Department Code must start with a letter and contain only uppercase letters, numbers, and underscores")
        if self.weight and self.weight < 0:
            frappe.throw("Weight cannot be negative")
