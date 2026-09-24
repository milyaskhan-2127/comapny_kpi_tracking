import frappe
from frappe.model.document import Document
from frappe.utils import getdate, today, date_diff


class Machine(Document):
    def validate(self):
        self._update_maintenance_days()

    def _update_maintenance_days(self):
        if self.last_maintenance_date:
            self.days_since_maintenance = date_diff(today(), self.last_maintenance_date)
        else:
            if self.installation_date:
                self.days_since_maintenance = date_diff(today(), self.installation_date)
            else:
                self.days_since_maintenance = 0
