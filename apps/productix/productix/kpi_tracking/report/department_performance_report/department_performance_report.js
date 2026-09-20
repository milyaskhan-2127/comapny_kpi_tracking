frappe.query_reports["Department Performance Report"] = {
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
            "label": __("Status"),
            "fieldtype": "Select",
            "options": "\nOn Track\nWarning\nCritical\nPending / No Data",
            "default": ""
        }
    ],
    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (column.fieldname === "score" && data && data.score !== null && data.score !== undefined) {
            const sc = parseFloat(data.score);
            const color = sc >= 80 ? "green" : (sc >= 60 ? "orange" : "red");
            return `<span class="indicator-pill ${color}"><b>${sc.toFixed(1)}/100</b></span>`;
        }
        if (column.fieldname === "previous_score" && data && data.previous_score !== null && data.previous_score !== undefined) {
            const sc = parseFloat(data.previous_score);
            return `<span class="indicator-pill grey">${sc.toFixed(1)}/100</span>`;
        }
        if (column.fieldname === "growth_pct" && data && data.growth_pct !== null && data.growth_pct !== undefined) {
            const g = parseFloat(data.growth_pct);
            const prefix = g > 0 ? "+" : "";
            const color = g > 0 ? "green" : (g < 0 ? "red" : "grey");
            return `<span class="indicator-pill ${color}">${prefix}${g.toFixed(1)}%</span>`;
        }
        if (column.fieldname === "status" && data && data.status) {
            let color = "blue";
            if (data.status === "On Track") color = "green";
            else if (data.status === "Warning") color = "orange";
            else if (data.status === "Critical") color = "red";
            return `<span class="indicator-pill ${color}">${data.status}</span>`;
        }
        if (column.fieldname === "critical_count" && data && data.critical_count > 0) {
            return `<span class="indicator-pill red font-weight-bold">${data.critical_count}</span>`;
        }
        if (column.fieldname === "open_alerts" && data && data.open_alerts > 0) {
            return `<span class="indicator-pill red">${data.open_alerts}</span>`;
        }
        return value;
    }
};
