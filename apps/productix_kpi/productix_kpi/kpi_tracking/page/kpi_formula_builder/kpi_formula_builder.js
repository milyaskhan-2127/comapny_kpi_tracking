// Productix KPI Tracking — Formula Builder Page (Admin Only)

frappe.pages["kpi-formula-builder"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "KPI Formula Builder",
        single_column: true,
    });

    page.main.addClass("kpi-tracking-app");

    frappe.xcall("productix_kpi.kpi_tracking.api.dashboard.get_user_context").then((ctx) => {
        page._ctx = ctx || {};
        if (!ctx.is_admin) {
            frappe.show_alert({ message: "Formula Builder is restricted to administrators.", indicator: "orange" });
            frappe.set_route("kpi-department-dashboard");
            return;
        }

        if (page.clear_inner_toolbar) page.clear_inner_toolbar();
        if (page.clear_menu) page.clear_menu();

        page.set_primary_action("🏢 Company Overview", () => frappe.set_route("kpi-company-overview"), "fa fa-building");
        page.set_secondary_action("🔄 Refresh", () => render_builder(page), "fa fa-sync");

        page.add_menu_item("🔄 Refresh Builder", () => render_builder(page));
        page.add_menu_item("🏢 Company Performance Overview", () => frappe.set_route("kpi-company-overview"));
        page.add_menu_item("📦 KPI Variables List", () => frappe.set_route("List", "KPI Variable"));
        page.add_menu_item("📐 KPI Formulas List", () => frappe.set_route("List", "KPI Formula"));
        render_builder(page);
    }).catch(() => {
        frappe.set_route("kpi-department-dashboard");
    });
};

