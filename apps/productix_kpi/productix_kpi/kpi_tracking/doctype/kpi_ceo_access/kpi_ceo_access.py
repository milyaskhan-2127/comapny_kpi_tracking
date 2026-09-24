import frappe
from frappe.model.document import Document


class KPICEOAccess(Document):
    def validate(self):
        if self.access_scope == "Selected Departments Only" and not self.department_access:
            frappe.throw("At least one department must be selected when using 'Selected Departments Only' scope")

        self._validate_kpi_department_match()

    def _validate_kpi_department_match(self):
        if self.access_scope != "Selected Departments Only" or not self.kpi_access:
            return

        allowed_departments = {d.department for d in self.department_access}
        specific_kpi_departments = {
            d.department for d in self.department_access
            if d.access_level == "View Specific KPIs"
        }

        for row in self.kpi_access:
            if row.department not in allowed_departments:
                frappe.throw(
                    f"KPI '{row.kpi_name}' is in department '{row.department}' "
                    f"which is not in the department access list"
                )
            if row.department not in specific_kpi_departments:
                frappe.throw(
                    f"KPI '{row.kpi_name}' is in department '{row.department}' "
                    f"which has access level other than 'View Specific KPIs'. "
                    f"Individual KPI access only applies to departments with 'View Specific KPIs' level."
                )
