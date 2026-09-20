frappe.query_reports["KPI Alert and Action Report"] = {
    "filters": [
        {
            "fieldname": "department",
            "label": __("Department"),
            "fieldtype": "Link",
            "options": "KPI Department",
            "default": "",
            "get_query": function() {
                return {
                    "filters": {
                        "is_active": 1
                    }
                };
            }
        },
        {
            "fieldname": "kpi",
            "label": __("KPI"),
            "fieldtype": "Link",
            "options": "KPI Definition",
            "default": "",
            "get_query": function() {
                const dept = frappe.query_report.get_filter_value("department");
                return {
                    "filters": dept ? { "department": dept, "is_active": 1 } : { "is_active": 1 }
                };
            }
        },
        {
            "fieldname": "severity",
            "label": __("Severity"),
            "fieldtype": "Select",
            "options": "\nCritical\nWarning\nInfo",
            "default": ""
        },
        {
            "fieldname": "status",
            "label": __("Status"),
            "fieldtype": "Select",
            "options": "\nOpen\nActive\nAcknowledged\nResolved",
            "default": ""
        },
        {
            "fieldname": "alert_type",
            "label": __("Alert Type"),
            "fieldtype": "Select",
            "options": "\nTarget Miss\nGrowth Decline\nNegative Trend\nPrediction Miss\nRepeated Decline\nAdmin Directive\nEmployee Escalation\nMissing Data Reminder",
            "default": ""
        },
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": ""
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": ""
        },
        {
            "fieldname": "period",
            "label": __("Trigger Period"),
            "fieldtype": "Data",
            "default": ""
        }
    ],
    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (column.fieldname === "severity" && data && data.severity) {
            let color = "blue";
            if (data.severity === "Critical") color = "red";
            else if (data.severity === "Warning") color = "orange";
            return `<span class="indicator-pill ${color}">${data.severity}</span>`;
        }
        if (column.fieldname === "status" && data && data.status) {
            let color = "blue";
            if (data.status === "Resolved") color = "green";
            else if (data.status === "Active") color = "red";
            else if (data.status === "Acknowledged") color = "orange";
            return `<span class="indicator-pill ${color}">${data.status}</span>`;
        }
        return value;
    }
};
