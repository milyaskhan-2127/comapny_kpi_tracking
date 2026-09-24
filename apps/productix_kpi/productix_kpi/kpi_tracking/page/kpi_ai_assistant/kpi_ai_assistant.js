// Productix KPI Tracking — Conversational AI Assistant Page (Admin Only)

frappe.pages["kpi-ai-assistant"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "KPI AI Assistant",
        single_column: true,
    });

    page.main.addClass("kpi-tracking-app");
    page._specialist = "productivity";
    page._chat_history = [];

    // Check user context for Admin authorization
    frappe.xcall("productix_kpi.kpi_tracking.api.dashboard.get_user_context").then((ctx) => {
        page._ctx = ctx || {};
        if (!ctx.is_admin) {
            frappe.show_alert({ message: "AI Assistant is restricted to administrators.", indicator: "orange" });
            frappe.set_route("kpi-department-dashboard");
            return;
        }

        setup_ai_page_actions(page);
        render_chat(page);
        load_suggestions(page);
    }).catch(() => {
        frappe.set_route("kpi-department-dashboard");
    });
};

function setup_ai_page_actions(page) {
    if (page.clear_inner_toolbar) page.clear_inner_toolbar();
    if (page.clear_menu) page.clear_menu();

    page.set_primary_action("📢 Send Alert to Department", () => show_send_alert_dialog(page), "fa fa-bullhorn");
    page.set_secondary_action("🏢 Company Overview", () => frappe.set_route("kpi-company-overview"), "fa fa-building");

    page.add_inner_button("🚨 Action Center", () => frappe.set_route("kpi-action-center"));
    page.add_inner_button("✍️ Data Entry", () => frappe.set_route("kpi-data-entry-page"));

    // Populate 3-dot dropdown menu
    page.add_menu_item("🏠 Workspace Home", () => frappe.set_route("company-tracking-system"));
    page.add_menu_item("📢 Send Alert to Department", () => show_send_alert_dialog(page));
    page.add_menu_item("🏢 Company Overview", () => frappe.set_route("kpi-company-overview"));
    page.add_menu_item("🚨 Action & Alert Center", () => frappe.set_route("kpi-action-center"));
    page.add_menu_item("✍️ Metric Data Entry", () => frappe.set_route("kpi-data-entry-page"));
    page.add_menu_item("🗑️ Clear Chat History", () => {
        page._chat_history = [];
        page.main.find("#ai-messages").html(`
            <div class="kpi-tracking-ai-message kpi-tracking-ai-message--ai" style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:16px 20px;box-shadow:0 1px 3px rgba(0,0,0,0.03);line-height:1.7;font-size:13.5px;color:#0f172a;">
                <strong>👋 Hello! I am your KPI &amp; Operations virtual assistant.</strong><br>
                <span>How can I help you today? Feel free to ask about department performance, missing data submissions, bottlenecks, or operational metrics.</span>
            </div>
        `);
    });
    page.add_menu_item("⚙️ KPI Settings", () => frappe.set_route("Form", "KPI Settings"));
}

