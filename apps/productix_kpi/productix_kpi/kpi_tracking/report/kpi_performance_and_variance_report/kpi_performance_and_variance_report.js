frappe.query_reports["KPI Performance and Variance Report"] = {
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
            "fieldname": "business_unit",
            "label": __("Business Unit"),
            "fieldtype": "Link",
            "options": "KPI Business Unit",
            "default": ""
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
            "fieldname": "frequency",
            "label": __("Frequency"),
            "fieldtype": "Select",
            "options": "\nDaily\nWeekly\nMonthly\nQuarterly\nYearly",
            "default": ""
        },
        {
            "fieldname": "period",
            "label": __("Reporting Period"),
            "fieldtype": "Data",
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
            "fieldname": "status",
            "label": __("Status"),
            "fieldtype": "Select",
            "options": "\nMeeting Target\nAbove Target\nBelow Target\nMissing Data\nUnavailable\nOn Track\nWarning\nCritical",
            "default": ""
        }
    ],
    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (column.fieldname === "normalized_score" && data && data.normalized_score !== null && data.normalized_score !== undefined) {
            const sc = parseFloat(data.normalized_score);
            const color = sc >= 80 ? "green" : (sc >= 60 ? "orange" : "red");
            return `<span class="indicator-pill ${color}">${sc.toFixed(1)}/100</span>`;
        }
        if (column.fieldname === "achievement_status" && data && data.achievement_status) {
            let color = "blue";
            if (data.achievement_status === "Meeting Target" || data.achievement_status === "Above Target") color = "green";
            else if (data.achievement_status === "Below Target") color = "red";
            else if (data.achievement_status === "Missing Data" || data.achievement_status === "Unavailable") color = "orange";
            return `<span class="indicator-pill ${color}">${data.achievement_status}</span>`;
        }
        if (column.fieldname === "status" && data && data.status) {
            let color = "blue";
            if (data.status === "On Track") color = "green";
            else if (data.status === "Warning") color = "orange";
            else if (data.status === "Critical") color = "red";
            return `<span class="indicator-pill ${color}">${data.status}</span>`;
        }
        return value;
    }
};
