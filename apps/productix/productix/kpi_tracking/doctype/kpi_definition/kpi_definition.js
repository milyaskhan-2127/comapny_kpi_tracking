// Productix KPI Tracking — KPI Definition Form Controller

frappe.ui.form.on("KPI Definition", {
    refresh: function (frm) {
        const user = frappe.session.user;
        const is_admin = user === "Administrator" ||
                         frappe.user.has_role("System Manager") ||
                         frappe.user.has_role("KPI Admin");

        render_commercial_kpi_specification(frm, is_admin);

        // Common Actions
        if (!frm.is_new()) {
            frm.add_custom_button(__("✍️ Log Metric Entry"), function () {
                frappe.set_route("kpi-data-entry-page", {
                    department: frm.doc.department,
                    kpi: frm.doc.name
                });
            }, __("Actions")).addClass("btn-primary");

            frm.add_custom_button(__("🏢 Department Dashboard"), function () {
                frappe.set_route("kpi-department-dashboard", {
                    department: frm.doc.department
                });
            }, __("Navigation"));

            frm.add_custom_button(__("📈 Trend & Forecast Analysis"), function () {
                show_kpi_trend_forecast_modal(frm);
            }, __("Analytics"));
        }

        if (is_admin) {
            frm.add_custom_button(__("📐 Formula Builder"), function () {
                frappe.set_route("kpi-formula-builder");
            }, __("Tools"));

            frm.add_custom_button(__("🏢 Company Overview"), function () {
                frappe.set_route("kpi-company-overview");
            }, __("Navigation"));
        } else {
            // Employees view specifications with read-only protection
            frm.disable_save();
            if (frm.page.clear_primary_action) frm.page.clear_primary_action();
            if (frm.page.clear_secondary_action) frm.page.clear_secondary_action();
        }
    },

    direction: function (frm) {
        if (frm.doc.direction === "Lower is Better") {
            frm.set_df_property("target_value", "description", __("Target ceiling (lower actual values produce higher achievement scores)"));
        } else if (frm.doc.direction === "Target Range") {
            frm.set_df_property("target_value", "description", __("Upper bound of acceptable target range"));
            frm.set_df_property("minimum_acceptable", "description", __("Lower bound of acceptable target range"));
        } else if (frm.doc.direction === "Exact Target") {
            frm.set_df_property("target_value", "description", __("Exact benchmark (deviations decrease achievement score)"));
        } else {
            frm.set_df_property("target_value", "description", __("Target benchmark (higher actual values yield higher achievement)"));
        }
    }
});

