// Productix KPI Tracking — KPI Definition List View

frappe.listview_settings["KPI Definition"] = {
    add_fields: ["department", "target_value", "unit", "direction", "frequency", "is_active", "weight"],
    get_indicator: function (doc) {
        if (doc.is_active) {
            return [__("Active"), "green", "is_active,=,1"];
        }
        return [__("Inactive"), "gray", "is_active,=,0"];
    },
    onload: function (listview) {
        const user = frappe.session.user;
        const is_admin = user === "Administrator" ||
                         frappe.user.has_role("System Manager") ||
                         frappe.user.has_role("KPI Admin");

        if (!is_admin) {
            if (listview.page.clear_primary_action) {
                listview.page.clear_primary_action();
            }

            listview.page.set_secondary_action(__("🏢 Department Dashboard"), function () {
                frappe.set_route("kpi-department-dashboard");
            }, "fa fa-arrow-left");
        } else {
            listview.page.add_inner_button(__("🏢 Company Overview"), function () {
                frappe.set_route("kpi-company-overview");
            });
            listview.page.add_inner_button(__("📐 Formula Builder"), function () {
                frappe.set_route("kpi-formula-builder");
            });
            listview.page.add_inner_button(__("✍️ Metric Data Entry"), function () {
                frappe.set_route("kpi-data-entry-page");
            });
        }
    }
};
