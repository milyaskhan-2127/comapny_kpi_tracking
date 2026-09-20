import frappe
from frappe.model.document import Document


class ProductixTenant(Document):

    def get_license(self):
        if self.license:
            return frappe.get_cached_doc("Productix License", self.license)
        return None

    def is_subscription_valid(self):
        lic = self.get_license()
        return lic.is_valid() if lic else False
