import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

class KPIPrediction(Document):
    @frappe.whitelist()
    def update_actual(self, actual_value):
        self.actual_value = float(actual_value)
        self.variance = self.actual_value - self.predicted_value
        if self.predicted_value and self.predicted_value != 0:
            self.variance_percentage = (self.variance / self.predicted_value) * 100
            self.accuracy = max(0, 100 - abs(self.variance_percentage))
        else:
            self.variance_percentage = 0
            self.accuracy = 0
        kpi_doc = frappe.get_cached_doc("KPI Definition", self.kpi)
        threshold = frappe.db.get_single_value("KPI Settings", "prediction_confidence_threshold") or 80
        if self.accuracy >= threshold:
            self.status = "Matched"
        else:
            self.status = "Prediction Miss"
        self.save(ignore_permissions=True)
        return {"status": self.status, "variance": self.variance, "accuracy": self.accuracy}
