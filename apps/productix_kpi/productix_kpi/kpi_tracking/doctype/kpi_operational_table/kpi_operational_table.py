import frappe
from frappe.model.document import Document
import re

class KPIOperationalTable(Document):
    def validate(self):
        self.table_code = self.table_code.upper().strip().replace(" ", "_")
        if not re.match(r'^[A-Z][A-Z0-9_-]*$', self.table_code):
            frappe.throw("Table Code must start with a letter and contain only uppercase letters, numbers, underscores, and hyphens")
        seen = set()
        for row in self.variables or []:
            if row.variable in seen:
                frappe.throw(f"Variable {row.variable} is added more than once")
            seen.add(row.variable)
