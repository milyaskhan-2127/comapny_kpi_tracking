import frappe
from frappe.model.document import Document
import re

class KPITemplate(Document):
    @frappe.whitelist()
    def apply_template(self, department, selected_items=None):
        if not department:
            frappe.throw("Department is required to apply template")
        dept_doc = frappe.get_doc("KPI Department", department)
        if not dept_doc.is_active:
            frappe.throw(f"Department {department} is not active")

        company_freq = frappe.db.get_single_value("KPI Settings", "default_frequency") or "Daily"
        created = []
        for item in self.items:
            if selected_items and item.kpi_name not in selected_items:
                continue
            clean_name = re.sub(r'[^A-Za-z0-9]+', '-', item.kpi_name).upper().strip('-')
            kpi_code = f"{dept_doc.department_code}-{clean_name}"
            item_freq = item.default_frequency or company_freq
            if frappe.db.exists("KPI Definition", kpi_code):
                frappe.db.set_value("KPI Definition", kpi_code, "frequency", item_freq)
                created.append(kpi_code)
                continue
            kpi = frappe.get_doc({
                "doctype": "KPI Definition",
                "kpi_name": item.kpi_name,
                "kpi_code": kpi_code,
                "department": department,
                "measurement_type": item.measurement_type,
                "direction": item.direction or "Higher is Better",
                "target_type": "Fixed Target" if item.default_target else "No Target",
                "target_value": item.default_target,
                "frequency": item_freq,
                "description": item.description,
                "is_active": 1,
                "prediction_enabled": 1,
                "alert_enabled": 1,
            })
            kpi.insert(ignore_permissions=True)
            created.append(kpi.name)
        return created
