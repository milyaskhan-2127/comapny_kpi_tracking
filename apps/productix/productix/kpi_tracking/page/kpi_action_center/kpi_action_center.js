// Productix KPI Tracking — Action Center Page (Admin)

frappe.pages["kpi-action-center"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "KPI Action & Alert Center",
        single_column: true,
    });

    page.main.addClass("kpi-tracking-app");

    // Check user context for Admin authorization
    frappe.xcall("productix.kpi_tracking.api.dashboard.get_user_context").then((ctx) => {
        page._ctx = ctx || {};
        if (!ctx.is_admin) {
            frappe.show_alert({ message: "Action Center is restricted to administrators.", indicator: "orange" });
            frappe.set_route("kpi-department-dashboard");
            return;
        }

        setup_action_center_actions(page);
        load_actions(page);
    }).catch(() => {
        frappe.set_route("kpi-department-dashboard");
    });
};

function setup_action_center_actions(page) {
    if (page.clear_inner_toolbar) page.clear_inner_toolbar();
    if (page.clear_menu) page.clear_menu();

    page.set_primary_action("🏢 Company Overview", () => frappe.set_route("kpi-company-overview"), "fa fa-building");
    page.set_secondary_action("🔄 Refresh", () => load_actions(page), "fa fa-sync");

    page.add_inner_button("🤖 AI Assistant", () => frappe.set_route("kpi-ai-assistant"));
    page.add_inner_button("✍️ Data Entry", () => frappe.set_route("kpi-data-entry-page"));

    // 3-dot menu items
    page.add_menu_item("🔄 Refresh Alerts", () => load_actions(page));
    page.add_menu_item("🏢 Company Performance Overview", () => frappe.set_route("kpi-company-overview"));
    page.add_menu_item("🤖 AI Assistant", () => frappe.set_route("kpi-ai-assistant"));
    page.add_menu_item("✍️ Metric Data Entry", () => frappe.set_route("kpi-data-entry-page"));
    page.add_menu_item("📋 All Alert Logs", () => frappe.set_route("List", "KPI Alert"));
}

function load_actions(page) {
    page.main.html('<div class="text-center p-5"><i class="fa fa-spinner fa-spin fa-2x"></i><p class="mt-2 text-muted">Loading Action Center...</p></div>');

    frappe.xcall("productix.kpi_tracking.api.dashboard.get_action_center").then((data) => {
        render_actions(page, data);
    }).catch(() => {
        page.main.html(`
            <div style="max-width:960px;margin:30px auto;text-align:center;padding:40px;background:#fff;border:1px solid #e2e8f0;border-radius:12px;">
                <div style="font-size:36px;margin-bottom:12px;">🔔</div>
                <h4 style="font-weight:700;color:#0f172a;">Action Center Clear</h4>
                <p style="color:#64748b;font-size:13px;margin-bottom:20px;">No active alert items or missing submissions found.</p>
                <button class="btn btn-primary" onclick="frappe.set_route('kpi-company-overview')">🏢 Go to Dashboard</button>
            </div>
        `);
    });
}

