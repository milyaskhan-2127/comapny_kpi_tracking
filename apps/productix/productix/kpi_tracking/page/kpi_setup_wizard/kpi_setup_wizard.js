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
        page.add_menu_item("💾 Backup & Restore Manager", () => frappe.set_route("backups"));
        page.add_menu_item("⚙️ KPI Settings", () => frappe.set_route("Form", "KPI Settings"));
        load_wizard(page);
    }).catch(() => {
        frappe.set_route("kpi-department-dashboard");
    });
};

function load_wizard(page) {
    page.main.html('<div class="text-center p-5"><i class="fa fa-spinner fa-spin fa-2x text-primary"></i><p class="mt-2 text-muted">Loading Setup Wizard...</p></div>');

    frappe.xcall("productix.kpi_tracking.api.setup.get_setup_status").then((data) => {
        render_wizard(page, data);
    }).catch((err) => {
        page.main.html('<div class="alert alert-danger m-4">Failed to load setup wizard status: ' + (err.message || "Unknown error") + '</div>');
    });
}

function render_wizard(page, data) {
    const currentSettings = data.settings || {};
    const companies = data.companies || [];
    const fiscal_years = data.fiscal_years || [];
    const currencies = data.currencies || ["PKR", "USD", "EUR", "GBP", "AED", "SAR", "INR", "CAD"];
    const existingDepts = data.departments || [];

    // Map existing departments by code and name for quick lookup
    const existingDeptMap = {};
    existingDepts.forEach(d => {
        if (d.department_code) existingDeptMap[d.department_code.toUpperCase()] = d;
        if (d.name) existingDeptMap[d.name.toUpperCase()] = d;
    });

    // Standard baseline departments
    const standardDepts = [
        { name: "Production", code: "PRODUCTION", icon: "🏭", default_weight: 1.5 },
        { name: "Quality Control", code: "QC", icon: "🧪", default_weight: 1.3 },
        { name: "Safety", code: "SAFETY", icon: "🛡️", default_weight: 1.0 },
        { name: "Procurement", code: "PROCUREMENT", icon: "📦", default_weight: 1.0 },
        { name: "Supply Chain", code: "SUPPLY_CHAIN", icon: "🚚", default_weight: 1.1 },
        { name: "Sales", code: "SALES", icon: "💼", default_weight: 1.2 },
        { name: "R&D", code: "RND", icon: "🔬", default_weight: 1.0 },
        { name: "Finance", code: "FINANCE", icon: "💰", default_weight: 1.1 },
        { name: "Human Resources", code: "HR", icon: "👥", default_weight: 1.0 },
        { name: "Customer Support & Success", code: "CUSTOMER_SUCCESS", icon: "🎧", default_weight: 1.1 },
    ];

    // Build unified department list (standard + custom)
    const combinedDepts = [];
    const handledCodes = new Set();

    standardDepts.forEach(sd => {
        const exist = existingDeptMap[sd.code];
        combinedDepts.push({
            name: exist ? (exist.department_name || sd.name) : sd.name,
            code: exist ? (exist.department_code || exist.name || sd.code) : sd.code,
            location: exist ? (exist.location || "") : "",
            icon: sd.icon,
            weight: exist ? (exist.weight != null ? exist.weight : sd.default_weight) : sd.default_weight,
            is_active: exist ? (exist.is_active != null ? exist.is_active : 1) : 1,
            is_existing: !!exist,
            kpi_count: exist ? (exist.kpi_count || 0) : 0,
            is_standard: true,
        });
        handledCodes.add(sd.code);
        if (exist && exist.name) handledCodes.add(exist.name.toUpperCase());
        if (exist && exist.department_code) handledCodes.add(exist.department_code.toUpperCase());
    });

    // Add any custom existing departments (preserves departments with distinct codes even if names match)
    existingDepts.forEach(ed => {
        const codeUpper = (ed.department_code || ed.name).toUpperCase();
        if (!handledCodes.has(codeUpper)) {
            combinedDepts.push({
                name: ed.department_name || ed.name,
                code: ed.department_code || ed.name,
                location: ed.location || "",
                icon: "🏢",
                weight: ed.weight != null ? ed.weight : 1.0,
                is_active: ed.is_active != null ? ed.is_active : 1,
                is_existing: true,
                kpi_count: ed.kpi_count || 0,
                is_standard: false,
            });
            handledCodes.add(codeUpper);
        }
    });

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

    // Department cards HTML in Step 2
    let deptCardsHtml = combinedDepts.map(d => {
        const isChecked = d.is_active ? 'checked' : '';
        const statusBadge = d.is_active
            ? `<span class="badge badge-success" style="font-size:10px;padding:3px 6px;">Active ✅</span>`
            : `<span class="badge badge-secondary" style="font-size:10px;padding:3px 6px;">Inactive ⏸️</span>`;
        const kpiBadge = d.kpi_count > 0
            ? `<span class="badge badge-info" style="font-size:10px;padding:3px 6px;">${d.kpi_count} KPIs</span>`
            : '';

        const locTag = d.location
            ? `<div style="font-size:11px;color:#64748b;margin-left:21px;margin-top:2px;">📍 <span>${frappe.utils.escape_html(d.location)}</span></div>`
            : '';

        return `
            <div class="dept-item-card" style="border:1px solid ${d.is_active ? '#cbd5e1' : '#e2e8f0'};background:${d.is_active ? '#ffffff' : '#f8fafc'};border-radius:8px;padding:12px;display:flex;flex-direction:column;justify-content:space-between;gap:8px;">
                <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:8px;">
                    <div>
                        <label style="font-size:13px;font-weight:600;color:#1e293b;margin:0;cursor:pointer;display:flex;align-items:center;gap:6px;">
                            <input type="checkbox" class="dept-check" data-name="${frappe.utils.escape_html(d.name)}" data-code="${frappe.utils.escape_html(d.code)}" ${isChecked} style="cursor:pointer;width:15px;height:15px;">
                            <span>${d.icon} ${frappe.utils.escape_html(d.name)}</span>
                        </label>
                        ${locTag}
                    </div>
                    <div style="display:flex;gap:4px;align-items:center;">
                        ${kpiBadge}
                        ${statusBadge}
                    </div>
                </div>
                <div style="display:flex;align-items:center;justify-content:space-between;font-size:11px;color:#64748b;padding-top:4px;border-top:1px dashed #e2e8f0;">
                    <span>Code: <code>${frappe.utils.escape_html(d.code)}</code></span>
                    <div style="display:flex;align-items:center;gap:4px;">
                        <span>Weight:</span>
                        <input type="number" step="0.1" min="0" class="form-control form-control-sm dept-weight-input" data-code="${frappe.utils.escape_html(d.code)}" value="${d.weight}" style="width:60px;height:24px;padding:2px 4px;font-size:11px;text-align:center;">
                    </div>
                </div>
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
                <div style="display:flex;align-items:center;gap:16px;">
                    <button class="btn btn-sm btn-outline-info text-white" id="btn-quick-setup" style="font-weight:600;border-color:rgba(255,255,255,0.4);" title="Automatically configure standard company, 9 departments, and all KPI templates in 1 click">
                        ⚡ 1-Click Quick Setup
                    </button>
                    <div style="text-align:right;">
                        <span style="font-size:22px;font-weight:800;color:#38bdf8;">${data.percentage}%</span>
                        <div style="font-size:11px;text-transform:uppercase;color:#94a3b8;">${data.completed}/${data.total} Steps Complete</div>
                    </div>
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
                                <input type="text" id="wizard-company-custom" class="form-control" placeholder="e.g. My Company" value="${currentSettings.company || ''}">
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
                                <option value="Quarterly" ${currentSettings.default_frequency === 'Quarterly' ? 'selected' : ''}>Quarterly</option>
                                <option value="Yearly" ${currentSettings.default_frequency === 'Yearly' ? 'selected' : ''}>Yearly</option>
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

            <!-- Step 2: Operational Departments Card -->
            <div class="card mb-4" style="border:1px solid #e2e8f0;border-radius:10px;box-shadow:0 1px 3px rgba(0,0,0,0.04);">
                <div class="card-body" style="padding:20px 24px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;flex-wrap:wrap;gap:10px;">
                        <div>
                            <h5 style="margin:0;font-weight:700;font-size:15px;color:#0f172a;">🏭 Step 2: Operational Departments</h5>
                            <span class="text-muted" style="font-size:12px;">Activate standard departments or create custom departments with weights</span>
                        </div>
                        <div style="display:flex;gap:8px;">
                            <button class="btn btn-xs btn-default" id="btn-select-all-depts" style="font-size:11px;">Select All</button>
                            <button class="btn btn-xs btn-default" id="btn-deselect-all-depts" style="font-size:11px;">Deselect All</button>
                        </div>
                    </div>

                    <!-- Department Cards Grid -->
                    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px;margin-bottom:20px;">
                        ${deptCardsHtml}
                    </div>

                    <!-- Inline Custom Department Creation Form -->
                    <div style="background:#f1f5f9;border:1px solid #cbd5e1;border-radius:8px;padding:14px;margin-bottom:16px;">
                        <div style="font-size:13px;font-weight:700;color:#1e293b;margin-bottom:10px;display:flex;align-items:center;gap:6px;">
                            <span>➕ Add Custom Operational Department</span>
                        </div>
                        <div class="row align-items-end">
                            <div class="col-md-3 mb-2">
                                <label style="font-size:11px;font-weight:600;color:#475569;margin-bottom:4px;">Department Name</label>
                                <input type="text" id="new-dept-name" class="form-control form-control-sm" placeholder="e.g. Sales, Quality Control">
                            </div>
                            <div class="col-md-3 mb-2">
                                <label style="font-size:11px;font-weight:600;color:#475569;margin-bottom:4px;">Location / Block</label>
                                <input type="text" id="new-dept-location" class="form-control form-control-sm" placeholder="e.g. Block 1, Plant B">
                            </div>
                            <div class="col-md-2 mb-2">
                                <label style="font-size:11px;font-weight:600;color:#475569;margin-bottom:4px;">Code</label>
                                <input type="text" id="new-dept-code" class="form-control form-control-sm" placeholder="e.g. SAL_B1, QC_P2">
                            </div>
                            <div class="col-md-2 mb-2">
                                <label style="font-size:11px;font-weight:600;color:#475569;margin-bottom:4px;">Weight</label>
                                <input type="number" step="0.1" min="0" id="new-dept-weight" class="form-control form-control-sm" value="1.0">
                            </div>
                            <div class="col-md-2 mb-2">
                                <button class="btn btn-sm btn-primary btn-block" id="btn-add-single-dept" style="font-weight:600;">
                                    ➕ Add
                                </button>
                            </div>
                        </div>
                    </div>

                    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">
                        <span id="dept-result-msg" style="font-size:12px;"></span>
                        <button class="btn btn-sm btn-success" id="btn-create-depts" style="font-weight:600;">
                            💾 Save &amp; Activate Selected Departments
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
                        Deploys standard KPI benchmarks (Production, QC, Safety, Procurement, Supply Chain, Sales, R&amp;D, Finance, HR) with target values and calculation rules aligned with the chosen Company Frequency.
                    </p>

                    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">
                        <span id="template-result-msg" style="font-size:12px;"></span>
                        <button class="btn btn-sm btn-primary" id="btn-deploy-templates" style="font-weight:600;">
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

    // Event handler: Auto-suggest Department Code when typing Department Name
    page.main.find("#new-dept-name").on("input", function () {
        const val = $(this).val() || "";
        const codeInput = page.main.find("#new-dept-code");
        if (!codeInput.data("user-edited")) {
            let suggested = val.toUpperCase().trim();
            suggested = suggested.replace(/&/g, "AND").replace(/[^A-Z0-9]/g, "_").replace(/_+/g, "_").replace(/^_|_$/g, "");
            if (suggested && !/^[A-Z]/.test(suggested)) {
                suggested = "DEP_" + suggested;
            }
            codeInput.val(suggested);
        }
    });

    page.main.find("#new-dept-code").on("input", function () {
        $(this).data("user-edited", true);
    });

    // Event handler: Quick Setup 1-Click
    page.main.find("#btn-quick-setup").on("click", function () {
        frappe.confirm(
            "Run 1-Click Quick Setup? This will configure standard Company settings, activate all 9 baseline operational departments, and deploy standard KPI benchmark templates.",
            () => {
                const cur = page.main.find("#wizard-currency-select").val() || "PKR";
                const comp = page.main.find("#wizard-company-select").val() || null;
                frappe.show_alert({ message: "Running Quick Setup...", indicator: "blue" });

                frappe.xcall("productix.kpi_tracking.api.setup.one_click_quick_setup", {
                    company_name: comp,
                    currency: cur,
                }).then((r) => {
                    frappe.show_alert({ message: `Quick Setup Complete! Activated ${r.departments_count} departments and deployed ${r.kpis_created} KPIs.`, indicator: "green" });
                    load_wizard(page);
                }).catch((err) => {
                    frappe.show_alert({ message: "Error during quick setup: " + (err.message || ""), indicator: "red" });
                });
            }
        );
    });

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
        const freq = page.main.find("#wizard-freq-select").val() || "Daily";

        const btn = $(this);
        btn.prop("disabled", true).html('<i class="fa fa-spinner fa-spin"></i> Saving...');

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

    // Event handler: Select All / Deselect All departments
    page.main.find("#btn-select-all-depts").on("click", function () {
        page.main.find(".dept-check").prop("checked", true);
    });
    page.main.find("#btn-deselect-all-depts").on("click", function () {
        page.main.find(".dept-check").prop("checked", false);
    });

    // Event handler: Add single custom department
    page.main.find("#btn-add-single-dept").on("click", function () {
        const dName = (page.main.find("#new-dept-name").val() || "").trim();
        const dLoc = (page.main.find("#new-dept-location").val() || "").trim();
        const dCode = (page.main.find("#new-dept-code").val() || "").trim();
        const dWeight = parseFloat(page.main.find("#new-dept-weight").val()) || 1.0;

        if (!dName) {
            frappe.show_alert({ message: "Please enter a Department Name", indicator: "orange" });
            page.main.find("#new-dept-name").focus();
            return;
        }

        const btn = $(this);
        btn.prop("disabled", true).html('<i class="fa fa-spinner fa-spin"></i>');

        frappe.xcall("productix.kpi_tracking.api.setup.create_or_update_department", {
            department_name: dName,
            department_code: dCode,
            location: dLoc,
            weight: dWeight,
            is_active: 1,
        }).then((r) => {
            frappe.show_alert({ message: `Department '${r.department_name}' (${r.department_code}) created successfully!`, indicator: "green" });
            load_wizard(page);
        }).catch((err) => {
            btn.prop("disabled", false).html("➕ Add");
            frappe.show_alert({ message: "Error creating department: " + (err.message || ""), indicator: "red" });
        });
    });

    // Event handler: Save & Activate Selected Departments
    page.main.find("#btn-create-depts").on("click", function () {
        const deptPayload = [];
        page.main.find(".dept-check").each(function () {
            const isChecked = $(this).is(":checked");
            const dCode = $(this).data("code");
            const dName = $(this).data("name");
            const weightInput = page.main.find(`.dept-weight-input[data-code="${dCode}"]`);
            const weightVal = weightInput.length ? parseFloat(weightInput.val()) || 1.0 : 1.0;

            deptPayload.push({
                name: dName,
                code: dCode,
                weight: weightVal,
                is_active: isChecked ? 1 : 0,
            });
        });

        if (deptPayload.length === 0) {
            frappe.show_alert({ message: "No departments to configure.", indicator: "orange" });
            return;
        }

        const btn = $(this);
        btn.prop("disabled", true).html('<i class="fa fa-spinner fa-spin"></i> Saving...');

        frappe.xcall("productix.kpi_tracking.api.setup.setup_departments", { departments: deptPayload }).then((r) => {
            page.main.find("#dept-result-msg").html(`<span class="text-success font-weight-bold">✅ Saved ${r.count || r.created.length} departments</span>`);
            frappe.show_alert({ message: __("Successfully updated {0} departments", [r.count || r.created.length]), indicator: "green" });
            load_wizard(page);
        }).catch((err) => {
            btn.prop("disabled", false).html("💾 Save & Activate Selected Departments");
            frappe.show_alert({ message: "Error updating departments: " + (err.message || ""), indicator: "red" });
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
        }).catch((err) => {
            btn.prop("disabled", false).html("🚀 Deploy Templates & KPIs");
            frappe.show_alert({ message: "Error deploying templates: " + (err.message || ""), indicator: "red" });
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
