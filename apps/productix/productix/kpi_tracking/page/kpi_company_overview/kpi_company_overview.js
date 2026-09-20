// Productix KPI Tracking — Enterprise Performance Overview Page (Admin)

window.productix_charts = window.productix_charts || {};

function destroy_chart(chart_ref) {
    if (!chart_ref) return;
    if (typeof chart_ref === "object" && chart_ref.destroy) {
        try {
            chart_ref.destroy();
        } catch (e) {}
        return;
    }
    if (typeof chart_ref === "string" && window.productix_charts && window.productix_charts[chart_ref]) {
        try {
            if (window.productix_charts[chart_ref].destroy) {
                window.productix_charts[chart_ref].destroy();
            }
        } catch (e) {}
        window.productix_charts[chart_ref] = null;
    }
}

frappe.pages["kpi-company-overview"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "Company Tracking System",
        single_column: true,
    });

    page.main.addClass("kpi-tracking-app");
    page._timeframe = "6_months";
    page._horizon = "next_month";
    page._frequency = "Monthly";
    page._period = null;

    frappe.xcall("productix.kpi_tracking.api.dashboard.get_user_context").then((ctx) => {
        page._ctx = ctx || {};
        page._frequency = (ctx && ctx.default_frequency) || "Daily";
        if (!ctx.is_admin) {
            frappe.show_alert({ message: "Company Overview is restricted to administrators.", indicator: "orange" });
            frappe.set_route("kpi-department-dashboard", { department: ctx.assigned_department });
            return;
        }
        setup_page_actions(page);
        load_dashboard(page);
    }).catch(() => {
        frappe.set_route("kpi-department-dashboard");
    });
};

function setup_page_actions(page) {
    page.set_primary_action("📊 Data Entry Monitoring", () => show_monitoring_modal(page), "fa fa-chart-bar");
    page.set_secondary_action("🔄 Refresh", () => load_dashboard(page), "fa fa-sync");

    page.add_inner_button("👥 User Management", () => show_user_management_modal(page));
    page.add_inner_button("🤖 AI Assistant", () => frappe.set_route("kpi-ai-assistant"));
    page.add_inner_button("🚨 Action Center", () => frappe.set_route("kpi-action-center"));
    page.add_inner_button("✍️ Data Entry", () => frappe.set_route("kpi-data-entry-page"));

    // Populate standard 3-dot dropdown menu
    page.add_menu_item("🔄 Refresh Dashboard", () => load_dashboard(page));
    page.add_menu_item("📊 Data Entry Monitoring", () => show_monitoring_modal(page));
    page.add_menu_item("👥 User & Role Management", () => show_user_management_modal(page));
    page.add_menu_item("🤖 AI Assistant", () => frappe.set_route("kpi-ai-assistant"));
    page.add_menu_item("🚨 Action & Alert Center", () => frappe.set_route("kpi-action-center"));
    page.add_menu_item("✍️ Metric Data Entry", () => frappe.set_route("kpi-data-entry-page"));
    page.add_menu_item("📐 Formula Builder", () => frappe.set_route("kpi-formula-builder"));
    page.add_menu_item("⚡ Performance Setup Wizard", () => frappe.set_route("kpi-setup-wizard"));
    page.add_menu_item("⚙️ Settings", () => frappe.set_route("Form", "KPI Settings"));
}

function load_dashboard(page) {
    page.main.html('<div class="text-center p-5"><i class="fa fa-spinner fa-spin fa-2x"></i><p class="mt-2 text-muted">Loading Company Performance Overview...</p></div>');

    frappe.xcall("productix.kpi_tracking.api.dashboard.get_company_overview", {
        timeframe: page._timeframe || "6_months",
        horizon: page._horizon || "next_month",
        frequency: page._frequency || "Monthly",
        period: page._period,
    }).then((data) => {
        render_dashboard(page, data);
    }).catch((err) => {
        page.main.html(`
            <div style="max-width:960px;margin:30px auto;text-align:center;padding:40px;background:#fff;border:1px solid #e2e8f0;border-radius:12px;">
                <div style="font-size:36px;margin-bottom:12px;">🏢</div>
                <h4 style="font-weight:700;color:#0f172a;">Company Performance Setup</h4>
                <p style="color:#64748b;font-size:13px;max-width:480px;margin:0 auto 20px;">Initialize company metrics and departments using the 1-Click Setup Wizard.</p>
                <button class="btn btn-primary" onclick="frappe.set_route('kpi-setup-wizard')" style="font-weight:600;">⚡ Open Setup Wizard</button>
            </div>
        `);
    });
}

