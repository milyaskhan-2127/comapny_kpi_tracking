// Productix KPI Tracking — Performance Data Entry Page

frappe.pages["kpi-data-entry-page"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "Performance Data Entry",
        single_column: true,
    });

    page.main.addClass("kpi-tracking-app");
    page._period = null;

    frappe.xcall("productix.kpi_tracking.api.dashboard.get_user_context").then((ctx) => {
        page._ctx = ctx || {};
        page._frequency = (ctx && ctx.default_frequency) || "Daily";
        const deptList = (ctx && ctx.department_list && ctx.department_list.length > 0)
            ? ctx.department_list
            : (ctx && ctx.departments || []).map(d => ({ name: d, department_name: d, department_code: d }));

        page._depts = deptList;

        const params = frappe.utils.get_url_dict();
        let targetDept = null;

        if (ctx.is_admin) {
            targetDept = params.department || "All";
        } else {
            targetDept = ctx.assigned_department || (deptList.length > 0 ? deptList[0].name : null);
        }

        setup_data_entry_actions(page);
        load_pending(page, targetDept);
    }).catch(() => {
        load_pending(page, "All");
    });
};

function setup_data_entry_actions(page) {
    if (page.clear_inner_toolbar) page.clear_inner_toolbar();
    if (page.clear_menu) page.clear_menu();

    const isAdmin = page._ctx && page._ctx.is_admin;
    if (isAdmin) {
        page.set_primary_action("🏢 Company Overview", () => frappe.set_route("kpi-company-overview"), "fa fa-building");
        page.set_secondary_action("🔄 Refresh", () => load_pending(page), "fa fa-sync");

        page.add_inner_button("📊 Department Dashboard", () => frappe.set_route("kpi-department-dashboard", { department: page._selected_dept === 'All' ? '' : page._selected_dept }));
        page.add_inner_button("🤖 AI Assistant", () => frappe.set_route("kpi-ai-assistant"));
        page.add_inner_button("🚨 Action Center", () => frappe.set_route("kpi-action-center"));

        // 3-dot menu items
        page.add_menu_item("🔄 Refresh Submissions", () => load_pending(page));
        page.add_menu_item("🏢 Company Performance Overview", () => frappe.set_route("kpi-company-overview"));
        page.add_menu_item("📊 Department Dashboard", () => frappe.set_route("kpi-department-dashboard", { department: page._selected_dept === 'All' ? '' : page._selected_dept }));
        page.add_menu_item("🤖 AI Assistant", () => frappe.set_route("kpi-ai-assistant"));
        page.add_menu_item("🚨 Action & Alert Center", () => frappe.set_route("kpi-action-center"));
        page.add_menu_item("💾 Backup & Restore Manager", () => frappe.set_route("backups"));
    } else {
        page.set_primary_action("📊 Department Dashboard", () => frappe.set_route("kpi-department-dashboard"), "fa fa-chart-line");
        page.set_secondary_action("🔄 Refresh", () => load_pending(page), "fa fa-sync");

        // 3-dot menu items for Employee
        page.add_menu_item("🔄 Refresh Submissions", () => load_pending(page));
        page.add_menu_item("📊 Department Dashboard", () => frappe.set_route("kpi-department-dashboard"));
    }
}

function load_pending(page, dept) {
    const isAdmin = page._ctx && page._ctx.is_admin;
    if (!isAdmin && page._ctx && page._ctx.assigned_department) {
        dept = page._ctx.assigned_department;
    } else {
        dept = dept || page._selected_dept || (isAdmin ? "All" : ((page._depts && page._depts[0] && page._depts[0].name) || "PRODUCTION"));
    }
    page._selected_dept = dept;

    page.main.html('<div class="text-center p-5"><i class="fa fa-spinner fa-spin fa-2x"></i><p class="mt-2 text-muted">Loading Pending Metric Submissions...</p></div>');

    frappe.xcall("productix.kpi_tracking.api.data_entry.get_pending_kpis", {
        department: dept === "All" ? null : dept,
        period: page._period,
    }).then((kpis) => {
        render_entry(page, kpis, dept);
    }).catch((err) => {
        page.main.html(`
            <div style="max-width:960px;margin:30px auto;text-align:center;padding:40px;background:#fff;border:1px solid #e2e8f0;border-radius:12px;">
                <div style="font-size:36px;margin-bottom:12px;">✍️</div>
                <h4 style="font-weight:700;color:#0f172a;">Data Entry Unavailable</h4>
                <p style="color:#64748b;font-size:13px;max-width:480px;margin:0 auto 20px;">${err.message || 'Unable to access data entry for this department.'}</p>
            </div>
        `);
    });
}