function render_commercial_kpi_specification(frm, is_admin) {
    if (frm.is_new()) return;

    frm.dashboard.clear_headline();

    const dir = frm.doc.direction || "Higher is Better";
    let dirBadge = { bg: "#ecfdf5", border: "#10b981", text: "#065f46", icon: "📈" };

    if (dir === "Lower is Better") {
        dirBadge = { bg: "#eff6ff", border: "#3b82f6", text: "#1e40af", icon: "📉" };
    } else if (dir === "Target Range") {
        dirBadge = { bg: "#faf5ff", border: "#8b5cf6", text: "#5b21b6", icon: "🎯" };
    } else if (dir === "Exact Target") {
        dirBadge = { bg: "#fffbeb", border: "#f59e0b", text: "#92400e", icon: "🎯" };
    }

    const isActive = frm.doc.is_active;
    const statusPill = isActive
        ? `<span style="background:#dcfce7;color:#166534;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700;">🟢 ACTIVE</span>`
        : `<span style="background:#f1f5f9;color:#64748b;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700;">⚪ INACTIVE</span>`;

    const html = `
        <div style="background:#ffffff;border:1px solid #e2e8f0;border-left:5px solid ${dirBadge.border};border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.04);padding:20px 24px;margin-bottom:20px;">
            <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:16px;border-bottom:1px solid #f1f5f9;padding-bottom:12px;">
                <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
                    <span style="font-size:18px;font-weight:700;color:#0f172a;">${frm.doc.kpi_name || frm.doc.name}</span>
                    <span style="font-size:12px;background:#f1f5f9;color:#475569;padding:3px 8px;border-radius:6px;font-family:monospace;font-weight:600;">
                        ${frm.doc.kpi_code || frm.doc.name}
                    </span>
                    <span style="background:${dirBadge.bg};border:1px solid ${dirBadge.border};color:${dirBadge.text};font-weight:600;font-size:11px;padding:3px 10px;border-radius:6px;">
                        ${dirBadge.icon} ${dir}
                    </span>
                </div>
                <div style="display:flex;align-items:center;gap:10px;">
                    ${statusPill}
                    ${!is_admin ? '<span class="badge badge-secondary" style="font-size:11px;">Department View</span>' : ''}
                </div>
            </div>

            <!-- 4-Card Commercial KPI Specification Grid -->
            <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));gap:14px;margin-bottom:16px;">
                <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:12px 16px;">
                    <div style="font-size:11px;color:#64748b;font-weight:600;text-transform:uppercase;margin-bottom:4px;">🎯 Benchmark Target</div>
                    <div style="font-size:16px;font-weight:700;color:#0f172a;">
                        ${frm.doc.target_value !== null && frm.doc.target_value !== undefined ? frm.doc.target_value : 'No Target'}
                        <span style="font-size:12px;color:#64748b;font-weight:normal;">${frm.doc.unit || ''}</span>
                    </div>
                    <div style="font-size:11px;color:#64748b;margin-top:2px;">
                        Type: <strong style="color:#334155;">${frm.doc.target_type || 'Fixed Target'}</strong>
                    </div>
                </div>

                <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:12px 16px;">
                    <div style="font-size:11px;color:#64748b;font-weight:600;text-transform:uppercase;margin-bottom:4px;">📅 Cadence & Weight</div>
                    <div style="font-size:16px;font-weight:700;color:#0f172a;">
                        ${frm.doc.frequency || 'Monthly'}
                    </div>
                    <div style="font-size:11px;color:#64748b;margin-top:2px;">
                        Dept Weight: <strong style="color:#334155;">${frm.doc.weight || 1.0}x</strong>
                    </div>
                </div>

                <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:12px 16px;">
                    <div style="font-size:11px;color:#64748b;font-weight:600;text-transform:uppercase;margin-bottom:4px;">🏢 Department & Owner</div>
                    <div style="font-size:15px;font-weight:700;color:#0f172a;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
                        ${frm.doc.department || 'Not Assigned'}
                    </div>
                    <div style="font-size:11px;color:#64748b;margin-top:2px;">
                        Owner: <strong style="color:#334155;">${frm.doc.owner || 'Admin'}</strong>
                    </div>
                </div>

                <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:12px 16px;">
                    <div style="font-size:11px;color:#64748b;font-weight:600;text-transform:uppercase;margin-bottom:4px;">📊 Analytics Config</div>
                    <div style="font-size:13px;font-weight:600;color:#0f172a;display:flex;align-items:center;gap:6px;">
                        <span>Warn: <strong style="color:#d97706;">${frm.doc.warning_threshold || 80}%</strong></span>
                        <span>Crit: <strong style="color:#dc2626;">${frm.doc.critical_threshold || 60}%</strong></span>
                    </div>
                    <div style="font-size:11px;color:#64748b;margin-top:2px;">
                        Forecasting: <strong style="color:#334155;">${frm.doc.prediction_enabled ? 'Enabled' : 'Disabled'}</strong>
                    </div>
                </div>
            </div>

            <!-- Dynamic Performance Snapshot Container -->
            <div id="kpi-spec-snapshot-${frm.doc.name}" style="background:#f1f5f9;border-radius:8px;padding:12px 16px;font-size:12px;color:#475569;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;">
                <span>Loading recent performance telemetry...</span>
            </div>
        </div>
    `;

    frm.dashboard.set_headline(html);

    // Fetch live performance telemetry
    frappe.call({
        method: "productix.kpi_tracking.api.dashboard.get_kpi_detail",
        args: { kpi_code: frm.doc.name, timeframe: "6_months" },
        callback: function (r) {
            if (r.message) {
                const data = r.message;
                const snapshotEl = $(`#kpi-spec-snapshot-${frm.doc.name}`);
                if (!snapshotEl.length) return;

                const latest = data.latest;
                const trend = data.trend;
                const growth = data.growth;
                const prediction = data.selected_prediction;

                let actualHtml = latest ? `<strong>${latest.actual_value} ${frm.doc.unit || ''}</strong> (${latest.achievement_percentage}%)` : `<span style="color:#94a3b8;">No data submitted</span>`;
                let trendHtml = trend ? `<strong>${trend.trend}</strong> (${trend.slope > 0 ? '+' : ''}${trend.slope})` : `Stable`;
                let growthHtml = growth && growth.formatted ? `<strong>${growth.formatted}</strong>` : `N/A`;
                let predHtml = prediction && prediction.predicted_value !== undefined ? `<strong>${prediction.predicted_value} ${frm.doc.unit || ''}</strong> (${prediction.confidence}% conf)` : `<span style="color:#94a3b8;">Unavailable</span>`;

                snapshotEl.html(`
                    <div>Latest Actual: <span style="color:#0f172a;">${actualHtml}</span></div>
                    <div>Trend: <span style="color:#0f172a;">${trendHtml}</span></div>
                    <div>Period Growth: <span style="color:#0f172a;">${growthHtml}</span></div>
                    <div>Next Forecast: <span style="color:#0f172a;">${predHtml}</span></div>
                `);
            }
        }
    });
}

