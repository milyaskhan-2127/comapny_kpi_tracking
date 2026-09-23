import frappe
from frappe.model.document import Document
from frappe.utils import today


class MachineReading(Document):
    def validate(self):
        self.entered_by = self.entered_by or frappe.session.user
        if not self.period:
            from productix.kpi_tracking.services.period_engine import get_current_period
            self.period = get_current_period("Daily", self.reading_date)
        self._calculate_health()

    def on_submit(self):
        self._update_machine_health()

    def on_cancel(self):
        self._recalculate_machine_health()

    def _calculate_health(self):
        from productix.kpi_tracking.services.machine_health import calculate_reading_health
        result = calculate_reading_health(self)
        self.health_score = result["health_score"]
        self.health_status = result["health_status"]
        self.data_quality = result["data_quality"]

    def _update_machine_health(self):
        from productix.kpi_tracking.services.machine_health import update_machine_health
        update_machine_health(self.machine)

    def _recalculate_machine_health(self):
        from productix.kpi_tracking.services.machine_health import update_machine_health
        update_machine_health(self.machine)
