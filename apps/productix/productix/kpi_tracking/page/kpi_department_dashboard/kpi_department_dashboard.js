// Productix KPI Tracking — Department Performance Dashboard
// Strict Employee View Isolation, Messaging & Escalation, High-Accuracy Analytics

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

frappe.pages["kpi-department-dashboard"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "Department Performance Dashboard",
        single_column: true,
    });

    page.main.addClass("kpi-tracking-app");
    page._timeframe = "6_months";
    page._horizon = "next_month";
    page._frequency = "Daily";
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
            targetDept = params.department;
            if (!targetDept) {
                targetDept = deptList.length > 0 ? deptList[0].name : "PRODUCTION";
            }
        } else {
            // Strict Employee Isolation: lock strictly to assigned department
            targetDept = ctx.assigned_department || (deptList.length > 0 ? deptList[0].name : null);
        }

        setup_department_page_actions(page);
        load_dept(page, targetDept);
    }).catch(() => {
        load_dept(page, "PRODUCTION");
    });
};

function setup_department_page_actions(page) {
    if (page.clear_inner_toolbar) page.clear_inner_toolbar();
    if (page.clear_menu) page.clear_menu();

    const isAdmin = page._ctx && page._ctx.is_admin;
    if (isAdmin) {
        page.set_primary_action("🏢 Company Overview", () => frappe.set_route("kpi-company-overview"), "fa fa-building");
        page.set_secondary_action("🔄 Refresh", () => load_dept(page), "fa fa-sync");

        page.add_inner_button("✍️ All Data Entry", () => frappe.set_route("kpi-data-entry-page"));
        page.add_inner_button("🤖 AI Assistant", () => frappe.set_route("kpi-ai-assistant"));
        page.add_inner_button("🚨 Action Center", () => frappe.set_route("kpi-action-center"));

        // 3-dot menu items for Admin
        page.add_menu_item("🔄 Refresh Department", () => load_dept(page));
        page.add_menu_item("🏢 Company Performance Overview", () => frappe.set_route("kpi-company-overview"));
        page.add_menu_item("✍️ Metric Data Entry", () => frappe.set_route("kpi-data-entry-page"));
        page.add_menu_item("🤖 AI Assistant", () => frappe.set_route("kpi-ai-assistant"));
        page.add_menu_item("🚨 Action & Alert Center", () => frappe.set_route("kpi-action-center"));
    } else {
        // Strict Employee View: ONLY department-level actions
        page.set_primary_action("✍️ Log Metric Data", () => {
            const target = $("#dept-data-entry-section");
            if (target.length) {
                $('html, body').animate({ scrollTop: target.offset().top - 80 }, 300);
            }
        }, "fa fa-edit");

        page.set_secondary_action("💬 Message Management", () => {
            const target = $("#dept-escalation-section");
            if (target.length) {
                $('html, body').animate({ scrollTop: target.offset().top - 80 }, 300);
            }
        }, "fa fa-paper-plane");

        // 3-dot menu items for Employee
        page.add_menu_item("🔄 Refresh Department Page", () => load_dept(page));
        page.add_menu_item("✍️ Log Metric Data", () => {
            const target = $("#dept-data-entry-section");
            if (target.length) {
                $('html, body').animate({ scrollTop: target.offset().top - 80 }, 300);
            }
        });
        page.add_menu_item("💬 Message Management / Escalation", () => {
            const target = $("#dept-escalation-section");
            if (target.length) {
                $('html, body').animate({ scrollTop: target.offset().top - 80 }, 300);
            }
        });
    }
}

function load_dept(page, dept) {
    const isAdmin = page._ctx && page._ctx.is_admin;
    if (!isAdmin && page._ctx && page._ctx.assigned_department) {
        dept = page._ctx.assigned_department;
    } else {
        dept = dept || page._selected_dept || (page._depts && page._depts[0] && page._depts[0].name) || "PRODUCTION";
    }
    page._selected_dept = dept;

    page.main.html('<div class="text-center p-5"><i class="fa fa-spinner fa-spin fa-2x"></i><p class="mt-2 text-muted">Loading Department Metrics...</p></div>');

    frappe.xcall("productix.kpi_tracking.api.dashboard.get_department_dashboard", {
        department: dept,
        timeframe: page._timeframe,
        horizon: page._horizon,
        frequency: page._frequency,
        period: page._period,
    }).then((data) => {
        render_dept(page, data, dept);
    }).catch((err) => {
        page.main.html(`
            <div style="max-width:960px;margin:30px auto;text-align:center;padding:40px;background:#fff;border:1px solid #e2e8f0;border-radius:12px;">
                <div style="font-size:36px;margin-bottom:12px;">⚠️</div>
                <h4 style="font-weight:700;color:#0f172a;">Department Unavailable</h4>
                <p style="color:#64748b;font-size:13px;max-width:480px;margin:0 auto 20px;">${err.message || 'You do not have access to this department.'}</p>
                ${isAdmin ? '<button class="btn btn-primary" onclick="frappe.set_route(\'kpi-company-overview\')" style="font-weight:600;">🏢 Back to Company Overview</button>' : ''}
            </div>
        `);
    });
}