function render_builder(page) {
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
                            📐 Formula Engine (Admin Only)
                        </span>
                        <span class="productix-status-pulse"></span>
                    </div>
                    <h1 style="margin:0 0 6px 0;font-size:22px;font-weight:700;color:#fff;">
                        <span>KPI Formula Builder &amp; Evaluator</span>
                    </h1>
                    <p style="margin:0;font-size:13px;color:#94a3b8;">
                        Compose mathematical equations, custom aggregations, and variable expressions.
                    </p>
                </div>
                <div>
                    <button class="btn btn-sm btn-default" onclick="frappe.set_route('List', 'KPI Variable')" style="color:#fff;background:rgba(255,255,255,0.15);border:1px solid rgba(255,255,255,0.25);">
                        ➕ Manage Variables
                    </button>
                </div>
            </div>

            <div class="row">
                <!-- Left Column: Variables & Function Keypad -->
                <div class="col-md-4 mb-4">
                    <div class="card mb-3" style="border:1px solid #e2e8f0;border-radius:10px;box-shadow:0 1px 3px rgba(0,0,0,0.03);">
                        <div class="card-body" style="padding:18px;">
                            <h5 style="margin:0 0 12px 0;font-size:14px;font-weight:700;color:#0f172a;">📦 Available Variables</h5>
                            <input type="text" id="var-search" class="form-control form-control-sm mb-2" placeholder="Search variables...">
                            <div id="var-list" style="max-height:220px;overflow-y:auto;padding-right:4px;">
                                <div class="text-center p-3 text-muted"><i class="fa fa-spinner fa-spin"></i> Loading...</div>
                            </div>
                        </div>
                    </div>

                    <div class="card" style="border:1px solid #e2e8f0;border-radius:10px;box-shadow:0 1px 3px rgba(0,0,0,0.03);">
                        <div class="card-body" style="padding:18px;">
                            <h5 style="margin:0 0 10px 0;font-size:14px;font-weight:700;color:#0f172a;">Functions</h5>
                            <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:14px;">
                                <button class="btn btn-xs btn-default fb-func" data-func="SUM(">SUM</button>
                                <button class="btn btn-xs btn-default fb-func" data-func="AVG(">AVG</button>
                                <button class="btn btn-xs btn-default fb-func" data-func="MIN(">MIN</button>
                                <button class="btn btn-xs btn-default fb-func" data-func="MAX(">MAX</button>
                                <button class="btn btn-xs btn-default fb-func" data-func="COUNT(">COUNT</button>
                                <button class="btn btn-xs btn-default fb-func" data-func="ABS(">ABS</button>
                                <button class="btn btn-xs btn-default fb-func" data-func="ROUND(">ROUND</button>
                                <button class="btn btn-xs btn-default fb-func" data-func="IF(">IF</button>
                            </div>

                            <h5 style="margin:0 0 10px 0;font-size:14px;font-weight:700;color:#0f172a;">Operators</h5>
                            <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;">
                                <button class="btn btn-xs btn-default fb-func" data-func=" + ">+</button>
                                <button class="btn btn-xs btn-default fb-func" data-func=" - ">−</button>
                                <button class="btn btn-xs btn-default fb-func" data-func=" * ">×</button>
                                <button class="btn btn-xs btn-default fb-func" data-func=" / ">÷</button>
                                <button class="btn btn-xs btn-default fb-func" data-func="(">(</button>
                                <button class="btn btn-xs btn-default fb-func" data-func=")">)</button>
                                <button class="btn btn-xs btn-default fb-func" data-func=", ">,</button>
                                <button class="btn btn-xs btn-default fb-func" data-func=" ^ ">^</button>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Right Column: Formula Details & Code Editor -->
                <div class="col-md-8">
                    <div class="card mb-4" style="border:1px solid #e2e8f0;border-radius:10px;box-shadow:0 1px 3px rgba(0,0,0,0.03);">
                        <div class="card-body" style="padding:22px;">
                            <h5 style="margin:0 0 16px 0;font-size:15px;font-weight:700;color:#0f172a;">✏️ Formula Definition</h5>

                            <div class="row">
                                <div class="col-md-6 mb-3">
                                    <label style="font-size:12px;font-weight:600;color:#475569;">Formula Name *</label>
                                    <input type="text" id="fb-formula-name" class="form-control" placeholder="e.g. Net Production Yield">
                                </div>
                                <div class="col-md-6 mb-3">
                                    <label style="font-size:12px;font-weight:600;color:#475569;">Formula Code *</label>
                                    <input type="text" id="fb-formula-code" class="form-control" placeholder="e.g. NET_PROD_YIELD">
                                </div>
                                <div class="col-md-6 mb-3">
                                    <label style="font-size:12px;font-weight:600;color:#475569;">Result Unit</label>
                                    <input type="text" id="fb-result-unit" class="form-control" placeholder="e.g. % or kg">
                                </div>
                                <div class="col-md-6 mb-3">
                                    <label style="font-size:12px;font-weight:600;color:#475569;">Result Label</label>
                                    <input type="text" id="fb-result-label" class="form-control" placeholder="e.g. Yield Percentage">
                                </div>
                            </div>

                            <div class="mb-3">
                                <label style="font-size:12px;font-weight:600;color:#475569;">Expression Syntax *</label>
                                <textarea id="formula-expr" class="form-control font-monospace" rows="3" placeholder="e.g. (TOTAL_OUTPUT - SCRAP_QTY) / TOTAL_INPUT * 100" style="font-family:monospace;font-size:13px;"></textarea>
                            </div>

                            <div style="display:flex;justify-content:space-between;align-items:center;">
                                <button class="btn btn-sm btn-default" id="btn-clear-formula">Clear Form</button>
                                <button class="btn btn-sm btn-primary" id="btn-save-formula" style="font-weight:600;">💾 Save Formula</button>
                            </div>
                        </div>
                    </div>

                    <!-- Existing Formulas Library -->
                    <div class="card" style="border:1px solid #e2e8f0;border-radius:10px;box-shadow:0 1px 3px rgba(0,0,0,0.03);">
                        <div class="card-body" style="padding:22px;">
                            <h5 style="margin:0 0 14px 0;font-size:15px;font-weight:700;color:#0f172a;">📚 Saved Formulas Library</h5>
                            <div id="formula-library" class="table-responsive">
                                <div class="text-center p-3 text-muted"><i class="fa fa-spinner fa-spin"></i></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

    page.main.html(html);

    load_variables(page);
    load_formulas(page);

    page.main.find(".fb-func").on("click", function () {
        const expr = page.main.find("#formula-expr");
        expr.val(expr.val() + $(this).data("func"));
        expr.focus();
    });

    page.main.find("#btn-clear-formula").on("click", () => {
        page.main.find("#formula-expr").val("");
        page.main.find("#fb-formula-name").val("");
        page.main.find("#fb-formula-code").val("");
        page.main.find("#fb-result-unit").val("");
        page.main.find("#fb-result-label").val("");
        page.main.find(".var-check").prop("checked", false);
    });

    page.main.find("#btn-save-formula").on("click", () => save_formula(page));
}

