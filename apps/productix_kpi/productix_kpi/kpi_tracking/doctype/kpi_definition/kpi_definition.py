import frappe
from frappe.model.document import Document
import re


class KPIDefinition(Document):
    def validate(self):
        user = frappe.session.user
        if not (user == "Administrator" or self.flags.ignore_permissions or frappe.flags.in_test):
            roles = frappe.get_roles(user)
            if "System Manager" not in roles and "KPI Admin" not in roles:
                frappe.throw(
                    "Access denied: Only KPI Administrators can create or modify KPI Definitions.",
                    frappe.PermissionError
                )

        self.kpi_code = self.kpi_code.upper().strip().replace(" ", "-")
        if not re.match(r'^[A-Z][A-Z0-9_-]*$', self.kpi_code):
            frappe.throw("KPI Code must start with a letter and contain only uppercase letters, numbers, hyphens, and underscores")
        if self.target_value and self.minimum_acceptable:
            if self.direction == "Higher is Better" and self.minimum_acceptable > self.target_value:
                frappe.throw("Minimum acceptable value cannot exceed target for 'Higher is Better' KPIs")
        if self.direction == "Lower is Better":
            if (self.warning_threshold == 80 and self.critical_threshold == 60) or not self.warning_threshold:
                self.warning_threshold = 110.0
                self.critical_threshold = 130.0

        if self.warning_threshold and self.critical_threshold:
            if self.direction == "Higher is Better" and self.warning_threshold <= self.critical_threshold:
                frappe.throw("Warning threshold must be greater than critical threshold for 'Higher is Better' KPIs")
            elif self.direction == "Lower is Better" and self.warning_threshold >= self.critical_threshold:
                frappe.throw("Warning threshold must be less than critical threshold for 'Lower is Better' KPIs")

    def on_trash(self):
        user = frappe.session.user
        if not (user == "Administrator" or self.flags.ignore_permissions or frappe.flags.in_test):
            roles = frappe.get_roles(user)
            if "System Manager" not in roles and "KPI Admin" not in roles:
                frappe.throw(
                    "Access denied: Only KPI Administrators can delete KPI Definitions.",
                    frappe.PermissionError
                )

    @frappe.whitelist()
    def get_latest_value(self):
        entry = frappe.db.get_value(
            "KPI Data Entry",
            {"kpi": self.name, "docstatus": 1},
            ["actual_value", "achievement_percentage", "status", "entry_date", "period"],
            order_by="entry_date desc",
            as_dict=True
        )
        return entry

    @frappe.whitelist()
    def get_historical_data(self, periods=12):
        entries = frappe.db.get_all(
            "KPI Data Entry",
            filters={"kpi": self.name, "docstatus": 1},
            fields=["actual_value", "target_value", "achievement_percentage", "status", "entry_date", "period"],
            order_by="entry_date desc",
            limit_page_length=periods
        )
        return entries