function render_dashboard(page, data) {
    if (!data) data = {};
    const score = data.score != null ? data.score : "--";
    const scoreVal = parseFloat(data.score) || 0;
    const scoreClass = scoreVal >= 80 ? "on-track" : scoreVal >= 60 ? "warning" : data.score != null ? "critical" : "missing";
    const alerts = data.alerts_summary || {};
    const depts = data.departments || [];
    const history = data.history || [];
    const growth = data.growth;
    const trend = data.trend || "Stable";
    const trendIcon = trend === "Improving" ? "📈" : (trend === "Declining" ? "📉" : "➖");
    const predObj = data.selected_prediction || {};

    let growthStr = "--";
    let growthBadgeClass = "badge-secondary";
    if (growth != null) {
        growthStr = (growth > 0 ? "+" : "") + growth + "%";
        growthBadgeClass = growth > 0 ? "badge-success" : (growth < 0 ? "badge-danger" : "badge-secondary");
    }

    let deptCardsHtml = '';
    if (depts.length > 0) {
        deptCardsHtml = depts.map(dept => {
            const ds = dept.score != null ? dept.score + "%" : "--";
            const dc = (dept.score || 0) >= 80 ? "on-track" : (dept.score || 0) >= 60 ? "warning" : dept.score != null ? "critical" : "missing";
            return `
                <div class="kpi-tracking-dept-card kpi-tracking-dept-card--${dc}" onclick="frappe.set_route('kpi-department-dashboard', {department: '${dept.department_code}'})" style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:18px;cursor:pointer;box-shadow:0 1px 3px rgba(0,0,0,0.04);transition:all 0.2s;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                        <strong style="font-size:15px;color:#0f172a;">${dept.department}</strong>
                        <span class="kpi-tracking-status-badge kpi-tracking-status-badge--${dc}" style="font-size:12px;font-weight:700;">${ds}</span>
                    </div>
                    <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px;">
                        <span class="kpi-tracking-status-badge kpi-tracking-status-badge--on-track">${dept.on_track || 0} On Track</span>
                        <span class="kpi-tracking-status-badge kpi-tracking-status-badge--warning">${dept.warning || 0} Warning</span>
                        <span class="kpi-tracking-status-badge kpi-tracking-status-badge--critical">${dept.critical || 0} Critical</span>
                        <span class="kpi-tracking-status-badge kpi-tracking-status-badge--missing">${dept.missing || 0} Pending</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;align-items:center;font-size:12px;color:#94a3b8;border-top:1px solid #f1f5f9;padding-top:10px;">
                        <span>📊 ${dept.total_kpis || 0} Total Metrics</span>
                        <span>⚖️ Weight: ${dept.weight || 1.0}</span>
                    </div>
                </div>
            `;
        }).join('');
    } else {
        deptCardsHtml = `
            <div style="grid-column:1/-1;text-align:center;padding:36px;background:#fff;border:1px dashed #cbd5e1;border-radius:10px;">
                <div style="font-size:32px;margin-bottom:8px;">🏭</div>
                <div style="font-weight:600;color:#334155;margin-bottom:4px;">No Operational Departments Configured</div>
                <div style="font-size:12px;color:#94a3b8;margin-bottom:14px;">Run the Setup Wizard to initialize standard departments and metrics.</div>
                <button class="btn btn-xs btn-primary" onclick="frappe.set_route('kpi-setup-wizard')">⚡ Open Setup Wizard</button>
            </div>
        `;
    }

    let html = `
        <div style="max-width:1150px;margin:0 auto;padding:10px 0 40px;">
            <!-- Back button & Breadcrumb Navigation -->
            <div style="margin-bottom:14px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;">
                <div>
                    <button class="btn btn-sm btn-default" onclick="frappe.set_route('company-tracking-system')" style="font-weight:600;color:#475569;" title="Return to Company Tracking Workspace">
                        <i class="fa fa-home mr-1"></i> Workspace Home
                    </button>
                </div>
                <div style="font-size:12px;color:#64748b;">
                    Role: <span class="badge badge-primary" style="font-size:11px;">Admin</span> · <strong>${(page._ctx && page._ctx.full_name) || 'Admin'}</strong>
                </div>
            </div>

            <!-- Hero Header Banner with Company Score & Growth -->
            <div style="background:linear-gradient(135deg, #1e293b 0%, #334155 60%, #475569 100%);border-radius:12px;padding:26px 30px;color:#fff;margin-bottom:20px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:18px;">
                <div>
                    <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
                        <span style="background:rgba(56,189,248,0.2);color:#38bdf8;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700;letter-spacing:0.5px;text-transform:uppercase;">
                            🏢 Company Tracking System
                        </span>
                        <span class="productix-status-pulse"></span>
                    </div>
                    <h1 style="margin:0 0 6px 0;font-size:22px;font-weight:700;color:#fff;">
                        <span>📊 Enterprise Performance Overview</span>
                    </h1>
                    <p style="margin:0;font-size:13px;color:#94a3b8;">
                        Aggregated departmental health index, real-time trend trajectory, and AI predictive forecasting.
                    </p>
                </div>
                <div style="display:flex;gap:14px;align-items:center;flex-wrap:wrap;">
                    <div style="background:rgba(255,255,255,0.1);border:1px solid rgba(255,255,255,0.2);border-radius:10px;padding:12px 20px;text-align:center;backdrop-filter:blur(4px);">
                        <div style="font-size:32px;font-weight:800;color:#38bdf8;line-height:1;">${score != "--" ? score + "%" : "--"}</div>
                        <div style="font-size:11px;text-transform:uppercase;color:#94a3b8;font-weight:600;margin-top:4px;">Current Index</div>
                    </div>
                    <div style="background:rgba(255,255,255,0.1);border:1px solid rgba(255,255,255,0.2);border-radius:10px;padding:12px 18px;text-align:center;backdrop-filter:blur(4px);">
                        <div style="font-size:20px;font-weight:800;color:#10b981;line-height:1;">${growthStr}</div>
                        <div style="font-size:11px;text-transform:uppercase;color:#94a3b8;font-weight:600;margin-top:4px;">Period Growth</div>
                    </div>
                </div>
            </div>

            <!-- Dynamic Synchronized Filter Bar -->
            <div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:14px 20px;margin-bottom:20px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:14px;">
                <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
                    <label style="margin:0;font-size:12px;font-weight:700;color:#475569;">🔄 Frequency Filter:</label>
                    <div class="btn-group btn-group-sm" id="freq-buttons">
                        <button class="btn ${page._frequency === 'Daily' ? 'btn-primary' : 'btn-default'}" data-freq="Daily">Daily</button>
                        <button class="btn ${page._frequency === 'Weekly' ? 'btn-primary' : 'btn-default'}" data-freq="Weekly">Weekly</button>
                        <button class="btn ${page._frequency === 'Monthly' ? 'btn-primary' : 'btn-default'}" data-freq="Monthly">Monthly</button>
                        <button class="btn ${page._frequency === 'All' ? 'btn-primary' : 'btn-default'}" data-freq="All">All Frequencies</button>
                    </div>
                </div>

                <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
                    <label style="margin:0;font-size:12px;font-weight:700;color:#475569;">📅 Historical Range:</label>
                    <div class="btn-group btn-group-sm" id="timeframe-buttons">
                        <button class="btn ${page._timeframe === 'today' ? 'btn-primary' : 'btn-default'}" data-tf="today">Recent</button>
                        <button class="btn ${page._timeframe === 'last_week' ? 'btn-primary' : 'btn-default'}" data-tf="last_week">Last Week</button>
                        <button class="btn ${page._timeframe === 'last_month' ? 'btn-primary' : 'btn-default'}" data-tf="last_month">Last Month</button>
                        <button class="btn ${page._timeframe === '6_months' ? 'btn-primary' : 'btn-default'}" data-tf="6_months">6 Months</button>
                        <button class="btn ${page._timeframe === 'overall' ? 'btn-primary' : 'btn-default'}" data-tf="overall">All Time</button>
                    </div>
                </div>

                <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
                    <label style="margin:0;font-size:12px;font-weight:700;color:#475569;">🔮 Forecast:</label>
                    <div class="btn-group btn-group-sm" id="horizon-buttons">
                        <button class="btn ${page._horizon === 'tomorrow' ? 'btn-info' : 'btn-default'}" data-hz="tomorrow">Tomorrow</button>
                        <button class="btn ${page._horizon === 'next_week' ? 'btn-info' : 'btn-default'}" data-hz="next_week">Next Week</button>
                        <button class="btn ${page._horizon === 'next_month' ? 'btn-info' : 'btn-default'}" data-hz="next_month">Next Month</button>
                        <button class="btn ${page._horizon === 'next_quarter' ? 'btn-info' : 'btn-default'}" data-hz="next_quarter">Next Quarter</button>
                    </div>
                </div>
            </div>

            <!-- Executive Metric Intelligence Cards Row -->
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin-bottom:20px;">
                <div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px 20px;box-shadow:0 1px 3px rgba(0,0,0,0.03);">
                    <div style="display:flex;justify-content:space-between;color:#64748b;font-size:12px;font-weight:700;">
                        <span>Company Trajectory</span>
                        <span>${trendIcon}</span>
                    </div>
                    <div style="font-size:22px;font-weight:800;color:#0f172a;margin-top:6px;">
                        <span>${trend}</span>
                        <span class="badge ${growthBadgeClass}" style="font-size:12px;margin-left:6px;">${growthStr}</span>
                    </div>
                    <div style="font-size:11px;color:#94a3b8;margin-top:4px;">Slope: +${data.relative_slope || 0}% per cycle</div>
                </div>

                <div style="background:#fff;border:1px solid #e2e8f0;border-left:4px solid #6366f1;border-radius:10px;padding:16px 20px;box-shadow:0 1px 3px rgba(0,0,0,0.03);">
                    <div style="display:flex;justify-content:space-between;color:#64748b;font-size:12px;font-weight:700;">
                        <span>${predObj.horizon || 'Next Month'} Forecast</span>
                        <span>🔮</span>
                    </div>
                    <div style="font-size:22px;font-weight:800;color:#4f46e5;margin-top:6px;">
                        ${predObj.predicted_score != null ? predObj.predicted_score + "%" : "--"}
                    </div>
                    <div style="font-size:11px;color:#64748b;margin-top:4px;">
                        Confidence: <strong>${predObj.confidence || 95}% (R² Regression)</strong>
                    </div>
                </div>

                <div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px 20px;box-shadow:0 1px 3px rgba(0,0,0,0.03);">
                    <div style="display:flex;justify-content:space-between;color:#64748b;font-size:12px;font-weight:700;">
                        <span>Departments &amp; Metrics</span>
                        <span>🏭</span>
                    </div>
                    <div style="font-size:22px;font-weight:800;color:#0f172a;margin-top:6px;">
                        ${data.total_departments || depts.length} <span style="font-size:13px;color:#64748b;font-weight:500;">Depts · ${data.total_kpis || 0} Metrics</span>
                    </div>
                    <div style="font-size:11px;color:#94a3b8;margin-top:4px;">
                        🚨 Active Alerts: <strong style="color:${(alerts.Critical || 0) > 0 ? '#ef4444' : '#10b981'};">${(alerts.Critical || 0) + (alerts.Warning || 0)}</strong>
                    </div>
                </div>
            </div>

            <!-- Charts Section -->
            <div class="row" style="margin-bottom:24px;">
                <div class="col-md-6 col-sm-12 mb-3">
                    <div class="card" style="border:1px solid #e2e8f0;border-radius:10px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,0.04);height:100%;">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                            <h5 style="margin:0;font-size:14px;font-weight:700;color:#0f172a;">📈 Company Score Timeline &amp; Trend</h5>
                            <span class="badge badge-primary" style="font-size:11px;">Timeline %</span>
                        </div>
                        <div id="company-trend-line-chart" style="height:240px;"></div>
                    </div>
                </div>

                <div class="col-md-6 col-sm-12 mb-3">
                    <div class="card" style="border:1px solid #e2e8f0;border-radius:10px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,0.04);height:100%;">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                            <h5 style="margin:0;font-size:14px;font-weight:700;color:#0f172a;">📊 Departmental Performance Index</h5>
                            <span class="badge badge-info" style="font-size:11px;">Department %</span>
                        </div>
                        <div id="kpi-dept-chart" style="height:240px;"></div>
                    </div>
                </div>
            </div>

            <!-- Department Breakdown Grid Section -->
            <div style="margin-bottom:24px;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
                    <h4 style="margin:0;font-size:16px;font-weight:700;color:#0f172a;">🏭 Operational Departments (${depts.length})</h4>
                    <span style="font-size:12px;color:#64748b;">Click any department card to inspect individual metrics</span>
                </div>
                <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px;">
                    ${deptCardsHtml}
                </div>
            </div>
        </div>
    `;

    page.main.html(html);

    // Event Handlers: Frequency filter
    page.main.find("#freq-buttons button").on("click", function () {
        page._frequency = $(this).data("freq");
        load_dashboard(page);
    });

    // Event Handlers: Timeframe Filter Buttons
    page.main.find("#timeframe-buttons button").on("click", function () {
        page._timeframe = $(this).data("tf");
        load_dashboard(page);
    });

    // Event Handlers: Prediction Horizon Filter Buttons
    page.main.find("#horizon-buttons button").on("click", function () {
        page._horizon = $(this).data("hz");
        load_dashboard(page);
    });

    // Render Charts with lifecycle management
    setTimeout(() => {
        const trendEl = page.main.find("#company-trend-line-chart");
        if (trendEl.length) {
            destroy_chart("#company-trend-line-chart");
            trendEl.empty();
            if (history.length > 0 && typeof frappe.Chart !== "undefined") {
                const historyLabels = history.map(h => h.period);
                const historyValues = history.map(h => h.score);

                if (predObj && predObj.predicted_score != null) {
                    historyLabels.push(`(${predObj.horizon || 'Forecast'})`);
                    historyValues.push(predObj.predicted_score);
                }

                window.productix_charts["#company-trend-line-chart"] = new frappe.Chart(trendEl[0], {
                    data: {
                        labels: historyLabels,
                        datasets: [
                            { name: "Company Score (%)", values: historyValues, chartType: "line" }
                        ]
                    },
                    type: "line",
                    height: 220,
                    colors: ["#2563eb"],
                    lineOptions: { regionFill: 1, hideDots: 0, dotSize: 5 }
                });
            } else {
                trendEl.html('<div class="text-center p-4 text-muted" style="font-size:12px;">No historical company trend data points recorded yet.</div>');
            }
        }

        const deptEl = page.main.find("#kpi-dept-chart");
        if (deptEl.length) {
            destroy_chart("#kpi-dept-chart");
            deptEl.empty();
            if (depts.length > 0 && typeof frappe.Chart !== "undefined") {
                const deptLabels = depts.map(d => d.department);
                const deptValues = depts.map(d => d.score || 0);

                window.productix_charts["#kpi-dept-chart"] = new frappe.Chart(deptEl[0], {
                    data: {
                        labels: deptLabels,
                        datasets: [
                            { name: "Department Score (%)", values: deptValues }
                        ]
                    },
                    type: "bar",
                    height: 220,
                    colors: ["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#06b6d4"]
                });
            } else {
                deptEl.html('<div class="text-center p-4 text-muted" style="font-size:12px;">No department scores available yet.</div>');
            }
        }
    }, 150);
}

