import frappe
from frappe.model.document import Document
from frappe.utils import getdate
from productix_kpi.kpi_tracking.services.period_engine import (
    get_current_period,
    calculate_raw_achievement_percentage,
    calculate_normalized_score,
    get_status_from_score,
)


class KPIDataEntry(Document):
    def validate(self):
        if not self.entered_by:
            self.entered_by = frappe.session.user
        self._check_department_access()
        self._set_period()
        self._fetch_target()
        self._calculate_achievement()
        self._set_status()
        self._check_duplicate()

    def on_submit(self):
        frappe.enqueue(
            "productix_kpi.kpi_tracking.services.analytics.run_post_entry_analytics",
            kpi_data_entry=self.name,
            queue="long"
        )

    def _set_period(self):
        if self.period:
            return
        kpi_doc = frappe.get_cached_doc("KPI Definition", self.kpi)
        d = getdate(self.entry_date)
        company_freq = frappe.db.get_single_value("KPI Settings", "default_frequency") or "Daily"
        freq = kpi_doc.frequency or company_freq
        self.period = get_current_period(freq, d)

    def _fetch_target(self):
        kpi_doc = frappe.get_cached_doc("KPI Definition", self.kpi)
        if kpi_doc.target_value is not None:
            self.target_value = float(kpi_doc.target_value)
        else:
            self.target_value = 0.0

    def _calculate_achievement(self):
        if not self.kpi:
            return
        kpi_doc = frappe.get_cached_doc("KPI Definition", self.kpi)
        direction = kpi_doc.direction or "Higher is Better"
        target_type = kpi_doc.target_type or "Fixed Target"
        target = float(self.target_value or 0.0)
        actual = float(self.actual_value if self.actual_value is not None else 0.0)

        raw_ach = calculate_raw_achievement_percentage(
            actual=actual,
            target=target,
            direction=direction,
            target_type=target_type,
            minimum_acceptable=kpi_doc.minimum_acceptable,
        )
        norm_score = calculate_normalized_score(
            actual=actual,
            target=target,
            direction=direction,
            target_type=target_type,
            minimum_acceptable=kpi_doc.minimum_acceptable,
        )
        self.achievement_percentage = raw_ach if raw_ach is not None else 0.0
        self.normalized_score = norm_score if norm_score is not None else 0.0

    def _set_status(self):
        kpi_doc = frappe.get_cached_doc("KPI Definition", self.kpi)
        score_for_status = self.normalized_score if self.normalized_score is not None else self.achievement_percentage
        self.status = get_status_from_score(
            score=score_for_status,
            warning_threshold=kpi_doc.warning_threshold,
            critical_threshold=kpi_doc.critical_threshold,
        )

    def _check_duplicate(self):
        filters = {
            "kpi": self.kpi,
            "department": self.department,
            "period": self.period,
            "docstatus": ["<", 2],
            "name": ["!=", self.name or ""]
        }
        if self.customer:
            filters["customer"] = self.customer
        existing = frappe.db.exists("KPI Data Entry", filters)
        if existing:
            frappe.throw(f"A KPI entry already exists for {self.kpi} in period {self.period}")

    def _check_department_access(self):
        from productix_kpi.kpi_tracking.security.permissions import is_kpi_admin, get_user_authorized_department

        user = frappe.session.user
        if is_kpi_admin(user):
            return

        user_dept = get_user_authorized_department(user)
        has_assignment = frappe.db.get_value(
            "KPI User Assignment",
            {"user": user, "department": self.department, "is_active": 1},
            "name"
        )
        if not has_assignment and user_dept != self.department:
            frappe.throw(
                f"Access denied: You are not authorized to submit data for department '{self.department}'.",
                frappe.PermissionError
            )