function load_variables(page) {
    frappe.xcall("frappe.client.get_list", {
        doctype: "KPI Variable",
        fields: ["name", "variable_name", "variable_code", "unit"],
        limit_page_length: 100,
        order_by: "variable_name asc",
    }).then((vars) => {
        let html = "";
        (vars || []).forEach((v) => {
            html += `
                <div class="kpi-tracking-var-item" style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid #f1f5f9;">
                    <div>
                        <label style="margin:0;font-size:12px;font-weight:600;color:#334155;cursor:pointer;">
                            <input type="checkbox" class="var-check mr-1" data-code="${v.variable_code}" data-name="${v.name}">
                            ${v.variable_name}
                        </label>
                        <code style="font-size:10px;display:block;color:#6366f1;">${v.variable_code}</code>
                    </div>
                    <button class="btn btn-xs btn-default insert-var" data-code="${v.variable_code}" title="Insert into formula" style="font-size:10px;padding:2px 6px;">+ Add</button>
                </div>
            `;
        });
        if (!vars || vars.length === 0) {
            html = '<p class="text-muted p-2" style="font-size:12px;">No variables defined. <a href="/app/kpi-variable/new">Create one</a></p>';
        }
        page.main.find("#var-list").html(html);

        page.main.find(".insert-var").on("click", function () {
            const code = $(this).data("code");
            const expr = page.main.find("#formula-expr");
            expr.val(expr.val() + code);
            expr.focus();
        });
    });
}

function load_formulas(page) {
    frappe.xcall("frappe.client.get_list", {
        doctype: "KPI Formula",
        fields: ["name", "formula_name", "formula_code", "expression", "result_unit", "is_active"],
        limit_page_length: 50,
        order_by: "formula_name asc",
    }).then((formulas) => {
        let rows = (formulas || []).map(f => `
            <tr>
                <td><strong>${f.formula_name}</strong></td>
                <td><code style="color:#2563eb;">${f.formula_code}</code></td>
                <td><span style="font-family:monospace;font-size:11px;color:#334155;">${f.expression || ""}</span></td>
                <td>${f.result_unit || "—"}</td>
                <td><span class="badge ${f.is_active ? 'badge-success' : 'badge-secondary'}">${f.is_active ? "Active" : "Inactive"}</span></td>
            </tr>
        `).join('');

        let html = `
            <table class="table table-sm table-hover" style="font-size:12px;margin:0;">
                <thead><tr style="background:#f8fafc;"><th>Name</th><th>Code</th><th>Expression</th><th>Unit</th><th>Status</th></tr></thead>
                <tbody>${rows}</tbody>
            </table>
        `;
        if (!formulas || formulas.length === 0) html = '<p class="text-muted p-2" style="font-size:12px;">No formulas created yet.</p>';
        page.main.find("#formula-library").html(html);
    });
}

function save_formula(page) {
    const formulaName = page.main.find("#fb-formula-name").val().trim();
    let formulaCode = page.main.find("#fb-formula-code").val().trim();
    const resultUnit = page.main.find("#fb-result-unit").val().trim();
    const resultLabel = page.main.find("#fb-result-label").val().trim();
    const expression = page.main.find("#formula-expr").val().trim();

    if (!formulaName) {
        frappe.show_alert({ message: "Formula name is required", indicator: "orange" });
        return;
    }
    if (!formulaCode) {
        formulaCode = formulaName.toUpperCase().replace(/\s+/g, "_");
    }
    if (!expression) {
        frappe.show_alert({ message: "Formula expression cannot be empty", indicator: "orange" });
        return;
    }

    const selected_vars = [];
    page.main.find(".var-check:checked").each(function () {
        selected_vars.push({ variable: $(this).data("name"), variable_code: $(this).data("code") });
    });

    frappe.xcall("frappe.client.insert", {
        doc: {
            doctype: "KPI Formula",
            formula_name: formulaName,
            formula_code: formulaCode.toUpperCase().replace(/\s+/g, "_"),
            expression: expression,
            result_unit: resultUnit,
            result_label: resultLabel,
            is_active: 1,
            variables: selected_vars,
        },
    }).then((doc) => {
        frappe.show_alert({ message: `✅ Formula ${doc.name} saved successfully!`, indicator: "green" });
        load_formulas(page);
        page.main.find("#btn-clear-formula").click();
    }).catch((err) => {
        frappe.show_alert({ message: "Error saving formula: " + (err.message || ""), indicator: "red" });
    });
}