function show_kpi_trend_forecast_modal(frm) {
    frappe.call({
        method: "productix.kpi_tracking.api.dashboard.get_kpi_detail",
        args: { kpi_code: frm.doc.name, timeframe: "overall" },
        callback: function (r) {
            if (!r.message) {
                frappe.msgprint(__("Unable to load trend telemetry for this KPI."));
                return;
            }

            const data = r.message;
            const history = (data.history || []).slice().reverse();
            const trend = data.trend || {};
            const growth = data.growth || {};
            const pred = data.predictions_all || {};

            let modalChart = null;
            const chartContainerId = `kpi-chart-modal-${(frm.doc.name || 'kpi').replace(/[^a-zA-Z0-9_-]/g, '_')}-${Date.now()}`;

            const dialog = new frappe.ui.Dialog({
                title: `${frm.doc.kpi_name || frm.doc.name} — Historical Trend & Forecast`,
                size: "large",
                fields: [
                    {
                        fieldtype: "HTML",
                        fieldname: "chart_area"
                    }
                ]
            });

            const html = `
                <div style="padding:10px 0;">
                    <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(140px, 1fr));gap:10px;margin-bottom:16px;">
                        <div style="background:#f8fafc;padding:10px 14px;border-radius:8px;border:1px solid #e2e8f0;">
                            <div style="font-size:11px;color:#64748b;">Trend Classification</div>
                            <div style="font-size:14px;font-weight:700;color:#0f172a;">${trend.trend || 'Stable'}</div>
                        </div>
                        <div style="background:#f8fafc;padding:10px 14px;border-radius:8px;border:1px solid #e2e8f0;">
                            <div style="font-size:11px;color:#64748b;">Regression Slope</div>
                            <div style="font-size:14px;font-weight:700;color:#0f172a;">${trend.slope || 0.0}</div>
                        </div>
                        <div style="background:#f8fafc;padding:10px 14px;border-radius:8px;border:1px solid #e2e8f0;">
                            <div style="font-size:11px;color:#64748b;">Period Growth</div>
                            <div style="font-size:14px;font-weight:700;color:#0f172a;">${growth.formatted || 'N/A'}</div>
                        </div>
                        <div style="background:#f8fafc;padding:10px 14px;border-radius:8px;border:1px solid #e2e8f0;">
                            <div style="font-size:11px;color:#64748b;">Forecast Status</div>
                            <div style="font-size:14px;font-weight:700;color:#0f172a;">${pred.available ? 'Dynamic OLS' : 'Insufficient Data'}</div>
                        </div>
                    </div>

                    <div style="font-size:13px;font-weight:700;color:#0f172a;margin-bottom:8px;">Historical Performance Timeline</div>
                    <div id="${chartContainerId}" style="height:260px;background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;padding:10px;"></div>
                </div>
            `;

            dialog.fields_dict.chart_area.$wrapper.html(html);

            let chartRendered = false;
            function renderChart() {
                if (chartRendered) return;
                const chartEl = dialog.fields_dict.chart_area.$wrapper.find(`#${chartContainerId}`);
                if (!chartEl.length) return;

                chartRendered = true;
                if (history.length >= 2 && window.frappe && frappe.Chart) {
                    const labels = history.map(h => h.period || h.entry_date);
                    const actualData = history.map(h => parseFloat(h.actual_value || 0));
                    const targetData = history.map(h => parseFloat(h.target_value || frm.doc.target_value || 0));

                    try {
                        modalChart = new frappe.Chart(chartEl[0], {
                            data: {
                                labels: labels,
                                datasets: [
                                    { name: `Actual Value (${frm.doc.unit || 'Value'})`, values: actualData, chartType: "line" },
                                    { name: `Target Benchmark (${frm.doc.unit || 'Value'})`, values: targetData, chartType: "line" }
                                ]
                            },
                            title: `${frm.doc.kpi_name} History`,
                            type: "line",
                            height: 230,
                            colors: ["#2563eb", "#94a3b8"],
                            lineOptions: { hideDots: 0, regionFill: 1 }
                        });
                    } catch (err) {
                        console.error("Error creating KPI definition history chart:", err);
                    }
                } else {
                    chartEl.html(`
                        <div style="display:flex;align-items:center;justify-content:center;height:100%;color:#94a3b8;font-size:13px;">
                            Insufficient historical data points to render trend line chart (requires ≥ 2 entries).
                        </div>
                    `);
                }
            }

            dialog.$wrapper.on("shown.bs.modal", function () {
                renderChart();
            });

            dialog.onhide = function () {
                if (modalChart) {
                    try { modalChart.destroy(); } catch (e) {}
                    modalChart = null;
                }
                setTimeout(() => {
                    if (dialog.$wrapper) {
                        dialog.$wrapper.remove();
                    }
                    $(".modal-backdrop").remove();
                }, 100);
            };

            dialog.show();

            setTimeout(() => {
                renderChart();
            }, 150);
        }
    });
}
