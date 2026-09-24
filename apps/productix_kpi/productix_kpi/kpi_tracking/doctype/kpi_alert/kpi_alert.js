// Productix KPI Tracking — KPI Alert Form Controller

frappe.ui.form.on("KPI Alert", {
    refresh: function (frm) {
        const user = frappe.session.user;
        const is_admin = user === "Administrator" ||
                         frappe.user.has_role("System Manager") ||
                         frappe.user.has_role("KPI Admin");

        render_commercial_alert_card(frm, is_admin);

        if (!is_admin) {
            // Protect structural administrative fields from tampering while keeping the alert editable
            frm.set_df_property("department", "read_only", 1);
            frm.set_df_property("alert_type", "read_only", 1);
            frm.set_df_property("severity", "read_only", 1);
            frm.set_df_property("trigger_period", "read_only", 1);
            frm.set_df_property("trigger_value", "read_only", 1);
            frm.set_df_property("threshold_value", "read_only", 1);

            // Employee Actions
            frm.add_custom_button(__("🏢 Department Dashboard"), function () {
                frappe.set_route("kpi-department-dashboard");
            }, __("Navigation"));

            if (frm.doc.status === "Active") {
                frm.add_custom_button(__("👁️ Acknowledge"), function () {
                    frappe.call({
                        doc: frm.doc,
                        method: "acknowledge",
                        callback: function (r) {
                            frappe.show_alert({ message: __("Alert acknowledged successfully."), indicator: "blue" });
                            frm.reload_doc();
                        }
                    });
                }, __("Actions")).addClass("btn-primary");
            }

            if (frm.doc.status !== "Resolved") {
                frm.add_custom_button(__("✅ Resolve"), function () {
                    frappe.confirm(__("Mark this directive/alert as Resolved?"), function () {
                        frappe.call({
                            doc: frm.doc,
                            method: "resolve",
                            callback: function (r) {
                                frappe.show_alert({ message: __("Alert marked as Resolved."), indicator: "green" });
                                frm.reload_doc();
                            }
                        });
                    });
                }, __("Actions")).addClass("btn-success");
            }

            if (frm.doc.kpi) {
                frm.add_custom_button(__("📈 View KPI Detail"), function () {
                    frappe.set_route("kpi-department-dashboard", { kpi: frm.doc.kpi });
                }, __("Navigation"));
            }
        } else {
            // Administrator Actions
            frm.add_custom_button(__("🚨 Action Center"), function () {
                frappe.set_route("kpi-action-center");
            }, __("Navigation"));

            frm.add_custom_button(__("🏢 Company Overview"), function () {
                frappe.set_route("kpi-company-overview");
            }, __("Navigation"));

            if (frm.doc.status === "Active") {
                frm.add_custom_button(__("👁️ Acknowledge"), function () {
                    frappe.call({
                        doc: frm.doc,
                        method: "acknowledge",
                        callback: function (r) {
                            frappe.show_alert({ message: __("Alert acknowledged"), indicator: "blue" });
                            frm.reload_doc();
                        }
                    });
                }, __("Actions"));
            }

            if (frm.doc.status !== "Resolved") {
                frm.add_custom_button(__("✅ Mark as Resolved"), function () {
                    frappe.confirm(__("Mark this alert as Resolved?"), function () {
                        frappe.call({
                            doc: frm.doc,
                            method: "resolve",
                            callback: function (r) {
                                frappe.show_alert({ message: __("Alert marked as Resolved"), indicator: "green" });
                                frm.reload_doc();
                            }
                        });
                    });
                }, __("Actions")).addClass("btn-success");
            }
        }
    }
});