function render_entry(page, kpis, dept) {
    const total = (kpis || []).length;
    const done = (kpis || []).filter((k) => k.submitted).length;
    const pending = total - done;
    const pct = total > 0 ? Math.round((done / total) * 100) : 0;
    const depts = page._depts || [];
    const isAdmin = page._ctx && page._ctx.is_admin;

    let deptControlHtml = '';
    if (isAdmin || (page._ctx && page._ctx.is_ceo)) {
        deptControlHtml = `
            <div style="display:flex;align-items:center;gap:10px;min-width:280px;">
                <label style="margin:0;font-size:13px;font-weight:700;color:#475569;">Department:</label>
                <select id="data-entry-dept-select" class="form-control form-control-sm" style="font-weight:600;max-width:260px;">
                    <option value="All" ${dept === 'All' ? 'selected' : ''}>🏢 All Departments</option>
                    ${depts.map(d => `<option value="${d.name}" ${d.name === dept ? 'selected' : ''}>${frappe.utils.escape_html(d.display_name || d.department_name || d.name)}</option>`).join('')}
                </select>
            </div>
        `;
    } else {
        const curDeptObj = depts.find(d => d.name === dept);
        const curDeptName = (curDeptObj && curDeptObj.display_name) || (curDeptObj && curDeptObj.department_name) || dept;
        deptControlHtml = `
            <div style="display:flex;align-items:center;gap:8px;">
                <span style="font-size:12px;font-weight:700;color:#475569;">Assigned Department:</span>
                <span class="badge badge-primary" style="font-size:13px;padding:5px 12px;background:#2563eb;">${frappe.utils.escape_html(curDeptName)}</span>
            </div>
        `;
    }

    let kpiItemsHtml = '';
    if (kpis && kpis.length > 0) {
        kpiItemsHtml = kpis.map((kpi, idx) => {
            const deptBadge = `<span class="badge badge-light" style="background:#f1f5f9;color:#334155;border:1px solid #e2e8f0;font-size:11px;font-weight:600;margin-right:6px;">${kpi.department}</span>`;

            if (kpi.submitted) {
                const statusCls = (kpi.status || 'On Track').toLowerCase().replace(/[\/\s]+/g, '-');
                return `
                    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-left:4px solid #10b981;border-radius:10px;padding:16px 20px;margin-bottom:12px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;">
                        <div style="display:flex;align-items:center;gap:12px;">
                            <span style="font-size:22px;">✅</span>
                            <div>
                                <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
                                    ${deptBadge}
                                    <strong style="font-size:15px;color:#0f172a;">${kpi.kpi_name}</strong>
                                    <span style="font-size:12px;color:#64748b;margin-left:4px;">Target: ${kpi.target || "N/A"} ${kpi.unit || ""}</span>
                                </div>
                                <div style="font-size:12px;color:#94a3b8;margin-top:3px;">
                                    Submitted actual value: <strong>${kpi.submitted_value}</strong> (${Math.round(kpi.achievement || 0)}%) by <strong>${kpi.entered_by_name || kpi.entered_by || 'User'}</strong>
                                </div>
                            </div>
                        </div>
                        <div style="display:flex;align-items:center;gap:8px;">
                            <span class="kpi-tracking-status-badge kpi-tracking-status-badge--${statusCls}">${kpi.status || 'On Track'}</span>
                            <span class="badge badge-success" style="font-size:11px;padding:6px 12px;">Submitted (${kpi.period})</span>
                        </div>
                    </div>
                `;
            }

            return `
                <div class="card mb-3" id="entry-${idx}" style="border:1px solid #e2e8f0;border-left:4px solid #3b82f6;border-radius:10px;box-shadow:0 1px 3px rgba(0,0,0,0.03);">
                    <div class="card-body" style="padding:18px 22px;">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;flex-wrap:wrap;gap:8px;">
                            <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
                                ${deptBadge}
                                <strong style="font-size:15px;color:#0f172a;">${kpi.kpi_name}</strong>
                                <span style="font-size:12px;color:#64748b;margin-left:4px;">Frequency: <strong>${kpi.frequency}</strong> · Direction: <strong>${kpi.direction}</strong></span>
                            </div>
                            <span class="badge" style="background:#eff6ff;color:#1e40af;font-size:11px;padding:5px 10px;">Due Period: ${kpi.period}</span>
                        </div>

                        <div class="row align-items-center">
                            <div class="col-md-5 mb-2">
                                <label style="font-size:12px;font-weight:600;color:#475569;">Actual Value (${kpi.unit || kpi.measurement_type})</label>
                                <input type="number" class="form-control kpi-actual-input" data-kpi="${kpi.kpi}" data-dept="${kpi.department}" step="any" placeholder="Enter actual achieved value...">
                            </div>
                            <div class="col-md-4 mb-2">
                                <label style="font-size:12px;font-weight:600;color:#475569;">Target Benchmark</label>
                                <div style="font-size:14px;font-weight:700;color:#0f172a;padding:8px 12px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;">
                                    ${kpi.target != null ? kpi.target : "No Target"} ${kpi.unit || ""}
                                </div>
                            </div>
                            <div class="col-md-3 mb-2">
                                <label style="font-size:12px;font-weight:600;color:transparent;">Action</label>
                                <button class="btn btn-primary btn-block kpi-submit-btn" data-idx="${idx}" data-kpi="${kpi.kpi}" data-dept="${kpi.department}" data-period="${kpi.period}" style="font-weight:600;">
                                    Submit
                                </button>
                            </div>
                        </div>

                        ${kpi.inputs && kpi.inputs.length > 0 ? `
                            <div style="margin-top:14px;padding-top:12px;border-top:1px solid #f1f5f9;">
                                <span style="font-size:12px;font-weight:700;color:#475569;">Detailed Input Parameters:</span>
                                <div class="row mt-2">
                                    ${kpi.inputs.map(inp => `
                                        <div class="col-md-6 mb-2">
                                            <label style="font-size:11px;color:#64748b;">${inp.label}${inp.is_required ? " *" : ""} (${inp.unit || ''})</label>
                                            <input type="number" class="form-control form-control-sm kpi-input-field" data-field="${inp.field_name}" data-label="${inp.label}" step="any" placeholder="0.00">
                                        </div>
                                    `).join('')}
                                </div>
                            </div>
                        ` : ''}
                    </div>
                </div>
            `;
        }).join('');
    } else {
        kpiItemsHtml = `
            <div style="text-align:center;padding:40px;background:#fff;border:1px dashed #cbd5e1;border-radius:10px;">
                <div style="font-size:32px;margin-bottom:8px;">🎉</div>
                <div style="font-weight:700;font-size:16px;color:#0f172a;margin-bottom:4px;">No Pending Metric Submissions</div>
                <div style="font-size:13px;color:#64748b;margin-bottom:16px;">All metric targets are up to date for the current reporting cycle.</div>
            </div>
        `;
    }

    let html = `
        <div style="max-width:1100px;margin:0 auto;padding:10px 0 40px;">
            <!-- Back button & Breadcrumb Navigation -->
            <div style="margin-bottom:14px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;">
                <div style="display:flex;align-items:center;gap:8px;">
                    <button class="btn btn-sm btn-default" id="data-entry-home-btn" style="font-weight:600;color:#475569;" title="Return to Company Tracking Workspace">
                        <i class="fa fa-home mr-1"></i> Workspace Home
                    </button>
                    <button class="btn btn-sm btn-default" id="data-entry-back-btn" style="font-weight:600;color:#475569;">
                        <i class="fa fa-arrow-left mr-1"></i> ${isAdmin ? 'Back to Overview' : 'Back to Dashboard'}
                    </button>
                </div>
                <div style="font-size:12px;color:#64748b;">
                    Authenticated as <strong>${page._ctx.full_name || 'User'}</strong> · Role: <span class="badge ${isAdmin ? 'badge-primary' : 'badge-info'}">${isAdmin ? 'Admin' : 'Employee'}</span>
                </div>
            </div>

            <!-- Hero Header Banner -->
            <div style="background:linear-gradient(135deg, #1e293b 0%, #334155 60%, #475569 100%);border-radius:12px;padding:26px 30px;color:#fff;margin-bottom:24px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:18px;">
                <div>
                    <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
                        <span style="background:rgba(56,189,248,0.2);color:#38bdf8;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700;letter-spacing:0.5px;text-transform:uppercase;">
                            ✍️ Operational Submissions
                        </span>
                        <span class="productix-status-pulse"></span>
                    </div>
                    <h1 style="margin:0 0 6px 0;font-size:22px;font-weight:700;color:#fff;">
                        <span>Performance Data Entry &amp; Submissions</span>
                    </h1>
                    <p style="margin:0;font-size:13px;color:#94a3b8;">
                        Submit operational metric values, production yields, safety counts, and targets.
                    </p>
                </div>
                <div style="display:flex;gap:14px;align-items:center;">
                    <div style="background:rgba(255,255,255,0.1);border:1px solid rgba(255,255,255,0.2);border-radius:10px;padding:12px 20px;text-align:center;backdrop-filter:blur(4px);">
                        <div style="font-size:26px;font-weight:800;color:#38bdf8;line-height:1;">${done}/${total}</div>
                        <div style="font-size:11px;text-transform:uppercase;color:#94a3b8;font-weight:600;margin-top:4px;">Submitted (${pct}%)</div>
                    </div>
                </div>
            </div>

            <!-- Department Switcher & Progress -->
            <div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px 20px;margin-bottom:24px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:14px;">
                ${deptControlHtml}

                <div style="flex:1;max-width:320px;min-width:180px;">
                    <div class="kpi-tracking-progress-bar">
                        <div class="kpi-tracking-progress-fill" style="width:${pct}%;"></div>
                        <span class="kpi-tracking-progress-text">${done}/${total} Completed (${pct}%)</span>
                    </div>
                </div>
            </div>

            <!-- Submissions List -->
            <div id="kpi-submissions-list">
                ${kpiItemsHtml}
            </div>
        </div>
    `;

    page.main.html(html);

    // Back & Home button handlers
    page.main.find("#data-entry-home-btn").on("click", function () {
        frappe.set_route("company-tracking-system");
    });
    page.main.find("#data-entry-back-btn").on("click", function () {
        if (isAdmin) {
            frappe.set_route("kpi-company-overview");
        } else {
            frappe.set_route("kpi-department-dashboard");
        }
    });

    // Switch department handler
    page.main.find("#data-entry-dept-select").on("change", function() {
        const selected = $(this).val();
        load_pending(page, selected);
    });

    // Submit individual KPI
    page.main.find(".kpi-submit-btn").on("click", function () {
        const btn = $(this);
        const container = btn.closest(".card");
        const actual_input = container.find(".kpi-actual-input");
        const actual_value = actual_input.val();

        if (actual_value === "" || actual_value == null) {
            frappe.show_alert({ message: "Please enter a value", indicator: "orange" });
            actual_input.focus();
            return;
        }

        const kpi = btn.data("kpi") || actual_input.data("kpi");
        const department = btn.data("dept") || actual_input.data("dept");
        const period = btn.data("period");

        const input_values = [];
        container.find(".kpi-input-field").each(function () {
            if ($(this).val()) {
                input_values.push({
                    field_name: $(this).data("field"),
                    label: $(this).data("label"),
                    value: parseFloat($(this).val()),
                    field_type: "Float",
                });
            }
        });

        btn.prop("disabled", true).html('<i class="fa fa-spinner fa-spin"></i> Submitting...');

        frappe.xcall("productix.kpi_tracking.api.data_entry.submit_kpi_data", {
            kpi, department, actual_value,
            period: period || null,
            input_values: input_values.length > 0 ? input_values : null,
        }).then((r) => {
            frappe.show_alert({ message: `✅ Submitted: ${r.status} (${Math.round(r.achievement)}%)`, indicator: r.status === "On Track" ? "green" : "orange" });
            load_pending(page, dept);
        }).catch((err) => {
            btn.prop("disabled", false).text("Submit");
            frappe.show_alert({ message: "Error submitting: " + (err.message || ""), indicator: "red" });
        });
    });
}