function show_monitoring_modal(page) {
    if (page._monitoring_dialog) {
        try {
            page._monitoring_dialog.hide();
            if (page._monitoring_dialog.$wrapper) {
                page._monitoring_dialog.$wrapper.remove();
            }
        } catch (e) {}
        page._monitoring_dialog = null;
    }

    const d = new frappe.ui.Dialog({
        title: "📊 Department Data-Entry Monitoring & Completion Status",
        size: "extra-large",
        fields: [{ fieldtype: "HTML", fieldname: "monitoring_html" }],
        primary_action_label: "🔔 Send Missing Data Reminders to All",
        primary_action: function () {
            frappe.confirm(
                "Send notifications to all active employees belonging to departments with missing data entries?",
                function () {
                    frappe.xcall("productix.kpi_tracking.services.alert_engine.send_missing_data_reminders", {
                        frequency: page._frequency || "Monthly",
                    }).then((res) => {
                        frappe.show_alert({ message: `✅ Dispatched ${res.notifications_sent} notification(s) across ${res.departments_notified.length} department(s).`, indicator: "green" });
                        d.hide();
                    });
                }
            );
        }
    });
    page._monitoring_dialog = d;

    d.onhide = function () {
        setTimeout(() => {
            if (d.$wrapper) {
                d.$wrapper.remove();
            }
            $(".modal-backdrop").remove();
        }, 100);
        page._monitoring_dialog = null;
    };

    d.fields_dict.monitoring_html.$wrapper.html('<div class="text-center p-4"><i class="fa fa-spinner fa-spin"></i> Loading monitoring records...</div>');
    d.show();

    frappe.xcall("productix.kpi_tracking.api.dashboard.get_company_overview", {
        timeframe: page._timeframe || "6_months",
        horizon: page._horizon || "next_month",
        frequency: page._frequency || "Monthly",
        period: page._period,
    }).then((res) => {
        if (!res) res = {};
        const rawMonitoring = res.data_entry_monitoring || {};
        const summary = rawMonitoring.summary || {};
        const deptsFromMonitoring = rawMonitoring.departments || [];

        // Build list of departments with resilient fallbacks
        const depts = (deptsFromMonitoring.length > 0)
            ? deptsFromMonitoring
            : (res.departments || []).map(d => {
                const req = d.total_kpis || 0;
                const miss = d.missing || 0;
                const comp = Math.max(0, req - miss);
                const compPct = req > 0 ? Math.round((comp / req) * 100) : 0;
                return {
                    department: d.department || d.department_code,
                    department_code: d.department_code || d.name,
                    required_entries: req,
                    completed_entries: comp,
                    missing_entries: miss,
                    completion_percentage: compPct,
                    last_entry_date: '--',
                    last_entered_by: '--',
                    assigned_employees: [],
                    period: page._period || page._frequency || 'Current Period',
                    frequency: page._frequency || 'Monthly',
                };
            });

        const totalReq = (summary.total_required != null) ? summary.total_required : depts.reduce((s, d) => s + (d.required_entries || 0), 0);
        const totalComp = (summary.total_completed != null) ? summary.total_completed : depts.reduce((s, d) => s + (d.completed_entries || 0), 0);
        const totalMiss = (summary.total_missing != null) ? summary.total_missing : depts.reduce((s, d) => s + (d.missing_entries || 0), 0);
        const overallPct = (summary.overall_completion_percentage != null) ? summary.overall_completion_percentage : (totalReq > 0 ? Math.round((totalComp / totalReq) * 100) : 0);
        const periodStr = summary.period || page._period || 'Current Cycle';
        const freqStr = summary.frequency || page._frequency || 'Monthly';

        let rowsHtml = depts.map(dept => {
            const req = dept.required_entries || 0;
            const comp = dept.completed_entries || 0;
            const miss = dept.missing_entries != null ? dept.missing_entries : Math.max(0, req - comp);
            const compPct = dept.completion_percentage != null ? dept.completion_percentage : (req > 0 ? Math.round((comp / req) * 100) : 0);
            const isDone = miss === 0 && req > 0;
            const statusBadge = isDone
                ? '<span class="badge badge-success" style="font-size:11px;">Complete</span>'
                : req === 0
                    ? '<span class="badge badge-secondary" style="font-size:11px;">No Metrics</span>'
                    : `<span class="badge badge-warning" style="font-size:11px;">${miss} Missing</span>`;

            const assignees = (dept.assigned_employees && dept.assigned_employees.length > 0)
                ? dept.assigned_employees.join(', ')
                : '<span style="color:#94a3b8;font-style:italic;">No active employee</span>';

            return `
                <tr>
                    <td><strong>${dept.department}</strong></td>
                    <td class="text-center font-weight-bold">${req}</td>
                    <td class="text-center text-success font-weight-bold">${comp}</td>
                    <td class="text-center text-danger font-weight-bold">${miss}</td>
                    <td class="text-center">
                        <div style="display:flex;align-items:center;gap:6px;">
                            <div class="progress" style="flex:1;height:8px;margin:0;">
                                <div class="progress-bar ${compPct >= 80 ? 'bg-success' : compPct >= 50 ? 'bg-warning' : 'bg-danger'}" style="width:${compPct}%;"></div>
                            </div>
                            <span style="font-size:11px;font-weight:700;">${compPct}%</span>
                        </div>
                    </td>
                    <td>${statusBadge}</td>
                    <td style="font-size:12px;">${dept.last_entry_date || '--'}</td>
                    <td style="font-size:12px;">${dept.last_entered_by || '--'}</td>
                    <td style="font-size:11px;max-width:180px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="${assignees}">${assignees}</td>
                    <td class="text-center">
                        ${!isDone && miss > 0 ? `
                            <button class="btn btn-xs btn-primary notify-dept-btn" data-dept="${dept.department_code}" data-deptname="${dept.department}" style="font-weight:600;">
                                🔔 Remind
                            </button>
                        ` : '<span style="color:#10b981;font-size:12px;">✅ Up to Date</span>'}
                    </td>
                </tr>
            `;
        }).join('');

        let content = `
            <div style="padding:4px 0;">
                <!-- Summary Metrics Top Bar -->
                <div class="row mb-3" style="text-align:center;">
                    <div class="col-3">
                        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:10px;">
                            <div style="font-size:11px;color:#64748b;text-transform:uppercase;font-weight:700;">Period</div>
                            <div style="font-size:16px;font-weight:800;color:#0f172a;">${periodStr} (${freqStr})</div>
                        </div>
                    </div>
                    <div class="col-3">
                        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:10px;">
                            <div style="font-size:11px;color:#64748b;text-transform:uppercase;font-weight:700;">Required Entries</div>
                            <div style="font-size:16px;font-weight:800;color:#0f172a;">${totalReq}</div>
                        </div>
                    </div>
                    <div class="col-3">
                        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:10px;">
                            <div style="font-size:11px;color:#64748b;text-transform:uppercase;font-weight:700;">Completed Submissions</div>
                            <div style="font-size:16px;font-weight:800;color:#10b981;">${totalComp} (${overallPct}%)</div>
                        </div>
                    </div>
                    <div class="col-3">
                        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:10px;">
                            <div style="font-size:11px;color:#64748b;text-transform:uppercase;font-weight:700;">Missing Entries</div>
                            <div style="font-size:16px;font-weight:800;color:#ef4444;">${totalMiss}</div>
                        </div>
                    </div>
                </div>

                <!-- Table -->
                <div class="table-responsive">
                    <table class="table table-bordered table-hover" style="font-size:13px;background:#fff;margin:0;">
                        <thead style="background:#f1f5f9;color:#0f172a;font-weight:700;">
                            <tr>
                                <th>Department</th>
                                <th class="text-center">Required</th>
                                <th class="text-center">Completed</th>
                                <th class="text-center">Missing</th>
                                <th style="width:140px;" class="text-center">Completion %</th>
                                <th>Status</th>
                                <th>Last Entry</th>
                                <th>Entered By</th>
                                <th>Assigned Employees</th>
                                <th class="text-center">Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${rowsHtml}
                        </tbody>
                    </table>
                </div>
            </div>
        `;

        d.fields_dict.monitoring_html.$wrapper.html(content);

        // Single department reminder button
        d.fields_dict.monitoring_html.$wrapper.find(".notify-dept-btn").on("click", function () {
            const btn = $(this);
            const deptCode = btn.data("dept");
            const deptName = btn.data("deptname");

            btn.prop("disabled", true).html('<i class="fa fa-spinner fa-spin"></i>');

            frappe.xcall("productix.kpi_tracking.services.alert_engine.send_missing_data_reminders", {
                department: deptCode,
                frequency: freqStr,
            }).then((res) => {
                frappe.show_alert({ message: `✅ Reminder sent to employees of ${deptName}`, indicator: "green" });
                btn.prop("disabled", false).html("✅ Sent");
            }).catch((err) => {
                btn.prop("disabled", false).html("🔔 Remind");
                frappe.show_alert({ message: "Error: " + (err.message || "Failed"), indicator: "red" });
            });
        });
    });
}

