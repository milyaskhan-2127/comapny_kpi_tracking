frappe.query_reports["KPI Data Quality and Completeness Report"] = {
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
            "fieldname": "status",
            "label": __("Quality Status"),
            "fieldtype": "Select",
            "options": "\nComplete\nIncomplete\nMissing\nInvalid\nNeeds Review",
            "default": ""
        }
    ],
    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (column.fieldname === "quality_status" && data && data.quality_status) {
            let color = "blue";
            if (data.quality_status === "Complete") color = "green";
            else if (data.quality_status === "Incomplete" || data.quality_status === "Needs Review") color = "orange";
            else if (data.quality_status === "Missing" || data.quality_status === "Invalid") color = "red";
            return `<span class="indicator-pill ${color}">${data.quality_status}</span>`;
        }
        if (column.fieldname === "completeness_pct" && data && data.completeness_pct !== null && data.completeness_pct !== undefined) {
            const cp = parseFloat(data.completeness_pct);
            const color = cp >= 100 ? "green" : (cp >= 50 ? "orange" : "red");
            return `<span class="indicator-pill ${color}">${cp.toFixed(1)}%</span>`;
        }
        if (column.fieldname === "invalid_values" && data && data.invalid_values > 0) {
            return `<span class="indicator-pill red font-weight-bold">${data.invalid_values}</span>`;
        }
        if (column.fieldname === "missing_entries" && data && data.missing_entries > 0) {
            return `<span class="indicator-pill red">${data.missing_entries}</span>`;
        }
        return value;
    }
};