function render_dept(page, data, dept) {
    const score = data.score != null ? data.score + "%" : "--";
    const deptName = data.department_name || dept;
    const depts = page._depts || [];
    const kpis = data.kpis || [];
    const isAdmin = page._ctx && page._ctx.is_admin;

    let deptControlHtml = '';
    if (isAdmin && depts.length > 1) {
        deptControlHtml = `
            <div style="display:flex;align-items:center;gap:10px;min-width:260px;">
                <label style="margin:0;font-size:13px;font-weight:700;color:#475569;">Switch Department:</label>
                <select id="dept-switcher-select" class="form-control form-control-sm" style="font-weight:600;max-width:220px;">
                    ${depts.map(d => `<option value="${d.name}" ${d.name === dept ? 'selected' : ''}>${d.department_name || d.name}</option>`).join('')}
                </select>
            </div>
        `;
    } else {
        deptControlHtml = `
            <div style="display:flex;align-items:center;gap:8px;">
                <span style="font-size:12px;font-weight:700;color:#475569;">Assigned Department:</span>
                <span class="badge badge-primary" style="font-size:13px;padding:5px 12px;background:#2563eb;">${deptName}</span>
            </div>
        `;
    }

    let kpiCardsHtml = '';
    if (kpis.length > 0) {
        kpiCardsHtml = kpis.map(kpi => {
            const status_class = (kpi.status || "missing").toLowerCase().replace(/[\/\s]+/g, "-");
            const trend_icon = kpi.trend === "Improving" ? "📈" : kpi.trend === "Declining" ? "📉" : "➖";
            const growth_str = kpi.growth != null ? (kpi.growth > 0 ? "+" : "") + kpi.growth + "%" : "--";
            const pred = kpi.prediction;
            const pred_str = pred ? `🔮 ${pred.horizon || 'Forecast'}: <strong>${pred.predicted_value} ${kpi.unit || ''}</strong> (${pred.confidence}% conf)` : "";
            const achPct = kpi.achievement != null ? Math.min(Math.round(kpi.achievement), 100) : 0;
            const achDisplay = kpi.achievement != null ? Math.round(kpi.achievement) + "%" : "--";

            return `
                <div class="kpi-tracking-kpi-card kpi-tracking-kpi-card--${status_class}" data-kpi="${kpi.kpi_code}" style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:18px;cursor:pointer;box-shadow:0 1px 3px rgba(0,0,0,0.04);transition:all 0.2s;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                        <strong style="font-size:14px;color:#0f172a;">${kpi.kpi}</strong>
                        <span class="kpi-tracking-status-badge kpi-tracking-status-badge--${status_class}" style="font-size:11px;font-weight:700;">${kpi.status || "Pending"}</span>
                    </div>

                    <div style="margin-bottom:12px;">
                        <div style="font-size:22px;font-weight:800;color:#0f172a;line-height:1.2;">
                            <span>${kpi.actual != null ? kpi.actual : "--"}</span>
                            <span style="font-size:13px;font-weight:500;color:#94a3b8;">/ Target: ${kpi.target != null ? kpi.target : "No Target"} ${kpi.unit || ""}</span>
                        </div>
                        <div style="background:#f1f5f9;border-radius:4px;height:6px;width:100%;margin-top:8px;overflow:hidden;">
                            <div style="background:${achPct >= 80 ? '#10b981' : achPct >= 60 ? '#f59e0b' : '#ef4444'};height:100%;width:${achPct}%;"></div>
                        </div>
                    </div>

                    <div style="display:flex;justify-content:space-between;font-size:11px;color:#64748b;margin-bottom:6px;">
                        <span>🎯 Ach: <strong>${achDisplay}</strong></span>
                        <span>📈 Growth: <strong>${growth_str}</strong></span>
                        <span>${trend_icon} ${kpi.trend || "Stable"}</span>
                    </div>

                    ${pred_str ? `<div style="font-size:11px;color:#4f46e5;background:#eef2ff;border:1px solid #e0e7ff;padding:6px 10px;border-radius:6px;margin-top:8px;">${pred_str}</div>` : ""}

                    <div style="border-top:1px solid #f1f5f9;margin-top:10px;padding-top:8px;display:flex;justify-content:space-between;font-size:11px;color:#94a3b8;">
                        <span>Frequency: <strong>${kpi.frequency || 'Monthly'}</strong></span>
                        <span style="color:#2563eb;font-weight:600;">View Trend Analysis →</span>
                    </div>
                </div>
            `;
        }).join('');
    } else {
        kpiCardsHtml = `
            <div style="grid-column:1/-1;text-align:center;padding:36px;background:#fff;border:1px dashed #cbd5e1;border-radius:10px;">
                <div style="font-size:32px;margin-bottom:8px;">📊</div>
                <div style="font-weight:600;color:#334155;margin-bottom:4px;">No KPIs Configured for ${deptName}</div>
                <div style="font-size:12px;color:#94a3b8;margin-bottom:14px;">Contact your administrator to configure KPI metrics for ${deptName}.</div>
            </div>
        `;
    }

    const deptHistory = data.history || [];
    const deptPred = data.predictions || {};
    const deptTrend = data.trend || "Stable";
    const deptGrowth = data.growth;
    let deptGrowthStr = "--";
    if (deptGrowth != null) {
        deptGrowthStr = (deptGrowth > 0 ? "+" : "") + deptGrowth + "%";
    }

    let trendSectionHtml = `
        <div class="row" style="margin-bottom:24px;">
            <div class="col-md-8 col-sm-12 mb-3">
                <div class="card" style="border:1px solid #e2e8f0;border-radius:10px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,0.04);background:#fff;height:100%;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                        <div>
                            <h5 style="margin:0;font-size:14px;font-weight:700;color:#0f172a;">📈 ${deptName} Historical Performance Trend</h5>
                            <span style="font-size:11px;color:#64748b;">Chronological aggregated department health index (0–100%)</span>
                        </div>
                        <span class="badge badge-primary" style="font-size:11px;">${deptTrend} Trajectory</span>
                    </div>
                    <div id="dept-trend-line-chart" style="height:220px;"></div>
                </div>
            </div>
            <div class="col-md-4 col-sm-12 mb-3">
                <div class="card" style="border:1px solid #e2e8f0;border-radius:10px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,0.04);background:#fff;height:100%;display:flex;flex-direction:column;justify-content:space-between;">
                    <div>
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                            <h5 style="margin:0;font-size:14px;font-weight:700;color:#0f172a;">🔮 Predictive Intelligence</h5>
                            <span class="badge ${deptPred.available ? 'badge-info' : 'badge-light'}" style="font-size:11px;">
                                ${deptPred.available ? 'OLS Model' : 'Notice'}
                            </span>
                        </div>
                        ${deptPred.available ? `
                            <div style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:8px;padding:14px;margin-bottom:12px;">
                                <div style="font-size:11px;color:#0369a1;font-weight:600;text-transform:uppercase;">${deptPred.horizon || 'Next Cycle'} Forecast</div>
                                <div style="font-size:26px;font-weight:800;color:#0284c7;margin:4px 0;">${deptPred.predicted_score != null ? deptPred.predicted_score + '%' : '--'}</div>
                                <div style="font-size:11px;color:#0369a1;">Target Period: <strong>${deptPred.target_period || 'Next Period'}</strong></div>
                                <div style="font-size:11px;color:#0369a1;margin-top:2px;">Confidence: <strong>${deptPred.confidence || 90}% (R² Regression)</strong></div>
                            </div>
                            <div style="font-size:12px;color:#64748b;">
                                Based on ${deptHistory.length} historical reporting cycles. Score is strictly normalized to [0, 100%].
                            </div>
                        ` : `
                            <div style="background:#f8fafc;border:1px dashed #cbd5e1;border-radius:8px;padding:20px;text-align:center;margin-bottom:12px;">
                                <div style="font-size:24px;margin-bottom:6px;">📊</div>
                                <div style="font-size:12px;font-weight:700;color:#475569;margin-bottom:4px;">Prediction Unavailable</div>
                                <div style="font-size:11px;color:#94a3b8;line-height:1.4;">
                                    ${deptPred.message || 'Requires at least 3 historical reporting periods to generate statistical linear regression predictions.'}
                                </div>
                            </div>
                        `}
                    </div>
                    <div style="border-top:1px solid #f1f5f9;padding-top:10px;display:flex;justify-content:space-between;font-size:11px;color:#64748b;">
                        <span>Historical Cycles: <strong>${deptHistory.length}</strong></span>
                        <span>Growth: <strong>${deptGrowthStr}</strong></span>
                    </div>
                </div>
            </div>
        </div>
    `;

    let alertsHtml = '';
    const alerts = data.alerts || [];
    if (alerts.length > 0) {
        alertsHtml = `
            <div style="margin-bottom:24px;">
                <h5 style="margin:0 0 12px 0;font-weight:700;font-size:14px;color:#0f172a;">🚨 Active Department Alerts</h5>
                <div style="display:flex;flex-direction:column;gap:8px;">
                    ${alerts.map(a => `
                        <div style="background:#fff;border:1px solid #e2e8f0;border-left:4px solid ${a.severity === 'Critical' ? '#ef4444' : '#f59e0b'};border-radius:8px;padding:12px 16px;display:flex;justify-content:space-between;align-items:center;">
                            <div>
                                <span class="badge ${a.severity === 'Critical' ? 'badge-danger' : 'badge-warning'}" style="margin-right:6px;">${a.severity}</span>
                                <strong style="color:#0f172a;font-size:13px;">${a.alert_type}</strong>: <span style="font-size:13px;color:#475569;">${a.message}</span>
                            </div>
                            <span style="font-size:11px;color:#94a3b8;">${a.trigger_period || ''}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    let html = `
        <div style="max-width:1150px;margin:0 auto;padding:10px 0 40px;">
            <!-- Back button & Breadcrumb Navigation (Isolated per role) -->
            <div style="margin-bottom:14px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;">
                <div style="display:flex;align-items:center;gap:8px;">
                    ${isAdmin ? `
                        <button class="btn btn-sm btn-default" id="dept-home-btn" style="font-weight:600;color:#475569;" title="Return to Company Tracking Workspace">
                            <i class="fa fa-home mr-1"></i> Workspace Home
                        </button>
                        <button class="btn btn-sm btn-default" id="dept-back-btn" style="font-weight:600;color:#475569;">
                            <i class="fa fa-arrow-left mr-1"></i> Back to Overview
                        </button>
                    ` : `
                        <div style="display:flex;align-items:center;gap:6px;">
                            <span class="badge badge-primary" style="font-size:12px;padding:5px 10px;background:#1e293b;">🏢 ${deptName} Station</span>
                        </div>
                    `}
                </div>
                <div style="font-size:12px;color:#64748b;">
                    Logged in as <strong>${page._ctx.full_name || 'User'}</strong> · Role: <span class="badge ${isAdmin ? 'badge-primary' : 'badge-info'}">${isAdmin ? 'Admin' : 'Employee'}</span>
                </div>
            </div>

            <!-- Hero Header Banner -->
            <div style="background:linear-gradient(135deg, #1e293b 0%, #334155 60%, #475569 100%);border-radius:12px;padding:26px 30px;color:#fff;margin-bottom:20px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:18px;">
                <div>
                    <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
                        <span style="background:rgba(56,189,248,0.2);color:#38bdf8;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700;letter-spacing:0.5px;text-transform:uppercase;">
                            🏭 Department Operations
                        </span>
                        <span class="productix-status-pulse"></span>
                    </div>
                    <h1 style="margin:0 0 6px 0;font-size:22px;font-weight:700;color:#fff;">
                        <span>${deptName} Performance Dashboard</span>
                    </h1>
                    <p style="margin:0;font-size:13px;color:#94a3b8;">
                        Real-time operational KPIs, achievement targets, and data submissions for ${deptName}.
                    </p>
                </div>
                <div style="display:flex;gap:16px;align-items:center;">
                    <div style="background:rgba(255,255,255,0.1);border:1px solid rgba(255,255,255,0.2);border-radius:10px;padding:12px 20px;text-align:center;backdrop-filter:blur(4px);">
                        <div style="font-size:32px;font-weight:800;color:#38bdf8;line-height:1;">${score}</div>
                        <div style="font-size:11px;text-transform:uppercase;color:#94a3b8;font-weight:600;margin-top:4px;">Dept Score</div>
                    </div>
                </div>
            </div>

            <!-- Dynamic Filter & Switcher Bar -->
            <div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:14px 20px;margin-bottom:20px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:14px;">
                ${deptControlHtml}

                <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
                    <label style="margin:0;font-size:12px;font-weight:700;color:#475569;">📅 Historical:</label>
                    <div class="btn-group btn-group-sm" id="dept-timeframe-buttons">
                        <button class="btn ${page._timeframe === 'today' ? 'btn-primary' : 'btn-default'}" data-tf="today">Recent</button>
                        <button class="btn ${page._timeframe === 'last_week' ? 'btn-primary' : 'btn-default'}" data-tf="last_week">Last Week</button>
                        <button class="btn ${page._timeframe === 'last_month' ? 'btn-primary' : 'btn-default'}" data-tf="last_month">Last Month</button>
                        <button class="btn ${page._timeframe === '6_months' ? 'btn-primary' : 'btn-default'}" data-tf="6_months">6 Months</button>
                    </div>
                </div>
            </div>

            <!-- Summary KPI Metric Row -->
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:20px;">
                <div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:14px 18px;text-align:center;">
                    <div style="font-size:22px;font-weight:800;color:#0f172a;">${data.total_kpis || 0}</div>
                    <div style="font-size:11px;text-transform:uppercase;color:#64748b;font-weight:600;margin-top:2px;">Total KPIs</div>
                </div>
                <div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:14px 18px;text-align:center;">
                    <div style="font-size:22px;font-weight:800;color:#10b981;">${data.on_track || 0}</div>
                    <div style="font-size:11px;text-transform:uppercase;color:#10b981;font-weight:600;margin-top:2px;">On Track</div>
                </div>
                <div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:14px 18px;text-align:center;">
                    <div style="font-size:22px;font-weight:800;color:#f59e0b;">${data.warning || 0}</div>
                    <div style="font-size:11px;text-transform:uppercase;color:#f59e0b;font-weight:600;margin-top:2px;">Warning</div>
                </div>
                <div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:14px 18px;text-align:center;">
                    <div style="font-size:22px;font-weight:800;color:#ef4444;">${data.critical || 0}</div>
                    <div style="font-size:11px;text-transform:uppercase;color:#ef4444;font-weight:600;margin-top:2px;">Critical</div>
                </div>
                <div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:14px 18px;text-align:center;">
                    <div style="font-size:22px;font-weight:800;color:#94a3b8;">${data.missing || 0}</div>
                    <div style="font-size:11px;text-transform:uppercase;color:#94a3b8;font-weight:600;margin-top:2px;">Pending / No Data</div>
                </div>
            </div>

            ${alertsHtml}

            ${trendSectionHtml}

            <!-- KPIs Grid -->
            <div style="margin-bottom:30px;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
                    <h4 style="margin:0;font-size:16px;font-weight:700;color:#0f172a;">📊 ${deptName} KPI Performance Metrics</h4>
                    <span style="font-size:12px;color:#64748b;">Click any card to inspect trends &amp; forecasts</span>
                </div>
                <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px;">
                    ${kpiCardsHtml}
                </div>
            </div>

            <!-- Embedded Department Data Entry Section -->
            <div id="dept-data-entry-section" style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:24px;margin-bottom:30px;box-shadow:0 1px 3px rgba(0,0,0,0.03);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;border-bottom:1px solid #f1f5f9;padding-bottom:12px;">
                    <div>
                        <h4 style="margin:0 0 4px 0;font-size:16px;font-weight:700;color:#0f172a;">✍️ ${deptName} Data Entry &amp; Submissions</h4>
                        <p style="margin:0;font-size:12px;color:#64748b;">Log operational metric results for the active period (${page._frequency}).</p>
                    </div>
                    <div id="dept-data-entry-progress" style="font-size:12px;font-weight:700;color:#2563eb;"></div>
                </div>
                <div id="dept-pending-kpis-list">
                    <div class="text-center p-3 text-muted"><i class="fa fa-spinner fa-spin mr-1"></i> Loading data entry fields...</div>
                </div>
            </div>

            <!-- Dedicated Employee-to-Admin Messaging & Operational Escalation Section -->
            <div id="dept-escalation-section" style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:24px;margin-bottom:30px;box-shadow:0 1px 3px rgba(0,0,0,0.03);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;border-bottom:1px solid #f1f5f9;padding-bottom:12px;">
                    <div>
                        <h4 style="margin:0 0 4px 0;font-size:16px;font-weight:700;color:#0f172a;">💬 Operational Communication &amp; Escalation to Management</h4>
                        <p style="margin:0;font-size:12px;color:#64748b;">
                            ${isAdmin
                                ? 'Review and manage operational escalations, blockers, and messages submitted by department employees.'
                                : 'Report operational blockers, resource shortages, equipment delays, or send direct status updates to management.'}
                        </p>
                    </div>
                    <span class="badge ${isAdmin ? 'badge-primary' : 'badge-warning'}" style="font-size:11px;">
                        ${isAdmin ? 'Admin View' : 'Employee Channel'}
                    </span>
                </div>

                ${!isAdmin ? `
                    <!-- Employee Dispatch Form -->
                    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:18px;margin-bottom:20px;">
                        <h5 style="margin:0 0 12px 0;font-size:14px;font-weight:700;color:#0f172a;">✉️ Send New Message / Operational Blocker</h5>
                        <div class="row">
                            <div class="col-md-4 mb-3">
                                <label style="font-size:12px;font-weight:600;color:#475569;">Issue / Update Category *</label>
                                <select id="esc-subject-type" class="form-control form-control-sm">
                                    <option value="Operational Blocker">🚨 Operational Blocker</option>
                                    <option value="Resource / Material Shortage">📦 Resource / Material Shortage</option>
                                    <option value="Equipment Downtime / Maintenance">⚙️ Equipment Downtime</option>
                                    <option value="Target Variance Explanation">🎯 Target Variance Explanation</option>
                                    <option value="General Management Update">📝 General Update</option>
                                </select>
                            </div>
                            <div class="col-md-4 mb-3">
                                <label style="font-size:12px;font-weight:600;color:#475569;">Severity Level</label>
                                <select id="esc-severity" class="form-control form-control-sm">
                                    <option value="Warning" selected>⚠️ Warning (Needs Attention)</option>
                                    <option value="Critical">🚨 Critical (Urgent Blocker)</option>
                                    <option value="Info">ℹ️ Info (General Notice)</option>
                                </select>
                            </div>
                            <div class="col-md-4 mb-3">
                                <label style="font-size:12px;font-weight:600;color:#475569;">Related KPI (Optional)</label>
                                <select id="esc-kpi-select" class="form-control form-control-sm">
                                    <option value="">-- General Department Issue --</option>
                                    ${kpis.map(k => `<option value="${k.kpi_code}">${k.kpi}</option>`).join('')}
                                </select>
                            </div>
                        </div>
                        <div class="mb-3">
                            <label style="font-size:12px;font-weight:600;color:#475569;">Message Details &amp; Context *</label>
                            <textarea id="esc-message-body" class="form-control form-control-sm" rows="3" placeholder="Describe the operational challenge, root cause, required assistance, or status update for management..."></textarea>
                        </div>
                        <div style="display:flex;justify-content:flex-end;">
                            <button class="btn btn-sm btn-primary" id="btn-send-escalation" style="font-weight:600;padding:6px 18px;">
                                🚀 Send Escalation / Message to Admin
                            </button>
                        </div>
                    </div>
                ` : ''}

                <!-- Communications & Escalation Log Table -->
                <div>
                    <h5 style="margin:0 0 10px 0;font-size:13px;font-weight:700;color:#475569;">📜 Department Communication History</h5>
                    <div id="dept-escalations-log-list">
                        <div class="text-center p-3 text-muted"><i class="fa fa-spinner fa-spin mr-1"></i> Loading communication history...</div>
                    </div>
                </div>
            </div>

            <!-- Embedded Department Data Entry History / Logs -->
            <div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:24px;box-shadow:0 1px 3px rgba(0,0,0,0.03);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;border-bottom:1px solid #f1f5f9;padding-bottom:12px;">
                    <div>
                        <h4 style="margin:0 0 4px 0;font-size:16px;font-weight:700;color:#0f172a;">📋 Data Entry Submissions History</h4>
                        <p style="margin:0;font-size:12px;color:#64748b;">Audit log of recent submissions with authenticated user names.</p>
                    </div>
                </div>
                <div id="dept-data-entry-logs-table">
                    <div class="text-center p-3 text-muted"><i class="fa fa-spinner fa-spin mr-1"></i> Loading logs...</div>
                </div>
            </div>
        </div>
    `;

    page.main.html(html);

    // Back & Home button handlers (Admin only)
    if (isAdmin) {
        page.main.find("#dept-home-btn").on("click", function() {
            frappe.set_route("company-tracking-system");
        });
        page.main.find("#dept-back-btn").on("click", function() {
            frappe.set_route("kpi-company-overview");
        });

        // Switch department handler
        page.main.find("#dept-switcher-select").on("change", function() {
            const selected = $(this).val();
            load_dept(page, selected);
        });
    }

    // Timeframe filter handler
    page.main.find("#dept-timeframe-buttons button").on("click", function () {
        page._timeframe = $(this).data("tf");
        load_dept(page, dept);
    });

    // KPI Detail Click Handler
    page.main.find(".kpi-tracking-kpi-card").on("click", function () {
        const kpi_code = $(this).data("kpi");
        if (kpi_code) show_kpi_detail(page, kpi_code);
    });

    // Send Escalation Handler (Employee)
    if (!isAdmin) {
        page.main.find("#btn-send-escalation").on("click", function() {
            const btn = $(this);
            const subType = page.main.find("#esc-subject-type").val();
            const severity = page.main.find("#esc-severity").val();
            const kpiCode = page.main.find("#esc-kpi-select").val();
            const msgBody = page.main.find("#esc-message-body").val().trim();

            if (!msgBody) {
                frappe.show_alert({ message: "Please enter your message details.", indicator: "orange" });
                page.main.find("#esc-message-body").focus();
                return;
            }

            btn.prop("disabled", true).html('<i class="fa fa-spinner fa-spin mr-1"></i> Sending...');

            frappe.xcall("productix.kpi_tracking.services.alert_engine.send_employee_escalation_alert", {
                department: dept,
                message: msgBody,
                subject: `${subType}: ${deptName}`,
                severity: severity,
                kpi: kpiCode || null,
            }).then((res) => {
                btn.prop("disabled", false).html('🚀 Send Escalation / Message to Admin');
                page.main.find("#esc-message-body").val("");
                frappe.show_alert({ message: "✅ Escalation sent directly to Management & Administrators.", indicator: "green" });
                load_embedded_escalations(page, dept);
            }).catch((err) => {
                btn.prop("disabled", false).html('🚀 Send Escalation / Message to Admin');
                frappe.show_alert({ message: "Error sending message: " + (err.message || ""), indicator: "red" });
            });
        });
    }

    // Load subcomponents
    load_embedded_data_entry(page, dept);
    load_embedded_escalations(page, dept);
    load_embedded_data_logs(page, dept);

    // Render Department Trend Chart with lifecycle management
    setTimeout(() => {
        const deptTrendEl = $("#dept-trend-line-chart");
        if (deptTrendEl.length) {
            destroy_chart("#dept-trend-line-chart");
            deptTrendEl.empty();
            if (deptHistory.length > 0 && typeof frappe.Chart !== "undefined") {
                const labels = deptHistory.map(h => h.period);
                const values = deptHistory.map(h => h.score);

                if (deptPred.available && deptPred.predicted_score != null) {
                    labels.push(`(${deptPred.horizon || 'Forecast'})`);
                    values.push(deptPred.predicted_score);
                }

                window.productix_charts["#dept-trend-line-chart"] = new frappe.Chart("#dept-trend-line-chart", {
                    data: {
                        labels: labels,
                        datasets: [
                            { name: "Department Score (%)", values: values, chartType: "line" }
                        ]
                    },
                    type: "line",
                    height: 200,
                    colors: ["#2563eb"],
                    lineOptions: { regionFill: 1, hideDots: 0, dotSize: 5 }
                });
            } else {
                deptTrendEl.html('<div class="text-center p-4 text-muted" style="font-size:12px;">No historical department submissions recorded yet for trend chart.</div>');
            }
        }
    }, 150);
}

function load_embedded_escalations(page, dept) {
    const container = page.main.find("#dept-escalations-log-list");
    const isAdmin = page._ctx && page._ctx.is_admin;

    frappe.xcall("productix.kpi_tracking.services.alert_engine.get_department_escalations", {
        department: dept,
        limit: 10,
    }).then((escalations) => {
        const list = escalations || [];
        if (list.length === 0) {
            container.html('<div class="text-center p-3 text-muted" style="font-size:12px;">No active messages or escalations recorded for this department.</div>');
            return;
        }

        let itemsHtml = list.map(item => {
            const isCrit = item.severity === 'Critical';
            const isWarn = item.severity === 'Warning';
            const badgeClass = isCrit ? 'badge-danger' : (isWarn ? 'badge-warning' : 'badge-info');
            const borderCol = isCrit ? '#ef4444' : (isWarn ? '#f59e0b' : '#3b82f6');
            const statusClass = item.status === 'Resolved' ? 'badge-success' : (item.status === 'Acknowledged' ? 'badge-info' : 'badge-warning');

            return `
                <div style="background:#fff;border:1px solid #e2e8f0;border-left:4px solid ${borderCol};border-radius:8px;padding:12px 16px;margin-bottom:8px;box-shadow:0 1px 2px rgba(0,0,0,0.02);">
                    <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;margin-bottom:4px;">
                        <div style="display:flex;align-items:center;gap:8px;">
                            <span class="badge ${badgeClass}" style="font-size:10px;">${item.severity}</span>
                            <strong style="font-size:13px;color:#0f172a;">${item.subject || item.alert_type}</strong>
                            ${item.kpi ? `<span style="font-size:11px;color:#6366f1;background:#eef2ff;padding:1px 6px;border-radius:4px;">KPI: ${item.kpi}</span>` : ''}
                        </div>
                        <div style="display:flex;align-items:center;gap:8px;">
                            <span class="badge ${statusClass}" style="font-size:10px;">${item.status}</span>
                            <span style="font-size:11px;color:#94a3b8;">${frappe.datetime.prettyDate(item.creation)}</span>
                        </div>
                    </div>
                    <p style="margin:0 0 6px 0;font-size:12px;color:#334155;">${item.message}</p>
                    <div style="display:flex;justify-content:space-between;align-items:center;font-size:11px;color:#64748b;">
                        <span>Sender: <strong>${item.sender_name || item.sender || 'User'}</strong> (${item.sender_role || 'Employee'})</span>
                        ${isAdmin && item.status !== 'Resolved' ? `
                            <div style="display:flex;gap:4px;">
                                ${item.status === 'Active' ? `<button class="btn btn-xs btn-default ack-alert-btn" data-name="${item.name}">👁️ Acknowledge</button>` : ''}
                                <button class="btn btn-xs btn-success resolve-alert-btn" data-name="${item.name}">✅ Resolve</button>
                            </div>
                        ` : ''}
                    </div>
                </div>
            `;
        }).join('');

        container.html(itemsHtml);

        // Admin action handlers
        if (isAdmin) {
            container.find(".ack-alert-btn").on("click", function() {
                const name = $(this).data("name");
                frappe.xcall("productix.kpi_tracking.services.alert_engine.acknowledge_alert", { alert_name: name }).then(() => {
                    frappe.show_alert({ message: "Alert acknowledged.", indicator: "blue" });
                    load_embedded_escalations(page, dept);
                });
            });

            container.find(".resolve-alert-btn").on("click", function() {
                const name = $(this).data("name");
                frappe.xcall("productix.kpi_tracking.services.alert_engine.resolve_alert", { alert_name: name }).then(() => {
                    frappe.show_alert({ message: "Alert marked as resolved.", indicator: "green" });
                    load_embedded_escalations(page, dept);
                });
            });
        }
    }).catch(() => {
        container.html('<div class="text-center p-3 text-muted" style="font-size:12px;">No historical messages found.</div>');
    });
}

function load_embedded_data_entry(page, dept) {
    frappe.xcall("productix.kpi_tracking.api.data_entry.get_pending_kpis", {
        department: dept,
        frequency: page._frequency,
    }).then((kpis) => {
        const container = page.main.find("#dept-pending-kpis-list");
        const total = (kpis || []).length;
        const done = (kpis || []).filter(k => k.submitted).length;
        const pct = total > 0 ? Math.round((done / total) * 100) : 0;

        page.main.find("#dept-data-entry-progress").html(`Submissions: ${done}/${total} Completed (${pct}%)`);

        if (!kpis || kpis.length === 0) {
            container.html('<div class="text-center p-4 text-muted">No pending KPIs found for the selected frequency.</div>');
            return;
        }

        let itemsHtml = kpis.map((kpi, idx) => {
            if (kpi.submitted) {
                const statusCls = (kpi.status || 'On Track').toLowerCase().replace(/[\/\s]+/g, '-');
                return `
                    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-left:4px solid #10b981;border-radius:8px;padding:14px 18px;margin-bottom:10px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">
                        <div style="display:flex;align-items:center;gap:10px;">
                            <span style="font-size:18px;">✅</span>
                            <div>
                                <strong style="font-size:14px;color:#0f172a;">${kpi.kpi_name}</strong>
                                <span style="font-size:12px;color:#64748b;margin-left:8px;">Target: ${kpi.target || "N/A"} ${kpi.unit || ""}</span>
                                <div style="font-size:11px;color:#94a3b8;margin-top:2px;">Logged value: <strong>${kpi.submitted_value}</strong> (${Math.round(kpi.achievement || 0)}%) by ${kpi.entered_by_name || kpi.entered_by || 'User'}</div>
                            </div>
                        </div>
                        <div style="display:flex;align-items:center;gap:8px;">
                            <span class="kpi-tracking-status-badge kpi-tracking-status-badge--${statusCls}">${kpi.status || 'On Track'}</span>
                            <span class="badge badge-success" style="font-size:11px;padding:5px 10px;">Submitted for ${kpi.period}</span>
                        </div>
                    </div>
                `;
            }

            return `
                <div class="card mb-3" style="border:1px solid #e2e8f0;border-left:4px solid #3b82f6;border-radius:8px;box-shadow:0 1px 2px rgba(0,0,0,0.02);">
                    <div class="card-body" style="padding:16px 20px;">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                            <div>
                                <strong style="font-size:14px;color:#0f172a;">${kpi.kpi_name}</strong>
                                <span style="font-size:12px;color:#64748b;margin-left:8px;">Frequency: <strong>${kpi.frequency}</strong></span>
                            </div>
                            <span class="badge" style="background:#eff6ff;color:#1e40af;font-size:11px;">Period: ${kpi.period}</span>
                        </div>
                        <div class="row align-items-center">
                            <div class="col-md-5 mb-2">
                                <label style="font-size:12px;font-weight:600;color:#475569;">Actual Value (${kpi.unit || kpi.measurement_type})</label>
                                <input type="number" class="form-control kpi-actual-input" data-kpi="${kpi.kpi}" data-dept="${dept}" step="any" placeholder="Enter actual achieved value...">
                            </div>
                            <div class="col-md-4 mb-2">
                                <label style="font-size:12px;font-weight:600;color:#475569;">Target Benchmark</label>
                                <div style="font-size:13px;font-weight:700;color:#0f172a;padding:8px 12px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;">
                                    ${kpi.target != null ? kpi.target : "No Target"} ${kpi.unit || ""}
                                </div>
                            </div>
                            <div class="col-md-3 mb-2">
                                <label style="font-size:12px;font-weight:600;color:transparent;">Action</label>
                                <button class="btn btn-primary btn-block dept-submit-btn" style="font-weight:600;">
                                    Submit
                                </button>
                            </div>
                        </div>
                        ${kpi.inputs && kpi.inputs.length > 0 ? `
                            <div style="margin-top:12px;padding-top:10px;border-top:1px solid #f1f5f9;">
                                <span style="font-size:11px;font-weight:700;color:#475569;">Input Parameters:</span>
                                <div class="row mt-1">
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

        container.html(itemsHtml);

        // Submit action
        container.find(".dept-submit-btn").on("click", function () {
            const btn = $(this);
            const card = btn.closest(".card");
            const actualInput = card.find(".kpi-actual-input");
            const actualVal = actualInput.val();

            if (actualVal === "" || actualVal == null) {
                frappe.show_alert({ message: "Please enter a value", indicator: "orange" });
                actualInput.focus();
                return;
            }

            const kpiCode = actualInput.data("kpi");
            const deptCode = actualInput.data("dept");

            const inputValues = [];
            card.find(".kpi-input-field").each(function () {
                if ($(this).val()) {
                    inputValues.push({
                        field_name: $(this).data("field"),
                        label: $(this).data("label"),
                        value: parseFloat($(this).val()),
                        field_type: "Float",
                    });
                }
            });

            btn.prop("disabled", true).html('<i class="fa fa-spinner fa-spin"></i> Submitting...');

            frappe.xcall("productix.kpi_tracking.api.data_entry.submit_kpi_data", {
                kpi: kpiCode,
                department: deptCode,
                actual_value: actualVal,
                input_values: inputValues.length > 0 ? inputValues : null,
            }).then((r) => {
                frappe.show_alert({ message: `✅ Submitted: ${r.status} (${Math.round(r.achievement)}%)`, indicator: r.status === "On Track" ? "green" : "orange" });
                load_dept(page, dept);
            }).catch((err) => {
                btn.prop("disabled", false).text("Submit");
                frappe.show_alert({ message: "Error submitting: " + (err.message || ""), indicator: "red" });
            });
        });
    });
}

function load_embedded_data_logs(page, dept) {
    const filters = { docstatus: 1 };
    if (dept && dept !== 'All') {
        filters.department = dept;
    }

    frappe.xcall("frappe.client.get_list", {
        doctype: "KPI Data Entry",
        filters: filters,
        fields: ["name", "kpi", "department", "actual_value", "target_value", "achievement_percentage", "status", "period", "entry_date", "entered_by", "creation"],
        order_by: "creation desc",
        limit_page_length: 15,
    }).then((entries) => {
        const logs = entries || [];
        const container = page.main.find("#dept-data-entry-logs-table");

        if (logs.length === 0) {
            container.html('<div class="text-center p-3 text-muted">No historical data submissions found for this department.</div>');
            return;
        }

        let tableRows = logs.map(l => {
            const statusCls = (l.status || 'On Track').toLowerCase().replace(/[\/\s]+/g, '-');
            const enteredBy = l.entered_by || 'User';
            return `
                <tr>
                    <td style="font-size:12px;color:#64748b;">${l.entry_date}</td>
                    <td><strong>${l.kpi}</strong></td>
                    <td><span class="badge badge-light">${l.period}</span></td>
                    <td class="font-weight-bold">${l.actual_value}</td>
                    <td class="text-muted">${l.target_value != null ? l.target_value : '--'}</td>
                    <td><span class="kpi-tracking-status-badge kpi-tracking-status-badge--${statusCls}">${l.status}</span></td>
                    <td><strong style="color:#0f172a;">${enteredBy}</strong></td>
                    <td style="font-size:11px;color:#94a3b8;">${frappe.datetime.prettyDate(l.creation)}</td>
                </tr>
            `;
        }).join('');

        container.html(`
            <div class="table-responsive">
                <table class="table table-sm table-bordered table-hover" style="font-size:12px;background:#fff;margin:0;">
                    <thead style="background:#f1f5f9;color:#0f172a;font-weight:700;">
                        <tr>
                            <th>Entry Date</th>
                            <th>KPI</th>
                            <th>Period</th>
                            <th>Actual Value</th>
                            <th>Target</th>
                            <th>Status</th>
                            <th>Entered By</th>
                            <th>Timestamp</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${tableRows}
                    </tbody>
                </table>
            </div>
        `);
    }).catch(() => {
        page.main.find("#dept-data-entry-logs-table").html('<div class="text-center p-3 text-muted">No historical submissions recorded.</div>');
    });
}

function show_kpi_detail(page, kpi_code) {
    if (page._kpi_dialog) {
        try {
            if (page._kpi_dialog_chart) {
                destroy_chart(page._kpi_dialog_chart);
                page._kpi_dialog_chart = null;
            }
            page._kpi_dialog.hide();
            if (page._kpi_dialog.$wrapper) {
                page._kpi_dialog.$wrapper.remove();
            }
        } catch (e) {}
        page._kpi_dialog = null;
    }

    frappe.xcall("productix.kpi_tracking.api.dashboard.get_kpi_detail", {
        kpi_code: kpi_code,
        timeframe: page._timeframe,
        horizon: page._horizon,
    }).then((data) => {
        if (!data || !data.kpi) {
            frappe.show_alert({ message: "Unable to load KPI details.", indicator: "red" });
            return;
        }

        const kpi = data.kpi || {};
        const unit = kpi.unit || "";
        const history = (data.history || []).slice().reverse();
        const growth = data.growth || {};
        const trend = data.trend || {};
        const multiPreds = data.predictions_all || {};
        const predTomorrow = multiPreds.tomorrow || {};
        const predWeek = multiPreds.next_week || {};
        const predMonth = multiPreds.next_month || {};
        const predQuarter = multiPreds.next_quarter || {};

        let growthStr = "--";
        if (growth.growth_percentage != null) {
            growthStr = (growth.growth_percentage > 0 ? "+" : "") + growth.growth_percentage + "%";
        }

        const targetVal = kpi.target_value != null ? kpi.target_value : "--";
        const latestVal = data.latest ? data.latest.actual_value : null;
        const latestAch = data.latest ? data.latest.achievement_percentage : null;
        const latestScore = (latestAch != null) ? Math.min(100, Math.max(0, Math.round(latestAch))) : null;
        const dir = kpi.direction || "Higher is Better";

        let forecastHtml = '';
        if (multiPreds.available) {
            const r2Str = multiPreds.r_squared != null ? ` (Model R² = ${multiPreds.r_squared})` : "";
            forecastHtml = `
                <div style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:10px;padding:14px 18px;margin-bottom:18px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;flex-wrap:wrap;gap:6px;">
                        <span style="font-size:12px;font-weight:700;color:#0369a1;">🔮 Projected Raw Metric Forecasts (OLS Linear Regression)${r2Str}</span>
                        <span style="font-size:11px;color:#0284c7;background:#e0f2fe;padding:2px 8px;border-radius:4px;font-weight:600;">Values in ${unit || 'metric units'}</span>
                    </div>
                    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px;">
                        <div style="background:#fff;padding:10px 12px;border-radius:6px;border:1px solid #e0f2fe;text-align:center;">
                            <div style="font-size:11px;color:#64748b;font-weight:600;">Tomorrow</div>
                            <div style="font-size:16px;font-weight:800;color:#0284c7;margin:2px 0;">${predTomorrow.predicted_value != null ? predTomorrow.predicted_value : '--'} <span style="font-size:11px;font-weight:normal;">${unit}</span></div>
                            <div style="font-size:10px;color:#0284c7;font-weight:700;">${predTomorrow.confidence || 95}% confidence</div>
                        </div>
                        <div style="background:#fff;padding:10px 12px;border-radius:6px;border:1px solid #e0f2fe;text-align:center;">
                            <div style="font-size:11px;color:#64748b;font-weight:600;">Next Week</div>
                            <div style="font-size:16px;font-weight:800;color:#0284c7;margin:2px 0;">${predWeek.predicted_value != null ? predWeek.predicted_value : '--'} <span style="font-size:11px;font-weight:normal;">${unit}</span></div>
                            <div style="font-size:10px;color:#0284c7;font-weight:700;">${predWeek.confidence || 94}% confidence</div>
                        </div>
                        <div style="background:#fff;padding:10px 12px;border-radius:6px;border:1px solid #e0f2fe;text-align:center;">
                            <div style="font-size:11px;color:#64748b;font-weight:600;">Next Month</div>
                            <div style="font-size:16px;font-weight:800;color:#2563eb;margin:2px 0;">${predMonth.predicted_value != null ? predMonth.predicted_value : '--'} <span style="font-size:11px;font-weight:normal;">${unit}</span></div>
                            <div style="font-size:10px;color:#2563eb;font-weight:700;">${predMonth.confidence || 93}% confidence</div>
                        </div>
                        <div style="background:#fff;padding:10px 12px;border-radius:6px;border:1px solid #e0f2fe;text-align:center;">
                            <div style="font-size:11px;color:#64748b;font-weight:600;">Next Quarter</div>
                            <div style="font-size:16px;font-weight:800;color:#0284c7;margin:2px 0;">${predQuarter.predicted_value != null ? predQuarter.predicted_value : '--'} <span style="font-size:11px;font-weight:normal;">${unit}</span></div>
                            <div style="font-size:10px;color:#0284c7;font-weight:700;">${predQuarter.confidence || 90}% confidence</div>
                        </div>
                    </div>
                </div>
            `;
        } else {
            forecastHtml = `
                <div style="background:#f8fafc;border:1px dashed #cbd5e1;border-radius:10px;padding:16px 18px;margin-bottom:18px;text-align:center;">
                    <span style="font-size:12px;font-weight:700;color:#475569;display:block;margin-bottom:4px;">🔮 Multi-Horizon Predictive Forecasts</span>
                    <p style="font-size:12px;color:#94a3b8;margin:0;">${multiPreds.message || "Prediction unavailable: Requires at least 3 historical reporting periods."}</p>
                </div>
            `;
        }

        const chartUid = "kpi-modal-trend-chart-" + (kpi_code || "metric").replace(/[^a-zA-Z0-9_-]/g, "_") + "-" + Date.now();

        let detail = `
            <div class="kpi-tracking-app" style="padding:10px 0;">
                <div class="row mb-3" style="text-align:center;">
                    <div class="col-3" style="background:#f8fafc;padding:12px;border-radius:8px;border:1px solid #e2e8f0;">
                        <span style="font-size:11px;color:#64748b;text-transform:uppercase;font-weight:700;">Trend Status</span>
                        <div style="font-size:15px;font-weight:800;color:#0f172a;margin-top:2px;">${trend.trend || "Stable"} (${trend.relative_slope > 0 ? "+" : ""}${trend.relative_slope || 0}%)</div>
                        <div style="font-size:10px;color:#94a3b8;margin-top:1px;">OLS Direction</div>
                    </div>
                    <div class="col-3" style="background:#f8fafc;padding:12px;border-radius:8px;border:1px solid #e2e8f0;">
                        <span style="font-size:11px;color:#64748b;text-transform:uppercase;font-weight:700;">Period Growth (PoP)</span>
                        <div style="font-size:15px;font-weight:800;color:#10b981;margin-top:2px;">${growthStr}</div>
                        <div style="font-size:10px;color:#94a3b8;margin-top:1px;">${growth.status || "Stable"}</div>
                    </div>
                    <div class="col-3" style="background:#f8fafc;padding:12px;border-radius:8px;border:1px solid #e2e8f0;">
                        <span style="font-size:11px;color:#64748b;text-transform:uppercase;font-weight:700;">Target Benchmark</span>
                        <div style="font-size:15px;font-weight:800;color:#475569;margin-top:2px;">${targetVal} <span style="font-size:11px;font-weight:normal;">${unit}</span></div>
                        <div style="font-size:10px;color:#94a3b8;margin-top:1px;">${dir}</div>
                    </div>
                    <div class="col-3" style="background:#f8fafc;padding:12px;border-radius:8px;border:1px solid #e2e8f0;">
                        <span style="font-size:11px;color:#64748b;text-transform:uppercase;font-weight:700;">Latest Value &amp; Score</span>
                        <div style="font-size:15px;font-weight:800;color:#2563eb;margin-top:2px;">${latestVal != null ? latestVal + " " + unit : "--"}</div>
                        <div style="font-size:10px;color:#2563eb;font-weight:600;margin-top:1px;">${latestAch != null ? Math.round(latestAch) + "% Achieved" : "--"} | Score: ${latestScore != null ? latestScore + "/100" : "--"}</div>
                    </div>
                </div>

                ${forecastHtml}

                <div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px;margin-bottom:18px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                        <h6 style="margin:0;font-weight:700;font-size:13px;color:#0f172a;">📈 Historical Actual vs. Target Trend Line &amp; Forecast</h6>
                        <span style="font-size:11px;color:#64748b;">${history.length} Data Points</span>
                    </div>
                    <div id="${chartUid}" class="kpi-modal-chart-mount" style="height:220px;min-height:220px;"></div>
                </div>
            </div>
        `;

        const d = new frappe.ui.Dialog({
            title: `📊 ${kpi.kpi_name || kpi_code} — Trend & High-Accuracy Forecasting`,
            size: "extra-large",
            fields: [{ fieldtype: "HTML", fieldname: "detail_html" }],
        });
        page._kpi_dialog = d;

        d.fields_dict.detail_html.$wrapper.html(detail);

        let chartInitialized = false;
        function renderModalChart() {
            if (chartInitialized) return;
            const chartEl = d.fields_dict.detail_html.$wrapper.find(`#${chartUid}`);
            if (!chartEl.length) return;

            chartInitialized = true;
            if (page._kpi_dialog_chart) {
                destroy_chart(page._kpi_dialog_chart);
                page._kpi_dialog_chart = null;
            }
            chartEl.empty();

            if (history.length > 0 && typeof frappe.Chart !== "undefined") {
                const labels = history.map((h) => h.period || h.entry_date || "");
                const actualVals = history.map((h) => parseFloat(h.actual_value != null ? h.actual_value : 0));
                const targetVals = history.map((h) => parseFloat(h.target_value != null ? h.target_value : (kpi.target_value || 0)));

                if (multiPreds.available && predMonth.predicted_value != null) {
                    labels.push(`(${predMonth.horizon || 'Next Month'} Forecast)`);
                    actualVals.push(parseFloat(predMonth.predicted_value));
                    targetVals.push(parseFloat(kpi.target_value || 0));
                }

                try {
                    page._kpi_dialog_chart = new frappe.Chart(chartEl[0], {
                        data: {
                            labels: labels,
                            datasets: [
                                { name: `Actual / Forecast (${unit || 'Value'})`, values: actualVals, chartType: "line" },
                                { name: `Target Benchmark (${unit || 'Value'})`, values: targetVals, chartType: "line" },
                            ],
                        },
                        type: "axis-mixed",
                        height: 200,
                        colors: ["#2563eb", "#94a3b8"],
                        lineOptions: { regionFill: 1, hideDots: 0, dotSize: 5 },
                    });
                } catch (err) {
                    console.error("Error creating modal trend chart:", err);
                }
            } else {
                chartEl.html('<div class="text-center p-4 text-muted" style="font-size:12px;">No historical data points recorded yet for trend chart.</div>');
            }
        }

        d.$wrapper.on("shown.bs.modal", function () {
            renderModalChart();
        });

        d.onhide = function () {
            if (page._kpi_dialog_chart) {
                destroy_chart(page._kpi_dialog_chart);
                page._kpi_dialog_chart = null;
            }
            setTimeout(() => {
                if (d.$wrapper) {
                    d.$wrapper.remove();
                }
                $(".modal-backdrop").remove();
            }, 100);
            page._kpi_dialog = null;
        };

        d.show();

        setTimeout(() => {
            renderModalChart();
        }, 150);
    });
}
