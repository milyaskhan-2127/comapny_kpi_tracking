// ============================================================
// Productix KPI — Custom Scripts for ERPNext native DocTypes
// User (Staff / User Creation with Direct Password + KPI role)
// (split out of the monolithic native_doctype_scripts.js)
// ============================================================

// ─────────────────────────────────────────────
// USER (Staff / User Creation with Direct Password)
// ─────────────────────────────────────────────
function open_kpi_role_access_dialog(frm) {
    const user_id = frm.doc.name;

    // Fresh context: current role, dept, CEO config, depts+KPIs
    frappe.xcall("productix_kpi.kpi_tracking.api.user_management.get_user_kpi_context", { user: user_id }).then(function(ctx) {
        ctx = ctx || {};
        const current_role = ctx.current_role || "Employee";
        const depts = ctx.departments || [];
        const ceoConfig = ctx.ceo_config || null;
        const deptOptions = depts.map(function(d) { return d.name; });

        const d = new frappe.ui.Dialog({
            title: "⚙️ KPI Role & Access — " + frappe.utils.escape_html(user_id),
            size: "extra-large",
            fields: [
                {
                    fieldtype: "Select",
                    fieldname: "role",
                    label: "KPI Role",
                    reqd: 1,
                    options: "Employee\nCEO\nAdministrator",
                    default: current_role
                },
                {
                    fieldtype: "Select",
                    fieldname: "department",
                    label: "Assigned Department (for Employee)",
                    options: deptOptions.join("\n"),
                    default: ctx.department || (depts[0] ? depts[0].name : "")
                },
                {
                    fieldtype: "Check",
                    fieldname: "is_active",
                    label: "Active Assignment",
                    default: ctx.is_active ? 1 : 0
                },
                {
                    fieldtype: "Section Break",
                    fieldname: "ceo_section",
                    label: "CEO Access Configuration"
                },
                {
                    fieldtype: "Column Break",
                    fieldname: "ceo_col_break"
                },
                {
                    fieldtype: "HTML",
                    fieldname: "ceo_config_html"
                }
            ],
            primary_action_label: "Save Role & Access",
            primary_action: function(values) {
                if (values.role === "Employee" && !values.department) {
                    frappe.msgprint(__("Please select an assigned department for the Employee role."));
                    return;
                }
                d.get_primary_btn().prop("disabled", true);

                const args = {
                    user_id: user_id,
                    email: frm.doc.email || user_id,
                    full_name: frm.doc.full_name || user_id,
                    role: values.role,
                    department: values.department,
                    is_active: values.is_active ? 1 : 0
                };

                if (values.role === "CEO") {
                    args.ceo_access = JSON.stringify(collect_ceo_config(d.fields_dict.ceo_config_html.$wrapper));
                }

                frappe.xcall("productix_kpi.kpi_tracking.api.user_management.save_user", args).then(function(res) {
                    frappe.show_alert({ message: "✅ KPI role & access for " + user_id + " saved.", indicator: "green" });
                    d.hide();
                    frappe.ui.form.refresh("User", user_id);
                }).catch(function(err) {
                    d.get_primary_btn().prop("disabled", false);
                    frappe.show_alert({ message: "Error: " + (err.message || "Failed to save"), indicator: "red" });
                });
            }
        });

        // Renders the CEO configuration builder (same UI as Company Overview Users section)
        function render_ceo_builder($target, config) {
            config = config || { can_view_company_overview: 1, can_view_machines: 1 };
            const scope = config.access_scope === "Selected Departments Only" ? "Selected Departments Only" : "All Departments";
            const selDepts = (config.departments || []).filter(function(x) { return x && x.department; });
            const selKpis = (config.kpis || []).filter(function(x) { return x && x.kpi; });
            const selScope = {};
            selDepts.forEach(function(x) { selScope[x.department] = x.access_level || "View All KPIs"; });
            const selKpiSet = {};
            selKpis.forEach(function(x) { selKpiSet[x.kpi] = x.department; });

            let deptHtml = "";
            (depts || []).forEach(function(dep) {
                const level = selScope[dep.name] || "View All KPIs";
                const kpiChecks = (dep.kpis || []).map(function(k) {
                    const checked = selKpiSet[k.name] ? "checked" : "";
                    return '<label class="ceo-kpi-check" data-dept="' + frappe.utils.escape_html(dep.name) +
                        '" style="display:' + (level === "View Specific KPIs" ? "inline-flex" : "none") +
                        ';align-items:center;gap:4px;margin-right:10px;font-size:12px;font-weight:400;">' +
                        '<input type="checkbox" class="ceo-kpi-cb" data-kpi="' + frappe.utils.escape_html(k.name) + '" data-dept="' +
                        frappe.utils.escape_html(dep.name) + '" ' + checked + '> ' + frappe.utils.escape_html(k.kpi_name || k.name) + "</label>";
                }).join("");
                deptHtml += '<div class="ceo-dept-row" data-dept="' + frappe.utils.escape_html(dep.name) + '" style="border:1px solid var(--border-color,#e2e8f0);border-radius:8px;padding:8px 10px;margin-bottom:8px;">' +
                    '<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">' +
                    '<label style="margin:0;font-weight:600;font-size:13px;display:flex;align-items:center;gap:6px;">' +
                    '<input type="checkbox" class="ceo-dept-cb" data-dept="' + frappe.utils.escape_html(dep.name) + '" ' + (selScope[dep.name] ? "checked" : "") + '> ' +
                    frappe.utils.escape_html(dep.display_name || dep.department_name || dep.name) + "</label>" +
                    '<select class="form-control form-control-sm ceo-dept-level" data-dept="' + frappe.utils.escape_html(dep.name) + '" style="width:auto;">' +
                    '<option value="View All KPIs"' + (level === "View All KPIs" ? " selected" : "") + ">View All KPIs</option>" +
                    '<option value="View Specific KPIs"' + (level === "View Specific KPIs" ? " selected" : "") + ">View Specific KPIs</option>" +
                    '<option value="View Summary Only"' + (level === "View Summary Only" ? " selected" : "") + ">View Summary Only</option>" +
                    "</select></div>" +
                    '<div class="mt-2" style="display:' + (selScope[dep.name] ? "block" : "none") + ';">' +
                    (kpiChecks || '<span class="text-muted" style="font-size:11px;">No active KPIs in this department.</span>') + "</div></div>";
            });

            $target.html(
                '<div style="padding:2px 0;">' +
                '<div class="form-group"><label style="font-weight:600;font-size:12px;">Access Scope</label>' +
                '<select class="form-control ceo-scope">' +
                '<option value="All Departments"' + (scope === "All Departments" ? " selected" : "") + ">All Departments</option>" +
                '<option value="Selected Departments Only"' + (scope === "Selected Departments Only" ? " selected" : "") + ">Selected Departments Only</option>" +
                "</select></div>" +
                '<div class="form-group"><label style="font-weight:600;font-size:12px;display:block;margin-bottom:4px;">Capabilities</label>' +
                '<label style="font-weight:400;font-size:12px;margin-right:14px;display:inline-flex;gap:4px;"><input type="checkbox" class="ceo-can-overview" ' +
                (config.can_view_company_overview ? "checked" : "") + "> Company Overview</label>" +
                '<label style="font-weight:400;font-size:12px;display:inline-flex;gap:4px;"><input type="checkbox" class="ceo-can-machines" ' +
                (config.can_view_machines ? "checked" : "") + "> Machine Health</label></div>" +
                '<div style="font-weight:600;font-size:12px;margin:10px 0 6px;">Department Access</div>' +
                '<div id="ceo-dept-list" style="max-height:260px;overflow:auto;padding-right:4px;">' +
                (deptHtml || '<div class="text-muted" style="font-size:12px;">No active departments found.</div>') + "</div></div>"
            );

            $target.find(".ceo-scope").on("change", function() {
                const scopeVal = $(this).val();
                $target.find("#ceo-dept-list").css("display", scopeVal === "Selected Departments Only" ? "block" : "none");
            }).trigger("change");

            $target.find(".ceo-dept-cb").on("change", function() {
                const depName = $(this).data("dept");
                const checked = $(this).is(":checked");
                const $row = $target.find('.ceo-dept-row[data-dept="' + depName + '"]');
                $row.find(".ceo-kpi-check").css("display",
                    checked && $row.find(".ceo-dept-level").val() === "View Specific KPIs" ? "inline-flex" : "none");
                $row.find(".ceo-dept-level").prop("disabled", !checked).css("opacity", checked ? 1 : 0.5);
            });

            $target.find(".ceo-dept-level").on("change", function() {
                const depName = $(this).data("dept");
                const lvl = $(this).val();
                $target.find('.ceo-kpi-check[data-dept="' + depName + '"]').css("display", lvl === "View Specific KPIs" ? "inline-flex" : "none");
            });

            $target.find(".ceo-dept-level").each(function() {
                const depName = $(this).data("dept");
                const checked = $target.find('.ceo-dept-cb[data-dept="' + depName + '"]').is(":checked");
                $(this).prop("disabled", !checked).css("opacity", checked ? 1 : 0.5);
            });
        }

        function collect_ceo_config($target) {
            const scopeVal = $target.find(".ceo-scope").val() || "All Departments";
            const departments = [];
            $target.find(".ceo-dept-cb:checked").each(function() {
                const depName = $(this).data("dept");
                departments.push({
                    department: depName,
                    access_level: $target.find('.ceo-dept-level[data-dept="' + depName + '"]').val() || "View All KPIs"
                });
            });
            const kpis = [];
            $target.find(".ceo-kpi-cb:checked").each(function() {
                kpis.push({ department: $(this).data("dept"), kpi: $(this).data("kpi") });
            });
            return {
                access_scope: scopeVal,
                can_view_company_overview: $target.find(".ceo-can-overview").is(":checked") ? 1 : 0,
                can_view_machines: $target.find(".ceo-can-machines").is(":checked") ? 1 : 0,
                departments: departments,
                kpis: kpis
            };
        }

        function update_ceo_section_visibility() {
            const role = d.get_value("role");
            ["ceo_section", "ceo_col_break", "ceo_config_html"].forEach(function(fn) {
                const f = d.fields_dict[fn];
                if (f && f.wrapper) {
                    $(f.wrapper).toggle(role === "CEO");
                }
            });
            const isEmployee = role === "Employee";
            d.set_df_property("department", "reqd", isEmployee ? 1 : 0);
            d.set_df_property("department", "hidden", isEmployee ? 0 : 1);
        }

        d.fields_dict.role.$input.on("change", function() {
            update_ceo_section_visibility();
            if (d.get_value("role") === "CEO") {
                render_ceo_builder(d.fields_dict.ceo_config_html.$wrapper, ceoConfig);
            }
        });

        if (current_role === "CEO") {
            render_ceo_builder(d.fields_dict.ceo_config_html.$wrapper, ceoConfig);
        }
        update_ceo_section_visibility();
        d.show();
    }).catch(function(err) {
        frappe.msgprint({
            title: "KPI Context Unavailable",
            message: (err && err.message) || "Could not load KPI role context for this user.",
            indicator: "red"
        });
    });
}

frappe.ui.form.on('User', {
    onload: function(frm) {
        if (frm.is_new()) {
            frm.set_value('send_welcome_email', 0);
            if (frm.fields_dict['new_password']) {
                frm.set_df_property('new_password', 'hidden', 0);
            }
        }
    },
    refresh: function(frm) {
        if (frm.is_new()) {
            frm.set_value('send_welcome_email', 0);
            if (frm.fields_dict['new_password']) {
                frm.set_df_property('new_password', 'hidden', 0);
            }
            frm.set_intro(
                '<div style="background:#f0fdf4;border:1px solid #86efac;border-radius:6px;padding:10px 14px;color:#166534;font-size:13px;">' +
                '🔑 <strong>Direct Password Creation:</strong> Enter the user password in the Password field. The account is created ready for immediate login without email verification.' +
                '</div>',
                false
            );
        } else {
            frm.add_custom_button(__('⚙️ KPI Role & Access Configuration'), function() {
                open_kpi_role_access_dialog(frm);
            }, __('KPI Tracking'));
        }
    }
});