function render_actions(page, data) {
    const alerts = data.alerts || [];
    const missing = data.missing_data || [];
    const critical_count = alerts.filter((a) => a.severity === "Critical").length;
    const warning_count = alerts.filter((a) => a.severity === "Warning").length;

    let alertsHtml = '';
    if (alerts.length > 0) {
        alertsHtml = `
            <div style="margin-bottom:24px;">
                <h5 style="font-weight:700;font-size:15px;color:#0f172a;margin-bottom:14px;">🚨 Active Performance Alerts (${alerts.length})</h5>
                <div style="display:flex;flex-direction:column;gap:10px;">
                    ${alerts.map(a => {
                        const isCrit = a.severity === 'Critical';
                        const isWarn = a.severity === 'Warning';
                        const isEscalation = a.alert_type === 'Employee Escalation';
                        const borderCol = isCrit ? '#ef4444' : (isEscalation ? '#6366f1' : '#f59e0b');
                        const badgeClass = isCrit ? 'badge-danger' : (isEscalation ? 'badge-primary' : 'badge-warning');
                        return `
                            <div class="card" style="border:1px solid #e2e8f0;border-left:4px solid ${borderCol};border-radius:10px;box-shadow:0 1px 3px rgba(0,0,0,0.03);">
                                <div class="card-body" style="padding:16px 20px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;">
                                    <div style="flex:1;min-width:260px;">
                                        <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;flex-wrap:wrap;">
                                            <span class="badge ${badgeClass}" style="font-size:11px;">${a.severity}</span>
                                            <strong style="font-size:14px;color:#0f172a;">${a.subject || a.alert_type}</strong>
                                            <span style="font-size:12px;color:#64748b;">· Department: <strong>${a.department || 'General'}</strong></span>
                                            ${a.sender_name ? `<span style="font-size:11px;color:#6366f1;background:#f5f3ff;padding:1px 6px;border-radius:4px;">From: ${a.sender_name} (${a.sender_role || 'Employee'})</span>` : ''}
                                        </div>
                                        <p style="margin:0 0 6px 0;font-size:13px;color:#334155;">${a.message}</p>
                                        <small style="color:#94a3b8;">Triggered: ${a.trigger_period || 'Recent'} | Status: <strong>${a.status}</strong></small>
                                    </div>
                                    <div style="display:flex;gap:8px;">
                                        ${a.status === 'Active' ? `<button class="btn btn-xs btn-default ack-btn" data-name="${a.name}" style="font-weight:600;">👁️ Acknowledge</button>` : ''}
                                        <button class="btn btn-xs btn-success resolve-btn" data-name="${a.name}" style="font-weight:600;">✅ Resolve</button>
                                    </div>
                                </div>
                            </div>
                        `;
                    }).join('')}
                </div>
            </div>
        `;
    }

    let missingHtml = '';
    if (missing.length > 0) {
        missingHtml = `
            <div style="margin-bottom:24px;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
                    <h5 style="font-weight:700;font-size:15px;color:#0f172a;margin:0;">⏳ Missing Metric Data Submissions (${missing.length})</h5>
                    <button class="btn btn-xs btn-primary" id="remind-all-missing-btn" style="font-weight:600;">
                        🔔 Send Reminder to All Pending Departments
                    </button>
                </div>
                <div style="display:flex;flex-direction:column;gap:10px;">
                    ${missing.map(m => `
                        <div class="card" style="border:1px solid #e2e8f0;border-left:4px solid #64748b;border-radius:10px;box-shadow:0 1px 3px rgba(0,0,0,0.03);">
                            <div class="card-body" style="padding:14px 20px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;">
                                <div>
                                    <span class="badge badge-secondary" style="font-size:11px;margin-right:6px;">Pending</span>
                                    <strong style="font-size:14px;color:#0f172a;">${m.kpi}</strong>
                                    <span style="font-size:12px;color:#64748b;margin-left:6px;">· Department: <strong>${m.department}</strong> (${m.frequency || 'Monthly'})</span>
                                    <div style="font-size:12px;color:#94a3b8;margin-top:2px;">No actual value logged for current reporting cycle.</div>
                                </div>
                                <div style="display:flex;gap:6px;">
                                    <button class="btn btn-xs btn-default send-dept-reminder-btn" data-dept="${m.department}" style="font-weight:600;">
                                        🔔 Remind Department
                                    </button>
                                    <button class="btn btn-xs btn-primary" onclick="frappe.set_route('kpi-data-entry-page', {department: '${m.department}'})" style="font-weight:600;">
                                        ✍️ Log Data
                                    </button>
                                </div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    let emptyHtml = '';
    if (alerts.length === 0 && missing.length === 0) {
        emptyHtml = `
            <div style="text-align:center;padding:50px 20px;background:#fff;border:1px solid #e2e8f0;border-radius:12px;box-shadow:0 1px 3px rgba(0,0,0,0.03);">
                <div style="font-size:42px;margin-bottom:12px;">🎉</div>
                <h4 style="font-weight:700;color:#0f172a;margin-bottom:6px;">All Operations Healthy</h4>
                <p style="color:#64748b;font-size:13px;max-width:440px;margin:0 auto 20px;">No critical deviations, alert notices, or missing data submissions recorded.</p>
                <button class="btn btn-sm btn-primary" onclick="frappe.set_route('kpi-company-overview')" style="font-weight:600;">🏢 Open Company Overview</button>
            </div>
        `;
    }

    let html = `
        <div style="max-width:1100px;margin:0 auto;padding:10px 0 40px;">
            <!-- Back button & Breadcrumb Navigation -->
            <div style="margin-bottom:14px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;">
                <div style="display:flex;align-items:center;gap:8px;">
                    <button class="btn btn-sm btn-default" onclick="frappe.set_route('company-tracking-system')" style="font-weight:600;color:#475569;" title="Return to Company Tracking Workspace">
                        <i class="fa fa-home mr-1"></i> Workspace Home
                    </button>
                    <button class="btn btn-sm btn-default" onclick="frappe.set_route('kpi-company-overview')" style="font-weight:600;color:#475569;">
                        <i class="fa fa-arrow-left mr-1"></i> Back to Overview
                    </button>
                </div>
                <div style="font-size:12px;color:#64748b;">
                    Admin Mode · Authenticated as <strong>${page._ctx.full_name || 'Admin'}</strong>
                </div>
            </div>

            <!-- Hero Header Banner -->
            <div style="background:linear-gradient(135deg, #1e293b 0%, #334155 60%, #475569 100%);border-radius:12px;padding:26px 30px;color:#fff;margin-bottom:24px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:18px;">
                <div>
                    <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
                        <span style="background:rgba(56,189,248,0.2);color:#38bdf8;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700;letter-spacing:0.5px;text-transform:uppercase;">
                            🚨 Operations Center
                        </span>
                        <span class="productix-status-pulse"></span>
                    </div>
                    <h1 style="margin:0 0 6px 0;font-size:22px;font-weight:700;color:#fff;">
                        <span>Performance Action &amp; Alert Center</span>
                    </h1>
                    <p style="margin:0;font-size:13px;color:#94a3b8;">
                        Manage critical metric deviations, acknowledge triggers, and send department reminders.
                    </p>
                </div>
                <div>
                    <button class="btn btn-sm btn-default" onclick="frappe.set_route('List', 'KPI Alert')" style="color:#fff;background:rgba(255,255,255,0.15);border:1px solid rgba(255,255,255,0.25);">
                        📋 All Alert Logs
                    </button>
                </div>
            </div>

            <!-- Summary Status Cards -->
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:24px;">
                <div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:14px 18px;text-align:center;">
                    <div style="font-size:24px;font-weight:800;color:${critical_count > 0 ? '#ef4444' : '#10b981'};">${critical_count}</div>
                    <div style="font-size:11px;text-transform:uppercase;color:#64748b;font-weight:600;margin-top:2px;">Critical Alerts</div>
                </div>
                <div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:14px 18px;text-align:center;">
                    <div style="font-size:24px;font-weight:800;color:${warning_count > 0 ? '#f59e0b' : '#10b981'};">${warning_count}</div>
                    <div style="font-size:11px;text-transform:uppercase;color:#64748b;font-weight:600;margin-top:2px;">Warnings</div>
                </div>
                <div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:14px 18px;text-align:center;">
                    <div style="font-size:24px;font-weight:800;color:#64748b;">${missing.length}</div>
                    <div style="font-size:11px;text-transform:uppercase;color:#64748b;font-weight:600;margin-top:2px;">Missing Submissions</div>
                </div>
                <div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:14px 18px;text-align:center;">
                    <div style="font-size:24px;font-weight:800;color:#0f172a;">${data.total_items || 0}</div>
                    <div style="font-size:11px;text-transform:uppercase;color:#64748b;font-weight:600;margin-top:2px;">Total Action Items</div>
                </div>
            </div>

            ${alertsHtml}
            ${missingHtml}
            ${emptyHtml}
        </div>
    `;

    page.main.html(html);

    // Acknowledge Button
    page.main.find(".ack-btn").on("click", function () {
        const name = $(this).data("name");
        frappe.xcall("frappe.client.set_value", {
            doctype: "KPI Alert", name: name, fieldname: "status", value: "Acknowledged",
        }).then(() => {
            frappe.show_alert({ message: "Alert acknowledged", indicator: "blue" });
            load_actions(page);
        });
    });

    // Resolve Button
    page.main.find(".resolve-btn").on("click", function () {
        const name = $(this).data("name");
        frappe.xcall("frappe.client.set_value", {
            doctype: "KPI Alert", name: name, fieldname: "status", value: "Resolved",
        }).then(() => {
            frappe.show_alert({ message: "✅ Alert marked as Resolved", indicator: "green" });
            load_actions(page);
        });
    });

    // Remind department button
    page.main.find(".send-dept-reminder-btn").on("click", function () {
        const dept = $(this).data("dept");
        const btn = $(this);
        btn.prop("disabled", true).html('<i class="fa fa-spinner fa-spin"></i>');

        frappe.xcall("productix.kpi_tracking.services.alert_engine.send_missing_data_reminders", {
            department: dept,
        }).then((res) => {
            frappe.show_alert({ message: `✅ Reminder sent to employees of ${dept}`, indicator: "green" });
            btn.prop("disabled", false).html("✅ Reminded");
        }).catch((err) => {
            btn.prop("disabled", false).html("🔔 Remind Department");
            frappe.show_alert({ message: "Error sending reminder: " + (err.message || ""), indicator: "red" });
        });
    });

    // Remind all missing button
    page.main.find("#remind-all-missing-btn").on("click", function () {
        frappe.confirm("Send notifications to all employees in departments with missing entries?", function () {
            frappe.xcall("productix.kpi_tracking.services.alert_engine.send_missing_data_reminders").then((res) => {
                frappe.show_alert({ message: `✅ Reminders sent to ${res.notifications_sent} employee(s).`, indicator: "green" });
            });
        });
    });
}
