import frappe
from frappe.model.document import Document


class MachineType(Document):
    def validate(self):
        seen_codes = set()
        for p in self.parameters:
            if p.parameter_code in seen_codes:
                frappe.throw(f"Duplicate parameter code '{p.parameter_code}' in parameters.")
            seen_codes.add(p.parameter_code)
