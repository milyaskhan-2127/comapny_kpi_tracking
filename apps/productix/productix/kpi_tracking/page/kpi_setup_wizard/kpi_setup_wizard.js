// Productix KPI Tracking — Performance Setup Wizard (Admin Only)

frappe.pages["kpi-setup-wizard"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "KPI Performance Setup Wizard",
        single_column: true,
    });

    page.main.addClass("kpi-tracking-app");

    frappe.xcall("productix.kpi_tracking.api.dashboard.get_user_context").then((ctx) => {
        page._ctx = ctx || {};
        if (!ctx.is_admin) {
            frappe.show_alert({ message: "Setup Wizard is restricted to administrators.", indicator: "orange" });
            frappe.set_route("kpi-department-dashboard");
            return;
        }

        if (page.clear_inner_toolbar) page.clear_inner_toolbar();
        if (page.clear_menu) page.clear_menu();

        page.set_primary_action("🏢 Company Overview", () => frappe.set_route("kpi-company-overview"), "fa fa-building");
        page.set_secondary_action("🔄 Refresh", () => load_wizard(page), "fa fa-sync");

        page.add_menu_item("🔄 Refresh Wizard", () => load_wizard(page));
        page.add_menu_item("🏢 Company Performance Overview", () => frappe.set_route("kpi-company-overview"));
        page.add_menu_item("⚙️ KPI Settings", () => frappe.set_route("Form", "KPI Settings"));
        load_wizard(page);
    }).catch(() => {
        frappe.set_route("kpi-department-dashboard");
    });
};

function load_wizard(page) {
    page.main.html('<div class="text-center p-5"><i class="fa fa-spinner fa-spin fa-2x"></i><p class="mt-2 text-muted">Loading Setup Wizard...</p></div>');

    frappe.xcall("productix.kpi_tracking.api.setup.get_setup_status").then((data) => {
        render_wizard(page, data);
    }).catch((err) => {
        page.main.html('<div class="alert alert-danger m-4">Failed to load setup wizard status.</div>');
    });
}

