frappe.query_reports["KPI Trend and Forecast Report"] = {
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
            "fieldname": "horizon",
            "label": __("Forecast Horizon"),
            "fieldtype": "Select",
            "options": "next_month\nnext_quarter\nnext_week\ntomorrow",
            "default": "next_month"
        },
        {
            "fieldname": "trend",
            "label": __("Trend Direction"),
            "fieldtype": "Select",
            "options": "\nImproving\nStable\nDeclining",
            "default": ""
        },
        {
            "fieldname": "frequency",
            "label": __("Frequency"),
            "fieldtype": "Select",
            "options": "\nDaily\nWeekly\nMonthly\nQuarterly\nYearly",
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
        if (column.fieldname === "trend" && data && data.trend) {
            let color = "blue";
            if (data.trend === "Improving") color = "green";
            else if (data.trend === "Declining") color = "red";
            return `<span class="indicator-pill ${color}">${data.trend}</span>`;
        }
        if (column.fieldname === "growth_pct" && data && data.growth_pct !== null && data.growth_pct !== undefined) {
            const g = parseFloat(data.growth_pct);
            const prefix = g > 0 ? "+" : "";
            const color = g > 0 ? "green" : (g < 0 ? "red" : "grey");
            return `<span class="indicator-pill ${color}">${prefix}${g.toFixed(1)}%</span>`;
        }
        if (column.fieldname === "prediction_status" && data && data.prediction_status) {
            const color = data.prediction_status === "Ready" ? "green" : "orange";
            return `<span class="indicator-pill ${color}">${data.prediction_status}</span>`;
        }
        if (column.fieldname === "confidence" && data && data.confidence !== null && data.confidence !== undefined) {
            const c = parseFloat(data.confidence);
            const color = c >= 80 ? "green" : "orange";
            return `<span class="indicator-pill ${color}">${c.toFixed(1)}%</span>`;
        }
        return value;
    }
};
