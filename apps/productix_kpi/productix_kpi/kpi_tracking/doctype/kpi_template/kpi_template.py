import frappe
from frappe.model.document import Document
import re

class KPITemplate(Document):
    @frappe.whitelist()
    def apply_template(self, department, selected_items=None):
        if not department:
            frappe.throw("Department is required to apply template")

        dept_name = department
        if not frappe.db.exists("KPI Department", dept_name):
            dept_name = frappe.db.get_value("KPI Department", {"department_code": department}, "name")
            if not dept_name:
                dept_name = frappe.db.get_value("KPI Department", {"department_name": department}, "name")

        if not dept_name or not frappe.db.exists("KPI Department", dept_name):
            frappe.throw(f"Department '{department}' does not exist.")

        dept_doc = frappe.get_doc("KPI Department", dept_name)
        if not dept_doc.is_active:
            frappe.throw(f"Department '{dept_doc.department_name or department}' is not active. Please activate it first.")

        company_freq = frappe.db.get_single_value("KPI Settings", "default_frequency") or "Daily"
        created = []
        dept_code = dept_doc.department_code or dept_doc.name
        for item in self.items:
            if selected_items and item.kpi_name not in selected_items:
                continue
            clean_name = re.sub(r'[^A-Za-z0-9]+', '-', item.kpi_name).upper().strip('-')
            kpi_code = f"{dept_code}-{clean_name}"
            item_freq = item.default_frequency or company_freq
            direction = item.direction or "Higher is Better"
            warn_th = 110.0 if direction == "Lower is Better" else 80.0
            crit_th = 130.0 if direction == "Lower is Better" else 60.0

            if frappe.db.exists("KPI Definition", kpi_code):
                frappe.db.set_value("KPI Definition", kpi_code, {
                    "frequency": item_freq,
                    "is_active": 1,
                    "department": dept_doc.name
                })
                created.append(kpi_code)
                continue
            kpi = frappe.get_doc({
                "doctype": "KPI Definition",
                "kpi_name": item.kpi_name,
                "kpi_code": kpi_code,
                "department": dept_doc.name,
                "measurement_type": item.measurement_type,
                "direction": direction,
                "target_type": "Fixed Target" if item.default_target else "No Target",
                "target_value": item.default_target,
                "warning_threshold": warn_th,
                "critical_threshold": crit_th,
                "frequency": item_freq,
                "description": item.description,
                "is_active": 1,
                "prediction_enabled": 1,
                "alert_enabled": 1,
            })
            kpi.insert(ignore_permissions=True)
            created.append(kpi.name)
        return created