function render_chat(page) {
    const specialists = [
        { key: "productivity", label: "🏭 Productivity & Operations" },
        { key: "energy", label: "⚡ Energy & Utilities" },
        { key: "hr", label: "👥 Human Capital & Labor" },
        { key: "process", label: "⚙️ Process & Quality" },
    ];

    let tabs = specialists.map((s) => {
        const active = s.key === page._specialist ? "active" : "";
        return `<button class="kpi-tracking-ai-tab ${active}" data-specialist="${s.key}" style="font-weight:600;padding:8px 18px;border-radius:8px;font-size:13px;">${s.label}</button>`;
    }).join('');

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
                <div style="display:flex;align-items:center;gap:10px;">
                    <span class="badge badge-success" style="font-size:11px;padding:4px 10px;font-weight:600;">⚡ AI Assistant Active</span>
                    <div style="font-size:12px;color:#64748b;">
                        Admin Mode · <strong>${page._ctx.full_name || 'Admin'}</strong>
                    </div>
                </div>
            </div>

            <!-- Hero Header Banner -->
            <div style="background:linear-gradient(135deg, #0f172a 0%, #1e293b 60%, #334155 100%);border-radius:14px;padding:26px 30px;color:#fff;margin-bottom:24px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:18px;box-shadow:0 4px 6px -1px rgba(0,0,0,0.1);">
                <div>
                    <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
                        <span style="background:rgba(56,189,248,0.2);color:#38bdf8;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700;letter-spacing:0.5px;text-transform:uppercase;">
                            🤖 Intelligent Enterprise Assistant
                        </span>
                        <span class="productix-status-pulse"></span>
                    </div>
                    <h1 style="margin:0 0 6px 0;font-size:22px;font-weight:700;color:#fff;">
                        <span>KPI Operations &amp; Diagnostic Virtual Assistant</span>
                    </h1>
                    <p style="margin:0;font-size:13px;color:#94a3b8;">
                        Ask questions naturally to analyze department bottlenecks, audit missing data submissions, and dispatch directives.
                    </p>
                </div>
                <div style="display:flex;gap:8px;flex-wrap:wrap;">
                    <button class="btn btn-sm btn-primary" id="btn-quick-alert" style="font-weight:600;padding:6px 14px;">
                        <i class="fa fa-bullhorn mr-1"></i> Send Alert
                    </button>
                    <button class="btn btn-sm btn-default" id="btn-clear-chat" style="color:#fff;background:rgba(255,255,255,0.12);border:1px solid rgba(255,255,255,0.2);font-weight:500;">
                        <i class="fa fa-trash mr-1"></i> Clear Chat
                    </button>
                </div>
            </div>

            <!-- Specialist Persona Tabs -->
            <div class="kpi-tracking-ai-tabs mb-3" style="display:flex;gap:8px;flex-wrap:wrap;">
                ${tabs}
            </div>

            <!-- Prompt Suggestions -->
            <div class="card mb-3" style="border:1px solid #e2e8f0;border-radius:10px;background:#fff;box-shadow:0 1px 2px rgba(0,0,0,0.02);">
                <div class="card-body" style="padding:12px 18px;display:flex;align-items:center;flex-wrap:wrap;gap:6px;">
                    <span style="font-size:12px;font-weight:700;color:#475569;margin-right:6px;"><i class="fa fa-lightbulb-o text-warning mr-1"></i> Suggested Questions:</span>
                    <span id="ai-suggestions" style="display:inline-flex;flex-wrap:wrap;gap:6px;"></span>
                </div>
            </div>

            <!-- Chat Window -->
            <div class="card" style="border:1px solid #e2e8f0;border-radius:12px;box-shadow:0 2px 4px rgba(0,0,0,0.03);background:#fff;overflow:hidden;">
                <div class="kpi-tracking-ai-chat" id="ai-chat-area" style="min-height:420px;max-height:62vh;overflow-y:auto;padding:24px;background:#f8fafc;">
                    <div class="kpi-tracking-ai-messages" id="ai-messages" style="display:flex;flex-direction:column;gap:16px;">
                        <div class="kpi-tracking-ai-message kpi-tracking-ai-message--ai" style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:16px 20px;max-width:88%;align-self:flex-start;color:#0f172a;box-shadow:0 1px 3px rgba(0,0,0,0.03);font-size:13.5px;line-height:1.7;">
                            <strong>👋 Hello! I am your KPI &amp; Operations virtual assistant.</strong><br>
                            <span style="color:#475569;">How can I help you today? Feel free to ask about department performance, missing data submissions, bottlenecks, or operational metrics.</span>
                        </div>
                    </div>
                </div>

                <!-- Input Box -->
                <div style="padding:16px 20px;background:#fff;border-top:1px solid #e2e8f0;">
                    <div class="input-group">
                        <input type="text" class="form-control" id="ai-question" placeholder="Type your message here... (e.g. 'Hi', 'Which departments have missing data entries?', 'What are our critical KPIs?')" style="padding:12px 16px;font-size:13.5px;border-radius:8px 0 0 8px;border-color:#cbd5e1;">
                        <div class="input-group-append">
                            <button class="btn btn-primary" id="ai-send" style="font-weight:600;padding:0 24px;border-radius:0 8px 8px 0;">
                                <i class="fa fa-paper-plane mr-1"></i> Send
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

    page.main.html(html);

    page.main.find(".kpi-tracking-ai-tab").on("click", function () {
        page._specialist = $(this).data("specialist");
        page.main.find(".kpi-tracking-ai-tab").removeClass("active");
        $(this).addClass("active");
        load_suggestions(page);
    });

    page.main.find("#btn-quick-alert").on("click", () => show_send_alert_dialog(page));

    page.main.find("#btn-clear-chat").on("click", function() {
        page._chat_history = [];
        page.main.find("#ai-messages").html(`
            <div class="kpi-tracking-ai-message kpi-tracking-ai-message--ai" style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:16px 20px;box-shadow:0 1px 3px rgba(0,0,0,0.03);line-height:1.7;font-size:13.5px;color:#0f172a;">
                <strong>👋 Hello! I am your KPI &amp; Operations virtual assistant.</strong><br>
                <span>How can I help you today? Feel free to ask about department performance, missing data submissions, bottlenecks, or operational metrics.</span>
            </div>
        `);
    });

    page.main.find("#ai-send").on("click", () => send_question(page));
    page.main.find("#ai-question").on("keypress", (e) => {
        if (e.which === 13) send_question(page);
    });
}