function show_user_management_modal(page) {
    if (page._user_mgmt_dialog) {
        try {
            page._user_mgmt_dialog.hide();
            if (page._user_mgmt_dialog.$wrapper) {
                page._user_mgmt_dialog.$wrapper.remove();
            }
        } catch (e) {}
        page._user_mgmt_dialog = null;
    }

    const d = new frappe.ui.Dialog({
        title: "👥 User & Role Management",
        size: "extra-large",
        fields: [{ fieldtype: "HTML", fieldname: "user_mgmt_html" }],
        primary_action_label: "➕ Create New User",
        primary_action: function () {
            show_edit_user_modal(null, page, () => show_user_management_modal(page));
        }
    });
    page._user_mgmt_dialog = d;

    d.onhide = function () {
        setTimeout(() => {
            if (d.$wrapper) {
                d.$wrapper.remove();
            }
            $(".modal-backdrop").remove();
        }, 100);
        page._user_mgmt_dialog = null;
    };

    d.fields_dict.user_mgmt_html.$wrapper.html('<div class="text-center p-4"><i class="fa fa-spinner fa-spin"></i> Loading users...</div>');
    d.show();

    frappe.xcall("productix.kpi_tracking.api.user_management.get_users").then((data) => {
        const users = (data && data.users) || [];

        let userRows = users.map(u => {
            const roleBadge = u.role === "Admin"
                ? '<span class="badge badge-primary" style="font-size:11px;padding:4px 8px;">Admin</span>'
                : '<span class="badge badge-info" style="font-size:11px;padding:4px 8px;">Employee</span>';

            const statusBadge = u.is_active
                ? '<span class="badge badge-success" style="font-size:11px;">Active</span>'
                : '<span class="badge badge-secondary" style="font-size:11px;">Inactive</span>';

            return `
                <tr>
                    <td><strong>${u.full_name}</strong><br><small class="text-muted">${u.email}</small></td>
                    <td>${roleBadge}</td>
                    <td><strong style="color:#0f172a;">${u.department_name || u.department || 'All Departments'}</strong></td>
                    <td>${statusBadge}</td>
                    <td style="font-size:12px;color:#64748b;">${u.last_login ? frappe.datetime.prettyDate(u.last_login) : 'Never'}</td>
                    <td class="text-right" style="white-space:nowrap;">
                        <button class="btn btn-xs btn-default edit-user-btn" data-user='${JSON.stringify(u)}' style="font-weight:600;margin-right:4px;">
                            ✏️ Edit
                        </button>
                        <button class="btn btn-xs ${u.is_active ? 'btn-default' : 'btn-success'} toggle-user-btn" data-user="${u.user}" data-active="${u.is_active}" style="font-weight:600;margin-right:4px;">
                            ${u.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                        <button class="btn btn-xs btn-danger delete-user-btn" data-user="${u.user}" data-name="${u.full_name}" style="font-weight:600;">
                            🗑️ Delete
                        </button>
                    </td>
                </tr>
            `;
        }).join('');

        let content = `
            <div style="padding:4px 0;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                    <span style="font-size:13px;color:#64748b;">Total Users: <strong>${users.length}</strong></span>
                </div>
                <div class="table-responsive">
                    <table class="table table-bordered table-hover" style="font-size:13px;background:#fff;margin:0;">
                        <thead style="background:#f1f5f9;color:#0f172a;font-weight:700;">
                            <tr>
                                <th>User</th>
                                <th>Role</th>
                                <th>Assigned Department</th>
                                <th>Status</th>
                                <th>Last Login</th>
                                <th class="text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${userRows || '<tr><td colspan="6" class="text-center text-muted p-3">No users found.</td></tr>'}
                        </tbody>
                    </table>
                </div>
            </div>
        `;

        d.fields_dict.user_mgmt_html.$wrapper.html(content);

        // Edit user button
        d.fields_dict.user_mgmt_html.$wrapper.find(".edit-user-btn").on("click", function () {
            const userObj = JSON.parse($(this).attr("data-user"));
            d.hide();
            show_edit_user_modal(userObj, page, () => show_user_management_modal(page));
        });

        // Toggle user status button
        d.fields_dict.user_mgmt_html.$wrapper.find(".toggle-user-btn").on("click", function () {
            const userEmail = $(this).data("user");
            const currentActive = $(this).data("active");
            const newActive = currentActive ? 0 : 1;

            frappe.xcall("productix.kpi_tracking.api.user_management.toggle_user_status", {
                user: userEmail,
                is_active: newActive,
            }).then(() => {
                frappe.show_alert({ message: `User ${newActive ? 'activated' : 'deactivated'} successfully`, indicator: "green" });
                d.hide();
                show_user_management_modal(page);
            });
        });

        // Delete user button
        d.fields_dict.user_mgmt_html.$wrapper.find(".delete-user-btn").on("click", function () {
            const userEmail = $(this).data("user");
            const userName = $(this).data("name");

            frappe.confirm(
                `Are you sure you want to delete user <b>${userName}</b> (${userEmail}) from the Company Tracking System? Historical data entries will remain preserved.`,
                function () {
                    frappe.xcall("productix.kpi_tracking.api.user_management.toggle_user_status", {
                        user: userEmail,
                        is_active: -1,
                    }).catch(() => {
                        return frappe.xcall("frappe.client.delete", {
                            doctype: "User",
                            name: userEmail,
                        });
                    }).then(() => {
                        frappe.show_alert({ message: `✅ User ${userName} deleted successfully!`, indicator: "green" });
                        d.hide();
                        show_user_management_modal(page);
                    }).catch((err) => {
                        frappe.show_alert({ message: "Error deleting user: " + (err.message || "Failed"), indicator: "red" });
                    });
                }
            );
        });
    });
}

