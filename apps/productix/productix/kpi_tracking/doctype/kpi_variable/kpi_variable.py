import frappe
from frappe.model.document import Document
import re

class KPIVariable(Document):
    def validate(self):
        self.variable_code = self.variable_code.upper().strip().replace(" ", "_")
        if not re.match(r'^[A-Z][A-Z0-9_]*$', self.variable_code):
            frappe.throw("Variable Code must start with a letter and contain only uppercase letters, numbers, and underscores")
        if not self.display_label:
            self.display_label = self.variable_name
        if self.source_type == "ERPNext DocType":
            if not self.source_doctype:
                frappe.throw("Source DocType is required when source type is ERPNext DocType")
            if not self.source_field:
                frappe.throw("Source Field is required when source type is ERPNext DocType")

    def get_display_name(self):
        return self.display_label or self.variable_name

    @frappe.whitelist()
    def fetch_value(self, filters=None, from_date=None, to_date=None):
        if self.source_type != "ERPNext DocType":
            return None
        query_filters = {}
        if self.source_filters:
            import json
            query_filters = json.loads(self.source_filters) if isinstance(self.source_filters, str) else self.source_filters
        if from_date and self.source_date_field:
            query_filters[self.source_date_field] = [">=", from_date]
        if to_date and self.source_date_field:
            query_filters[self.source_date_field] = ["<=", to_date] if from_date is None else ["between", [from_date, to_date]]
        if filters:
            query_filters.update(filters)
        agg = self.source_aggregation or "SUM"
        result = frappe.db.get_list(
            self.source_doctype,
            filters=query_filters,
            fields=[f"{agg.lower()}({self.source_field}) as value"],
            as_list=True
        )
        return result[0][0] if result and result[0][0] else 0