function load_suggestions(page) {
    frappe.xcall("productix_kpi.kpi_tracking.api.ai_assistant.get_suggestions", {
        specialist_type: page._specialist,
    }).then((questions) => {
        let html = "";
        (questions || []).forEach((q) => {
            html += `<span class="kpi-tracking-suggestion-chip" style="font-size:12px;padding:5px 13px;border-radius:16px;background:#f1f5f9;color:#334155;border:1px solid #e2e8f0;cursor:pointer;display:inline-block;transition:all 0.15s ease;">${q}</span>`;
        });
        page.main.find("#ai-suggestions").html(html);
        page.main.find(".kpi-tracking-suggestion-chip").on("click", function () {
            page.main.find("#ai-question").val($(this).text());
            send_question(page);
        });
    });
}

function send_question(page) {
    const question = page.main.find("#ai-question").val().trim();
    if (!question) return;

    add_message(page, "user", question);
    page._chat_history.push({ role: "user", content: question });
    page.main.find("#ai-question").val("");

    const loading_id = add_message(page, "ai", '<i class="fa fa-spinner fa-spin mr-2"></i> Thinking...');

    frappe.xcall("productix_kpi.kpi_tracking.api.ai_assistant.ask_ai", {
        specialist_type: page._specialist,
        question: question,
        history: page._chat_history,
    }).then((r) => {
        page.main.find(`#${loading_id}`).remove();
        if (r.error) {
            add_message(page, "ai", `<div class="text-danger font-weight-bold">⚠️ ${r.error}</div>`);
        } else {
            let replyText = r.response || "";
            page._chat_history.push({ role: "assistant", content: replyText });
            let formatted = render_clean_markdown(replyText);

            if (replyText.toLowerCase().includes("missing") || replyText.toLowerCase().includes("pending entries") || replyText.toLowerCase().includes("send alert")) {
                formatted += `
                    <div style="margin-top:14px;padding-top:10px;border-top:1px solid #e2e8f0;display:flex;gap:8px;">
                        <button class="btn btn-xs btn-primary ai-action-send-alert-btn" style="font-weight:600;padding:4px 10px;">
                            📢 Send Alert to Affected Department
                        </button>
                    </div>
                `;
            }

            add_message(page, "ai", formatted);

            page.main.find(".ai-action-send-alert-btn").last().on("click", function () {
                show_send_alert_dialog(page);
            });
        }
    }).catch((err) => {
        page.main.find(`#${loading_id}`).remove();
        add_message(page, "ai", `<div class="text-danger">⚠️ ${err.message || 'Unable to retrieve AI response.'}</div>`);
    });
}

