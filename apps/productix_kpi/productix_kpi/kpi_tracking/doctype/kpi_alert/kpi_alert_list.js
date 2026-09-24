// Productix KPI Tracking — KPI Alert List View

frappe.listview_settings["KPI Alert"] = {
    add_fields: ["severity", "status", "department", "alert_type", "sender_name", "creation", "subject"],
    get_indicator: function (doc) {
        if (doc.status === "Resolved") {
            return [__("Resolved"), "green", "status,=,Resolved"];
        }
        if (doc.status === "Acknowledged") {
            return [__("Acknowledged"), "purple", "status,=,Acknowledged"];
        }
        if (doc.severity === "Critical") {
            return [__("Critical"), "red", "severity,=,Critical"];
        }
        if (doc.severity === "Warning") {
            return [__("Warning"), "orange", "severity,=,Warning"];
        }
        return [__("Info"), "blue", "severity,=,Info"];
    },
    onload: function (listview) {
        const user = frappe.session.user;
        const is_admin = user === "Administrator" ||
                         frappe.user.has_role("System Manager") ||
                         frappe.user.has_role("KPI Admin");

        if (!is_admin) {
            // Non-admin employees view department alerts; remove "Add KPI Alert" action
            if (listview.page.clear_primary_action) {
                listview.page.clear_primary_action();
            }

            listview.page.set_secondary_action(__("🏢 Department Dashboard"), function () {
                frappe.set_route("kpi-department-dashboard");
            }, "fa fa-arrow-left");
        } else {
            listview.page.add_inner_button(__("🚨 Action Center"), function () {
                frappe.set_route("kpi-action-center");
            });
            listview.page.add_inner_button(__("🏢 Company Overview"), function () {
                frappe.set_route("kpi-company-overview");
            });
        }
    }
};