function show_edit_user_modal(userObj, page, callback) {
    frappe.xcall("productix.kpi_tracking.api.user_management.get_users").then((data) => {
        const departments = data.departments || [];
        const isEdit = !!userObj;

        const d = new frappe.ui.Dialog({
            title: isEdit ? `✏️ Edit User — ${userObj.full_name}` : "➕ Create New User",
            size: "large",
            fields: [
                { fieldtype: "Data", fieldname: "full_name", label: "Full Name", reqd: 1, default: userObj ? userObj.full_name : "" },
                { fieldtype: "Data", fieldname: "email", label: "Email Address (Login ID)", reqd: 1, options: "Email", default: userObj ? userObj.email : "", read_only: isEdit ? 1 : 0 },
                { fieldtype: "Select", fieldname: "role", label: "Role", reqd: 1, options: "Employee\nAdmin", default: userObj ? userObj.role : "Employee" },
                { fieldtype: "Select", fieldname: "department", label: "Assigned Department (for Employee)", options: "\n" + departments.map(d => d.name).join('\n'), default: userObj ? userObj.department : (departments[0] ? departments[0].name : "") },
                { fieldtype: "Password", fieldname: "new_password", label: isEdit ? "Reset Password (leave empty to keep current)" : "Password", reqd: isEdit ? 0 : 1 },
                { fieldtype: "Check", fieldname: "is_active", label: "Active User", default: userObj ? userObj.is_active : 1 },
            ],
            primary_action_label: isEdit ? "Save Changes" : "Create User",
            primary_action: function (values) {
                if (values.role === "Employee" && !values.department) {
                    frappe.msgprint("Please select an assigned department for the Employee role.");
                    return;
                }

                frappe.xcall("productix.kpi_tracking.api.user_management.save_user", {
                    user_id: userObj ? userObj.user : null,
                    email: values.email,
                    full_name: values.full_name,
                    role: values.role,
                    department: values.department,
                    new_password: values.new_password,
                    is_active: values.is_active,
                }).then((res) => {
                    frappe.show_alert({ message: `✅ User ${values.full_name} saved successfully!`, indicator: "green" });
                    d.hide();
                    if (callback) callback();
                }).catch((err) => {
                    frappe.show_alert({ message: "Error: " + (err.message || "Failed to save user"), indicator: "red" });
                });
            }
        });

        d.onhide = function () {
            setTimeout(() => {
                if (d.$wrapper) {
                    d.$wrapper.remove();
                }
                $(".modal-backdrop").remove();
            }, 100);
        };

        d.fields_dict.role.$input.on("change", function () {
            const role = $(this).val();
            if (role === "Admin") {
                d.set_df_property("department", "reqd", 0);
            } else {
                d.set_df_property("department", "reqd", 1);
            }
        });

        d.show();
    });
}