function render_wizard(page, data) {
    const currentSettings = data.settings || {};
    const companies = data.companies || [];
    const fiscal_years = data.fiscal_years || [];
    const currencies = data.currencies || ["PKR", "USD", "EUR", "GBP", "AED", "SAR", "INR", "CAD"];

    let companyOptionsHtml = '';
    if (companies.length > 0) {
        companies.forEach(c => {
            const isSel = (c === currentSettings.company) ? 'selected' : '';
            companyOptionsHtml += `<option value="${c}" ${isSel}>${c}</option>`;
        });
        companyOptionsHtml += `<option value="__new__">+ Enter New Company Name...</option>`;
    }

    let fyOptionsHtml = fiscal_years.map(fy => `
        <option value="${fy}" ${fy === currentSettings.fiscal_year ? 'selected' : ''}>${fy}</option>
    `).join('');

    let currOptionsHtml = currencies.map(cur => {
        const isSel = (cur === (currentSettings.currency || "PKR")) ? 'selected' : '';
        return `<option value="${cur}" ${isSel}>${cur}</option>`;
    }).join('');

    let stepPillsHtml = (data.steps || []).map(s => {
        let badgeClass = s.status === 'complete' ? 'badge-success' : s.status === 'warning' ? 'badge-warning' : 'badge-secondary';
        let icon = s.status === 'complete' ? '✅' : s.status === 'warning' ? '⚠️' : '⏳';
        return `
            <div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:10px 14px;display:flex;align-items:center;justify-content:space-between;min-width:180px;">
                <span style="font-size:13px;font-weight:600;color:#334155;">${icon} ${s.step}</span>
                <span class="badge ${badgeClass}" style="font-size:11px;">${s.count != null ? s.count : s.status}</span>
            </div>
        `;
    }).join('');

    let html = `
        <div style="max-width:960px;margin:0 auto;padding:10px 0 40px;">
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

            <!-- Header Card -->
            <div style="background:linear-gradient(135deg,#1e293b 0%,#334155 100%);border-radius:12px;padding:24px 28px;color:#fff;margin-bottom:20px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:16px;">
                <div>
                    <h2 style="margin:0 0 6px 0;font-size:20px;font-weight:700;color:#fff;">🎯 Productix KPI &amp; Performance Setup</h2>
                    <p style="margin:0;font-size:13px;color:#94a3b8;">Dynamic initialization for company targets, operational departments, and KPI metrics.</p>
                </div>
                <div style="text-align:right;">
                    <span style="font-size:22px;font-weight:800;color:#38bdf8;">${data.percentage}%</span>
                    <div style="font-size:11px;text-transform:uppercase;color:#94a3b8;">${data.completed}/${data.total} Steps Complete</div>
                </div>
            </div>

            <!-- Steps Summary Grid -->
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin-bottom:24px;">
                ${stepPillsHtml}
            </div>

            <!-- Step 1: Company Configuration Card -->
            <div class="card mb-4" style="border:1px solid #e2e8f0;border-radius:10px;box-shadow:0 1px 3px rgba(0,0,0,0.04);">
                <div class="card-body" style="padding:20px 24px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
                        <h5 style="margin:0;font-weight:700;font-size:15px;color:#0f172a;">🏢 Step 1: Company Settings</h5>
                        ${currentSettings.company ? `<span class="badge badge-success" style="font-size:12px;">Active: ${currentSettings.company} (${currentSettings.currency || 'PKR'} · ${currentSettings.default_frequency || 'Daily'})</span>` : '<span class="badge badge-warning">Pending Configuration</span>'}
                    </div>

                    <div class="row">
                        <div class="col-md-4 mb-3">
                            <label style="font-size:12px;font-weight:600;color:#475569;">Company Name</label>
                            ${companies.length > 0 ? `
                                <select id="wizard-company-select" class="form-control">
                                    ${companyOptionsHtml}
                                </select>
                                <input type="text" id="wizard-company-custom" class="form-control mt-2" placeholder="Enter new company name..." style="display:none;">
                            ` : `
                                <input type="text" id="wizard-company-custom" class="form-control" placeholder="e.g. Apex Chemical Industries" value="${currentSettings.company || ''}">
                            `}
                        </div>
                        <div class="col-md-3 mb-3">
                            <label style="font-size:12px;font-weight:600;color:#475569;">Fiscal Year</label>
                            <select id="wizard-fy-select" class="form-control">
                                ${fyOptionsHtml}
                            </select>
                        </div>
                        <div class="col-md-2 mb-3">
                            <label style="font-size:12px;font-weight:600;color:#475569;">Default Currency</label>
                            <select id="wizard-currency-select" class="form-control">
                                ${currOptionsHtml}
                            </select>
                        </div>
                        <div class="col-md-3 mb-3">
                            <label style="font-size:12px;font-weight:600;color:#475569;">Default Data Frequency</label>
                            <select id="wizard-freq-select" class="form-control">
                                <option value="Daily" ${(!currentSettings.default_frequency || currentSettings.default_frequency === 'Daily') ? 'selected' : ''}>Daily</option>
                                <option value="Weekly" ${currentSettings.default_frequency === 'Weekly' ? 'selected' : ''}>Weekly</option>
                                <option value="Monthly" ${currentSettings.default_frequency === 'Monthly' ? 'selected' : ''}>Monthly</option>
                            </select>
                        </div>
                    </div>
                    <div style="font-size:11px;color:#64748b;margin-bottom:12px;">
                        💡 <em>Note:</em> The Default Data Frequency set here controls all operational department dashboards and metric submission cycles across the organization.
                    </div>

                    <div style="display:flex;justify-content:flex-end;">
                        <button class="btn btn-sm btn-primary" id="btn-save-company" style="font-weight:600;">
                            💾 Save Company Settings
                        </button>
                    </div>
                </div>
            </div>

            <!-- Step 2: Departments Card -->
            <div class="card mb-4" style="border:1px solid #e2e8f0;border-radius:10px;box-shadow:0 1px 3px rgba(0,0,0,0.04);">
                <div class="card-body" style="padding:20px 24px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
                        <h5 style="margin:0;font-weight:700;font-size:15px;color:#0f172a;">🏭 Step 2: Operational Departments</h5>
                        <span class="text-muted" style="font-size:12px;">Select all departments to activate</span>
                    </div>

                    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px;margin-bottom:16px;">
                        <label style="font-size:13px;color:#334155;"><input type="checkbox" class="dept-check" data-name="Production" data-code="PRODUCTION" data-weight="1.5" checked> 🏭 Production (Weight: 1.5)</label>
                        <label style="font-size:13px;color:#334155;"><input type="checkbox" class="dept-check" data-name="Quality Control" data-code="QC" data-weight="1.3" checked> 🧪 Quality Control (1.3)</label>
                        <label style="font-size:13px;color:#334155;"><input type="checkbox" class="dept-check" data-name="Safety" data-code="SAFETY" data-weight="1.0" checked> 🛡️ Safety (1.0)</label>
                        <label style="font-size:13px;color:#334155;"><input type="checkbox" class="dept-check" data-name="Procurement" data-code="PROCUREMENT" data-weight="1.0" checked> 📦 Procurement (1.0)</label>
                        <label style="font-size:13px;color:#334155;"><input type="checkbox" class="dept-check" data-name="Supply Chain" data-code="SUPPLY_CHAIN" data-weight="1.1" checked> 🚚 Supply Chain (1.1)</label>
                        <label style="font-size:13px;color:#334155;"><input type="checkbox" class="dept-check" data-name="Sales" data-code="SALES" data-weight="1.2" checked> 💼 Sales (1.2)</label>
                        <label style="font-size:13px;color:#334155;"><input type="checkbox" class="dept-check" data-name="R&amp;D" data-code="RND" data-weight="1.0" checked> 🔬 R&amp;D (1.0)</label>
                        <label style="font-size:13px;color:#334155;"><input type="checkbox" class="dept-check" data-name="Finance" data-code="FINANCE" data-weight="1.1" checked> 💰 Finance (1.1)</label>
                        <label style="font-size:13px;color:#334155;"><input type="checkbox" class="dept-check" data-name="Human Resources" data-code="HR" data-weight="1.0" checked> 👥 HR (1.0)</label>
                    </div>

                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <span id="dept-result-msg" style="font-size:12px;"></span>
                        <button class="btn btn-sm btn-default" id="btn-create-depts" style="font-weight:600;">
                            ➕ Create / Activate Selected Departments
                        </button>
                    </div>
                </div>
            </div>

            <!-- Step 3: Templates & KPIs Card -->
            <div class="card mb-4" style="border:1px solid #e2e8f0;border-radius:10px;box-shadow:0 1px 3px rgba(0,0,0,0.04);">
                <div class="card-body" style="padding:20px 24px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
                        <h5 style="margin:0;font-weight:700;font-size:15px;color:#0f172a;">📊 Step 3: KPI Templates &amp; Definitions</h5>
                        <span class="text-muted" style="font-size:12px;">Deploy templates across all active departments</span>
                    </div>

                    <p style="font-size:13px;color:#64748b;margin-bottom:14px;">
                        Deploys standard KPI benchmarks (Production, QC, Safety, Procurement, Supply Chain, Sales, R&amp;D, Finance, HR) with target values and calculation rules.
                    </p>

                    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">
                        <span id="template-result-msg" style="font-size:12px;"></span>
                        <button class="btn btn-sm btn-default" id="btn-deploy-templates" style="font-weight:600;">
                            🚀 Deploy Templates &amp; KPIs
                        </button>
                    </div>
                </div>
            </div>

            <!-- Final Completion Card -->
            <div class="card" style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;">
                <div class="card-body" style="padding:24px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:14px;">
                    <div>
                        <h5 style="margin:0 0 4px 0;font-weight:700;font-size:15px;color:#0f172a;">🚀 Ready to Track Performance?</h5>
                        <p style="margin:0;font-size:13px;color:#64748b;">Open your live KPI Company Dashboard to monitor all department indices.</p>
                    </div>
                    <div style="display:flex;gap:10px;">
                        <button class="btn btn-success" id="btn-finalize-setup" style="font-weight:700;">
                            ✅ Mark Complete &amp; Open KPI Dashboard →
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;

    page.main.html(html);

    // Event handler: Company dropdown switch
    page.main.find("#wizard-company-select").on("change", function () {
        if ($(this).val() === "__new__") {
            page.main.find("#wizard-company-custom").show().focus();
        } else {
            page.main.find("#wizard-company-custom").hide();
        }
    });

    // Event handler: Save Company Settings
    page.main.find("#btn-save-company").on("click", function () {
        let compName = page.main.find("#wizard-company-select").val();
        if (!compName || compName === "__new__") {
            compName = page.main.find("#wizard-company-custom").val();
        }
        if (!compName || !compName.trim()) {
            frappe.show_alert({ message: "Please select or enter a Company name", indicator: "orange" });
            return;
        }

        const fy = page.main.find("#wizard-fy-select").val();
        const cur = page.main.find("#wizard-currency-select").val() || "PKR";

        const btn = $(this);
        btn.prop("disabled", true).html('<i class="fa fa-spinner fa-spin"></i> Saving...');

        const freq = page.main.find("#wizard-freq-select").val() || "Monthly";

        frappe.xcall("productix.kpi_tracking.api.setup.setup_company", {
            company: compName.trim(),
            fiscal_year: fy,
            currency: cur,
            default_frequency: freq,
        }).then((r) => {
            frappe.show_alert({ message: __("Company settings saved: {0} ({1})", [r.company, r.currency]), indicator: "green" });
            load_wizard(page);
        }).catch((err) => {
            btn.prop("disabled", false).html("💾 Save Company Settings");
            frappe.show_alert({ message: __("Error saving company: " + (err.message || "")), indicator: "red" });
        });
    });

    // Event handler: Create Departments
    page.main.find("#btn-create-depts").on("click", function () {
        const selected = [];
        page.main.find(".dept-check:checked").each(function () {
            selected.push({
                name: $(this).data("name"),
                code: $(this).data("code"),
                weight: $(this).data("weight") || 1.0,
            });
        });

        if (selected.length === 0) {
            frappe.show_alert({ message: "Please select at least one department", indicator: "orange" });
            return;
        }

        const btn = $(this);
        btn.prop("disabled", true).html('<i class="fa fa-spinner fa-spin"></i> Creating...');

        frappe.xcall("productix.kpi_tracking.api.setup.setup_departments", { departments: selected }).then((r) => {
            page.main.find("#dept-result-msg").html(`<span class="text-success font-weight-bold">✅ Created/Verified ${r.created.length} departments</span>`);
            frappe.show_alert({ message: __("Created/Verified {0} departments", [r.created.length]), indicator: "green" });
            load_wizard(page);
        }).catch(() => {
            btn.prop("disabled", false).html("➕ Create / Activate Selected Departments");
        });
    });

    // Event handler: Deploy Templates & KPIs
    page.main.find("#btn-deploy-templates").on("click", function () {
        const btn = $(this);
        btn.prop("disabled", true).html('<i class="fa fa-spinner fa-spin"></i> Deploying...');

        frappe.xcall("productix.kpi_tracking.api.setup.apply_all_default_templates").then((r) => {
            page.main.find("#template-result-msg").html(`<span class="text-success font-weight-bold">✅ Deployed ${r.count} KPIs across active templates!</span>`);
            frappe.show_alert({ message: __("Deployed {0} KPIs across active templates!", [r.count]), indicator: "green" });
            load_wizard(page);
        }).catch(() => {
            btn.prop("disabled", false).html("🚀 Deploy Templates & KPIs");
        });
    });

    // Event handler: Finalize Setup
    page.main.find("#btn-finalize-setup").on("click", function () {
        frappe.xcall("productix.kpi_tracking.api.setup.complete_setup").then(() => {
            frappe.show_alert({ message: "Setup completed successfully!", indicator: "green" });
            frappe.set_route("kpi-company-overview");
        });
    });
}