function show_send_alert_dialog(page) {
    frappe.xcall("productix_kpi.kpi_tracking.api.dashboard.get_user_context").then((ctx) => {
        const departments = ctx.department_list || [];

        let deptOptionsList = ["All Departments"];
        departments.forEach(d => {
            if (!deptOptionsList.includes(d.name)) {
                deptOptionsList.push(d.name);
            }
        });

        const d = new frappe.ui.Dialog({
            title: "📢 Dispatch Management Alert to Department Employees",
            size: "large",
            fields: [
                {
                    fieldtype: "Select",
                    fieldname: "department",
                    label: "Target Department",
                    reqd: 1,
                    options: deptOptionsList.join('\n'),
                    default: "All Departments",
                },
                {
                    fieldtype: "Select",
                    fieldname: "severity",
                    label: "Alert Severity",
                    options: "Info\nWarning\nCritical",
                    default: "Info",
                },
                {
                    fieldtype: "Small Text",
                    fieldname: "message",
                    label: "Alert Message Directive",
                    reqd: 1,
                    default: "KPI data entry is pending for your department. Please complete the required entries for the current reporting period.",
                },
            ],
            primary_action_label: "Send Alert",
            primary_action: function (values) {
                if (!values.department || !values.message) {
                    frappe.msgprint("Please select a department and enter an alert message.");
                    return;
                }

                frappe.xcall("productix_kpi.kpi_tracking.services.alert_engine.dispatch_ai_department_alert", {
                    department: values.department === "All Departments" ? "ALL" : values.department,
                    message: values.message,
                    severity: values.severity || "Info",
                }).then((res) => {
                    if (res.status === "warning") {
                        frappe.msgprint(res.message);
                    } else {
                        frappe.show_alert({
                            message: `✅ [${res.severity || 'Info'}] Alert dispatched to ${res.count} employee(s) in ${res.department}!`,
                            indicator: "green",
                        });
                        d.hide();
                    }
                }).catch((err) => {
                    frappe.show_alert({ message: "Error dispatching alert: " + (err.message || ""), indicator: "red" });
                });
            }
        });

        d.show();
    });
}

function add_message(page, type, content) {
    const id = "msg-" + Date.now() + "-" + Math.random().toString(36).slice(2, 6);
    const cls = type === "user" ? "kpi-tracking-ai-message--user" : "kpi-tracking-ai-message--ai";
    const bg = type === "user"
        ? "background:#2563eb;color:#fff;border-radius:12px;padding:12px 18px;max-width:80%;align-self:flex-end;font-size:13.5px;line-height:1.5;box-shadow:0 1px 2px rgba(0,0,0,0.08);"
        : "background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:16px 20px;max-width:88%;align-self:flex-start;color:#0f172a;box-shadow:0 1px 3px rgba(0,0,0,0.03);font-size:13.5px;line-height:1.7;";

    page.main.find("#ai-messages").append(
        `<div class="kpi-tracking-ai-message ${cls}" id="${id}" style="${bg}">${content}</div>`
    );
    const container = page.main.find("#ai-chat-area");
    container.scrollTop(container[0].scrollHeight);
    return id;
}

function render_clean_markdown(md) {
    if (!md) return "";
    if (window.marked) {
        return marked.parse(md);
    }
    // Clean formatted fallback
    return md
        .replace(/^### (.*$)/gim, '<h4 style="font-weight:700;font-size:14.5px;margin:12px 0 6px;color:#0f172a;">$1</h4>')
        .replace(/^## (.*$)/gim, '<h3 style="font-weight:700;font-size:15.5px;margin:14px 0 8px;color:#0f172a;">$1</h3>')
        .replace(/^# (.*$)/gim, '<h2 style="font-weight:800;font-size:17px;margin:16px 0 10px;color:#0f172a;">$1</h2>')
        .replace(/\*\*(.*?)\*\*/gim, '<strong style="color:#0f172a;">$1</strong>')
        .replace(/\*(.*?)\*/gim, '<em>$1</em>')
        .replace(/^[•\-\*] (.*$)/gim, '<div style="margin:4px 0;display:flex;align-items:flex-start;"><span style="color:#2563eb;margin-right:8px;font-size:14px;">•</span><span>$1</span></div>')
        .replace(/\n\n/gim, '<div style="margin-bottom:10px;"></div>')
        .replace(/\n/gim, '<br>');
}