function render_commercial_alert_card(frm, is_admin) {
    if (frm.is_new()) return;

    frm.dashboard.clear_headline();

    const sev = frm.doc.severity || "Info";
    const status = frm.doc.status || "Active";

    let sevBadge = {
        bg: "#fee2e2",
        border: "#ef4444",
        text: "#991b1b",
        icon: "🔴",
        label: "CRITICAL"
    };

    if (sev === "Warning") {
        sevBadge = {
            bg: "#fef3c7",
            border: "#f59e0b",
            text: "#92400e",
            icon: "🟡",
            label: "WARNING"
        };
    } else if (sev === "Info" || sev === "Informational") {
        sevBadge = {
            bg: "#e0f2fe",
            border: "#0ea5e9",
            text: "#0369a1",
            icon: "🔵",
            label: "INFO"
        };
    }

    let statusPill = `<span style="background:#dbeafe;color:#1e40af;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700;">${status.toUpperCase()}</span>`;
    if (status === "Resolved") {
        statusPill = `<span style="background:#dcfce7;color:#166534;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700;">🟢 RESOLVED</span>`;
    } else if (status === "Acknowledged") {
        statusPill = `<span style="background:#f3e8ff;color:#6b21a8;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700;">🟣 ACKNOWLEDGED</span>`;
    }

    const html = `
        <div style="background:#ffffff;border:1px solid #e2e8f0;border-left:5px solid ${sevBadge.border};border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.04);padding:20px 24px;margin-bottom:20px;">
            <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:14px;border-bottom:1px solid #f1f5f9;padding-bottom:12px;">
                <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
                    <span style="background:${sevBadge.bg};border:1px solid ${sevBadge.border};color:${sevBadge.text};font-weight:700;font-size:11px;padding:3px 10px;border-radius:6px;letter-spacing:0.5px;">
                        ${sevBadge.icon} ${sevBadge.label}
                    </span>
                    <span style="font-size:12px;background:#f1f5f9;color:#475569;padding:3px 10px;border-radius:6px;font-family:monospace;font-weight:600;">
                        ${frm.doc.name}
                    </span>
                    <span style="font-size:12px;background:#f8fafc;color:#64748b;border:1px solid #e2e8f0;padding:2px 8px;border-radius:6px;">
                        ${frm.doc.alert_type || 'Alert Directive'}
                    </span>
                </div>
                <div>
                    ${statusPill}
                </div>
            </div>

            <div style="margin-bottom:14px;">
                <h3 style="font-size:18px;font-weight:700;color:#0f172a;margin:0 0 8px 0;line-height:1.3;">
                    ${frm.doc.subject || 'KPI Directive Notice'}
                </h3>
                <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;font-size:12px;color:#64748b;">
                    <span>🏢 Department: <strong style="color:#1e293b;">${frm.doc.department || 'All Departments'}</strong></span>
                    ${frm.doc.kpi ? `<span>📊 KPI: <strong style="color:#1e293b;">${frm.doc.kpi}</strong></span>` : ''}
                    ${frm.doc.trigger_period ? `<span>📅 Period: <strong style="color:#1e293b;">${frm.doc.trigger_period}</strong></span>` : ''}
                    ${frm.doc.sender_name ? `<span>👤 Issued By: <strong style="color:#1e293b;">${frm.doc.sender_name}</strong></span>` : ''}
                </div>
            </div>

            <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:14px 16px;margin-bottom:14px;">
                <div style="font-size:11px;font-weight:700;text-transform:uppercase;color:#64748b;margin-bottom:6px;letter-spacing:0.5px;">
                    Directive Message
                </div>
                <div style="font-size:13px;color:#1e293b;line-height:1.5;white-space:pre-wrap;">
                    ${frm.doc.message || 'No specific directive text recorded.'}
                </div>
            </div>

            ${(frm.doc.trigger_value !== undefined && frm.doc.trigger_value !== null) || (frm.doc.threshold_value !== undefined && frm.doc.threshold_value !== null) ? `
                <div style="display:flex;gap:20px;flex-wrap:wrap;font-size:12px;color:#475569;background:#f1f5f9;padding:10px 14px;border-radius:6px;">
                    ${frm.doc.trigger_value !== null && frm.doc.trigger_value !== undefined ? `<span>Trigger Value: <strong style="color:#0f172a;">${frm.doc.trigger_value}</strong></span>` : ''}
                    ${frm.doc.threshold_value !== null && frm.doc.threshold_value !== undefined ? `<span>Threshold Value: <strong style="color:#0f172a;">${frm.doc.threshold_value}</strong></span>` : ''}
                </div>
            ` : ''}
        </div>
    `;

    frm.dashboard.set_headline(html);
}
