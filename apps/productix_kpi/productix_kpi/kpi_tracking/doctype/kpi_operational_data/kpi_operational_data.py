import frappe
from frappe.model.document import Document
from frappe.utils import getdate

class KPIOperationalData(Document):
    def validate(self):
        self.entered_by = self.entered_by or frappe.session.user
        self._set_period()
        self._check_department_access()
        self._check_duplicate()

    def _set_period(self):
        d = getdate(self.entry_date)
        self.period = d.strftime("%Y-%m")

    def _check_department_access(self):
        if frappe.session.user == "Administrator":
            return
        user_roles = frappe.get_roles(frappe.session.user)
        if "System Manager" in user_roles or "KPI Admin" in user_roles:
            return
        assignment = frappe.db.get_value(
            "KPI User Assignment",
            {"user": frappe.session.user, "department": self.department, "is_active": 1},
            "name"
        )
        if not assignment:
            frappe.throw(f"You are not authorized to enter data for department {self.department}")

    def _check_duplicate(self):
        if self.is_new() or self.amended_from:
            filters = {
                "operational_table": self.operational_table,
                "period": self.period,
                "docstatus": ["<", 2],
                "name": ["!=", self.name or ""]
            }
            if self.customer:
                filters["customer"] = self.customer
            existing = frappe.db.exists("KPI Operational Data", filters)
            if existing:
                frappe.throw(f"Operational data already exists for {self.operational_table} in period {self.period}")
