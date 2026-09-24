import frappe
from frappe.model.document import Document

class KPISettings(Document):
    def validate(self):
        if self.min_prediction_data_points and self.min_prediction_data_points < 2:
            frappe.throw("Minimum data points for prediction must be at least 2")
        if self.alert_cooldown_hours and self.alert_cooldown_hours < 0:
            frappe.throw("Alert cooldown hours cannot be negative")
        if self.repeated_decline_periods and self.repeated_decline_periods < 2:
            frappe.throw("Consecutive decline periods must be at least 2")
