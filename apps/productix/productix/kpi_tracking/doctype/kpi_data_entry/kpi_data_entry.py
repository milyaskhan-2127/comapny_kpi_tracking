import frappe
from frappe.model.document import Document
from frappe.utils import getdate


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
            "productix.kpi_tracking.services.analytics.run_post_entry_analytics",
            kpi_data_entry=self.name,
            queue="long"
        )

    def _set_period(self):
        kpi_doc = frappe.get_cached_doc("KPI Definition", self.kpi)
        d = getdate(self.entry_date)
        company_freq = frappe.db.get_single_value("KPI Settings", "default_frequency") or "Daily"
        freq = kpi_doc.frequency or company_freq
        if freq == "Daily":
            self.period = d.strftime("%Y-%m-%d")
        elif freq == "Weekly":
            iso = d.isocalendar()
            self.period = f"{iso[0]}-W{iso[1]:02d}"
        elif freq == "Monthly":
            self.period = d.strftime("%Y-%m")
        elif freq == "Quarterly":
            q = (d.month - 1) // 3 + 1
            self.period = f"{d.year}-Q{q}"
        elif freq == "Yearly":
            self.period = str(d.year)
        else:
            self.period = d.strftime("%Y-%m-%d") if freq == "Daily" else d.strftime("%Y-%m")

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

        if target_type == "No Target":
            self.achievement_percentage = 100.0
            return

        if direction == "Lower is Better":
            if actual <= 0:
                self.achievement_percentage = 100.0
            elif target <= 0:
                # Target is 0 (e.g. zero accidents). Each unit over 0 reduces achievement
                self.achievement_percentage = round(max(0.0, min(100.0, 100.0 - (actual * 25.0))), 2)
            else:
                if actual <= target:
                    self.achievement_percentage = 100.0
                else:
                    self.achievement_percentage = round(max(0.0, min(100.0, (target / actual) * 100.0)), 2)

        elif direction == "Target Range":
            min_val = float(kpi_doc.minimum_acceptable if kpi_doc.minimum_acceptable is not None else 0.0)
            max_val = float(target if target != 0 else min_val)
            if min_val <= actual <= max_val:
                self.achievement_percentage = 100.0
            elif actual < min_val:
                self.achievement_percentage = round(max(0.0, min(100.0, (actual / min_val * 100.0) if min_val != 0 else 0.0)), 2)
            else:
                self.achievement_percentage = round(max(0.0, min(100.0, (max_val / actual * 100.0) if actual != 0 else 0.0)), 2)

        elif direction == "Exact Target":
            if target == 0:
                self.achievement_percentage = 100.0 if actual == 0 else 0.0
            else:
                variance = abs(actual - target)
                variance_pct = (variance / abs(target)) * 100.0
                self.achievement_percentage = round(max(0.0, min(100.0, 100.0 - variance_pct)), 2)

        else:  # Higher is Better
            if target <= 0:
                self.achievement_percentage = 100.0 if actual >= 0 else 0.0
            else:
                self.achievement_percentage = round(max(0.0, min(100.0, (actual / target) * 100.0)), 2)

        # Ensure strictly bounded to [0.0, 100.0]
        self.achievement_percentage = round(max(0.0, min(100.0, float(self.achievement_percentage or 0.0))), 2)

    def _set_status(self):
        kpi_doc = frappe.get_cached_doc("KPI Definition", self.kpi)
        warn = float(kpi_doc.warning_threshold if kpi_doc.warning_threshold is not None else 80.0)
        crit = float(kpi_doc.critical_threshold if kpi_doc.critical_threshold is not None else 60.0)
        ach = float(self.achievement_percentage if self.achievement_percentage is not None else 0.0)

        if ach >= warn:
            self.status = "On Track"
        elif ach >= crit:
            self.status = "Warning"
        else:
            self.status = "Critical"

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
        from productix.kpi_tracking.security.permissions import is_kpi_admin, get_user_authorized_department

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
