/* ============================================================
   Productix ERP — Dynamic Role-Based Visual Dashboard Page
   Provides customized command centers for:
   - Factory Admin / System Manager
   - Production Manager
   - Store Keeper / Inventory Manager
   - Purchase Manager / Procurement
   - General Staff / Floor Operator
   ============================================================ */

frappe.pages['recipe-dashboard'].on_page_load = function(wrapper) {
    let page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __('Productix Command Center'),
        single_column: true
    });

    wrapper.productix_page = page;
    wrapper.current_view_role = null; // default: auto-detect from user roles

    page.set_secondary_action(__('🔄 Sync / Refresh'), function() {
        render_dashboard(page, wrapper.current_view_role);
    });

    render_dashboard(page, wrapper.current_view_role);
};

function render_dashboard(page, activeRoleOverride) {
    let $container = $(page.main);
    $container.empty();

    $container.html(`
        <div class="productix-page-dashboard" style="padding: 10px 0 40px;">
            <div id="px-hero-section"></div>
            <div id="px-alert-section"></div>

            <!-- Charts & Analytics Section (Analytics & Trends on top after Operational Notice) -->
            <div class="row" style="margin-bottom: 24px;" id="px-charts-row">
                <div class="col-md-6 col-sm-12" style="margin-bottom: 16px;">
                    <div class="productix-chart-box" style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                        <div class="productix-box-header" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                            <span class="productix-box-title" id="px-chart-1-title" style="font-weight:700;font-size:14px;color:#0f172a;">📊 Production Runs by Status</span>
                            <span class="badge" style="background:#dbeafe;color:#1e40af;font-size:11px;">Live Sync</span>
                        </div>
                        <div id="px-chart-orders" style="height: 250px; display: flex; align-items: center; justify-content: center;"></div>
                    </div>
                </div>
                <div class="col-md-6 col-sm-12" style="margin-bottom: 16px;">
                    <div class="productix-chart-box" style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                        <div class="productix-box-header" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                            <span class="productix-box-title" id="px-chart-2-title" style="font-weight:700;font-size:14px;color:#0f172a;">🧪 Formulations by Category</span>
                            <span class="badge" style="background:#f1f5f9;color:#334155;font-size:11px;">Catalog</span>
                        </div>
                        <div id="px-chart-recipes" style="height: 250px; display: flex; align-items: center; justify-content: center;"></div>
                    </div>
                </div>
            </div>

            <!-- KPI Cards Section -->
            <div id="px-kpi-cards"></div>

            <!-- Operations Command Hub (Role-Tailored Tabs) -->
            <div class="productix-hub-wrapper" style="margin-bottom: 24px;" id="px-hub-section">
                <div id="px-hub-tabs-container"></div>
                <div id="px-hub-content-container"></div>
            </div>

            <!-- Operations Center (Recent Activity & Production Runs) -->
            <div class="row">
                <div class="col-md-7 col-sm-12" style="margin-bottom: 16px;">
                    <div class="productix-card-panel" style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                        <div class="productix-box-header" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                            <span class="productix-box-title" style="font-weight:700;font-size:14px;color:#0f172a;">🏭 Formulation Runs &amp; Queue</span>
                            <a href="/app/production-order" class="btn btn-xs btn-default">View All →</a>
                        </div>
                        <div id="px-orders-table-wrapper" class="table-responsive">
                            <div class="text-center text-muted p-4">Loading formulation runs...</div>
                        </div>
                    </div>
                </div>
                <div class="col-md-5 col-sm-12" style="margin-bottom: 16px;">
                    <div class="productix-card-panel" style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                        <div class="productix-box-header" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                            <span class="productix-box-title" style="font-weight:700;font-size:14px;color:#0f172a;">📜 Live User Activity &amp; Audit Log</span>
                            <a href="/app/ai-agent-log" class="btn btn-xs btn-default">Full Audit Log →</a>
                        </div>
                        <div id="px-activity-wrapper" style="max-height: 380px; overflow-y: auto;">
                            <div class="text-center text-muted p-4">Loading user activity stream...</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `);

    // Fetch dashboard and role data
    frappe.call({
        method: 'productix.api.inventory.get_dashboard_kpis',
        args: { role_override: activeRoleOverride },
        callback: function(r) {
            if (!r.message) return;
            let d = r.message;
            let roleCtx = d.role_context || {};
            let role = activeRoleOverride || d.active_role || roleCtx.primary_role || 'admin';

            // Setup top action buttons
            try { setup_page_buttons(page, roleCtx, role); } catch (e) { console.error('Error in setup_page_buttons:', e); }

            // Render Hero Banner
            try { render_hero(d, roleCtx, role, page); } catch (e) { console.error('Error in render_hero:', e); }

            // Render Alert Banner
            try { render_alerts(d); } catch (e) { console.error('Error in render_alerts:', e); }

            // Render KPI Cards tailored by role
            try { render_kpis(d, role); } catch (e) { console.error('Error in render_kpis:', e); }

            // Render Charts
            try { render_charts(d, role); } catch (e) { console.error('Error in render_charts:', e); }

            // Render Tabs and fast action grid
            try { render_hub_tabs(roleCtx, role); } catch (e) { console.error('Error in render_hub_tabs:', e); }

            // Render Recent Orders Table directly from response
            try { load_recent_orders(d.recent_orders || []); } catch (e) { console.error('Error in load_recent_orders:', e); }

            // Render Live Activity Stream directly from response
            try { render_activity_stream(d.recent_activity || []); } catch (e) { console.error('Error in render_activity_stream:', e); }
        }
    });
}

function setup_page_buttons(page, roleCtx, role) {
    page.clear_inner_buttons();

    if (roleCtx.can_create_recipe) {
        page.add_inner_button(__('➕ New Recipe'), function() {
            frappe.set_route('Form', 'Recipe', 'new-recipe-1');
        }, __('Quick Action')).addClass('btn-primary');
    }

    if (roleCtx.can_create_production_order) {
        page.add_inner_button(__('⚡ New Production Run'), function() {
            frappe.set_route('Form', 'Production Order', 'new-production-order-1');
        }, __('Quick Action'));
    }

    if (roleCtx.can_receive_grn) {
        page.add_inner_button(__('📥 Stock In'), function() {
            frappe.set_route('Form', 'Purchase Receipt', 'new-purchase-receipt-1');
        }, __('Quick Action'));
    }

    if (roleCtx.is_purchase || roleCtx.is_admin) {
        page.add_inner_button(__('📜 GRN History'), function() {
            frappe.set_route('query-report', 'Purchasing Report');
        }, __('Quick Action'));
    }

    if (roleCtx.can_manage_roles) {
        page.add_inner_button(__('👤 Staff Directory'), function() {
            frappe.set_route('List', 'User');
        }, __('Admin'));
    }
}

function render_hero(d, roleCtx, role, page) {
    let roleLabels = {
        'factory_admin': { label: 'Factory Admin', icon: '👑', colorClass: 'px-role-chip-admin', desc: 'Full Factory Command & Control Center' },
        'admin': { label: 'Factory Admin', icon: '👑', colorClass: 'px-role-chip-admin', desc: 'Full Factory Command & Control Center' },
        'asst_admin': { label: 'Assistant System Administrator', icon: '🛡️', colorClass: 'px-role-chip-admin', desc: 'Managing staff directory, operational logs, and reporting' },
        'production': { label: 'Production Manager', icon: '🏭', colorClass: 'px-role-chip-production', desc: 'Oversees manufacturing workflows, recipe engineering, and batch assembly' },
        'store': { label: 'Store Keeper', icon: '📦', colorClass: 'px-role-chip-store', desc: 'Handles physical inventory, warehouse receiving, and batch expiration' },
        'purchase': { label: 'Purchase Manager', icon: '🤝', colorClass: 'px-role-chip-purchase', desc: 'Governs supplier relations, ingredient sourcing, and purchase fulfillment' },
        'staff': { label: 'General Staff / Auditor', icon: '👷', colorClass: 'px-role-chip-staff', desc: 'View dashboards, stock levels, production history & instruction room' },
    };

    let curRoleInfo = roleLabels[role] || roleLabels['admin'];
    let userName = roleCtx.full_name || frappe.session.user;

    // Role-specific action buttons dynamically generated from permissions
    let heroActionButtons = '';
    if (roleCtx.can_create_recipe) {
        heroActionButtons += `<a href="/app/recipe/new" class="btn btn-sm btn-primary" style="background:#2563eb;border:none;"><span>➕ New Recipe</span></a>`;
    }
    if (roleCtx.can_create_production_order) {
        heroActionButtons += `<a href="/app/production-order/new" class="btn btn-sm btn-success" style="background:#16a34a;border:none;"><span>⚡ New Run</span></a>`;
    }
    if (roleCtx.can_receive_grn) {
        heroActionButtons += `<a href="/app/purchase-receipt/new" class="btn btn-sm btn-info" style="background:#0891b2;border:none;"><span>📦 Receive GRN</span></a>`;
    }
    if (roleCtx.can_adjust_stock && !roleCtx.can_receive_grn) {
        heroActionButtons += `<a href="/app/stock-entry" class="btn btn-sm btn-warning" style="background:#d97706;border:none;color:#fff;"><span>🔄 Stock Entry</span></a>`;
    }
    if (roleCtx.can_create_supplier && !roleCtx.can_create_recipe) {
        heroActionButtons += `<a href="/app/supplier/new" class="btn btn-sm btn-primary" style="background:#2563eb;border:none;"><span>🏢 New Supplier</span></a>`;
    }
    if (roleCtx.can_manage_roles) {
        heroActionButtons += `<a href="/app/user" class="btn btn-sm btn-default" style="background:#334155;color:#fff;border:none;"><span>👤 Staff Directory</span></a>`;
    }
    if (roleCtx.can_read_production_order && !roleCtx.can_create_production_order) {
        heroActionButtons += `<a href="/app/production-order" class="btn btn-sm btn-success" style="background:#16a34a;border:none;"><span>🏭 Today's Queue</span></a>`;
    }
    if (!roleCtx.can_create_recipe && roleCtx.can_read_recipe) {
        heroActionButtons += `<a href="/app/recipe" class="btn btn-sm btn-primary" style="background:#2563eb;border:none;"><span>📖 Recipes</span></a>`;
    }

    $('#px-hero-section').html(`
        <div class="productix-hero-banner" style="background:linear-gradient(135deg, #0f172a 0%, #1e293b 60%, #334155 100%);border-radius:12px;padding:24px 28px;color:#fff;margin-bottom:20px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:16px;">
            <div>
                <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;flex-wrap:wrap;">
                    <span class="px-role-chip ${curRoleInfo.colorClass}">
                        <span>${curRoleInfo.icon}</span> ${curRoleInfo.label}
                    </span>
                    <span class="productix-status-pulse"></span>
                </div>
                <h1 class="productix-hero-title" style="margin:0;font-size:22px;font-weight:700;color:#fff;">
                    <span>🍳 Productix Recipe Management</span>
                </h1>
                <div style="margin-top:12px;display:flex;gap:10px;flex-wrap:wrap;">
                    ${heroActionButtons}
                </div>
            </div>
            <div style="text-align:right;">
                <div class="px-user-badge-corner" style="background:rgba(255,255,255,0.12);border:1px solid rgba(255,255,255,0.25);border-radius:10px;padding:10px 18px;display:inline-flex;align-items:center;gap:12px;backdrop-filter:blur(4px);">
                    <span style="font-size:24px;">👤</span>
                    <div style="text-align:left;">
                        <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.5px;color:#94a3b8;font-weight:600;">Active User</div>
                        <div style="font-size:18px;font-weight:800;color:#ffffff;line-height:1.2;">${userName}</div>
                    </div>
                </div>
            </div>
        </div>
    `);

    // Handle role preview switches
    $('#px-hero-section .px-role-btn').on('click', function() {
        let selectedRole = $(this).data('role');
        render_dashboard(page, selectedRole);
    });
}

function render_alerts(d) {
    if (d.low_stock_count > 0 || d.expiry_alert_count > 0) {
        let msgs = [];
        if (d.low_stock_count > 0) msgs.push(`<strong>${d.low_stock_count}</strong> material(s) below minimum safety stock`);
        if (d.expiry_alert_count > 0) msgs.push(`<strong>${d.expiry_alert_count}</strong> batch(es) near or past expiry`);
        $('#px-alert-section').html(`
            <div class="productix-alert-banner productix-alert-warning" style="background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:12px 16px;margin-bottom:20px;display:flex;justify-content:space-between;align-items:center;color:#92400e;">
                <div>⚠️ <strong>Operational Notice:</strong> ${msgs.join(' &nbsp;|&nbsp; ')}</div>
                <div style="display:flex;gap:8px;">
                    <a href="/app/query-report/Inventory%20Status%20Report" class="btn btn-xs btn-default">Inventory Report</a>
                    <a href="/app/query-report/Batch%20Expiry%20Report" class="btn btn-xs btn-default">Expiry Report</a>
                </div>
            </div>
        `);
    } else {
        $('#px-alert-section').empty();
    }
}

function render_kpis(d, role) {
    let valFormatted = parseFloat(d.total_stock_value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    let inProgressCount = (d.order_status_counts && d.order_status_counts['In Progress']) || 0;
    let pendingCount = (d.order_status_counts && d.order_status_counts['Pending']) || 0;
    let completedCount = (d.order_status_counts && d.order_status_counts['Completed']) || 0;

    let kpiHtml = '';

    if (role === 'production') {
        kpiHtml = `
            <a href="/app/production-order" class="productix-kpi-card" style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px;text-decoration:none!important;color:inherit;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-size:12px;color:#64748b;font-weight:600;">
                    <span>Active Runs In-Progress</span><span style="font-size:16px;">⚡</span>
                </div>
                <div style="font-size:26px;font-weight:700;color:#2563eb;">${inProgressCount}</div>
                <div style="font-size:11px;color:#94a3b8;margin-top:4px;">Currently blending on floor</div>
            </a>
            <a href="/app/production-order" class="productix-kpi-card" style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px;text-decoration:none!important;color:inherit;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-size:12px;color:#64748b;font-weight:600;">
                    <span>Pending Queue</span><span style="font-size:16px;">⏳</span>
                </div>
                <div style="font-size:26px;font-weight:700;color:#f59e0b;">${pendingCount}</div>
                <div style="font-size:11px;color:#94a3b8;margin-top:4px;">Awaiting material batching</div>
            </a>
            <a href="/app/production-order" class="productix-kpi-card" style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px;text-decoration:none!important;color:inherit;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-size:12px;color:#64748b;font-weight:600;">
                    <span>Completed Batches</span><span style="font-size:16px;">✅</span>
                </div>
                <div style="font-size:26px;font-weight:700;color:#10b981;">${completedCount}</div>
                <div style="font-size:11px;color:#94a3b8;margin-top:4px;">Total successful runs</div>
            </a>
            <a href="/app/recipe" class="productix-kpi-card" style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px;text-decoration:none!important;color:inherit;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-size:12px;color:#64748b;font-weight:600;">
                    <span>Total Formulations</span><span style="font-size:16px;">🧪</span>
                </div>
                <div style="font-size:26px;font-weight:700;color:#0f172a;">${d.total_recipes || 0}</div>
                <div style="font-size:11px;color:#94a3b8;margin-top:4px;">Active standard BOMs</div>
            </a>
            <a href="/app/query-report/Inventory%20Status%20Report" class="productix-kpi-card" style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px;text-decoration:none!important;color:inherit;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-size:12px;color:#64748b;font-weight:600;">
                    <span>Material Alerts</span><span style="font-size:16px;">⚠️</span>
                </div>
                <div style="font-size:26px;font-weight:700;color:${d.low_stock_count > 0 ? '#ef4444' : '#10b981'};">${d.low_stock_count || 0}</div>
                <div style="font-size:11px;color:#94a3b8;margin-top:4px;">${d.low_stock_count > 0 ? 'Low ingredient stock' : 'Sufficient stocks'}</div>
            </a>
        `;
    } else if (role === 'store') {
        kpiHtml = `
            <a href="/app/item" class="productix-kpi-card" style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px;text-decoration:none!important;color:inherit;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-size:12px;color:#64748b;font-weight:600;">
                    <span>Active Raw Materials</span><span style="font-size:16px;">📦</span>
                </div>
                <div style="font-size:26px;font-weight:700;color:#0f172a;">${d.total_items || 0}</div>
                <div style="font-size:11px;color:#94a3b8;margin-top:4px;">In-stock inventory items</div>
            </a>
            <a href="/app/batch" class="productix-kpi-card" style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px;text-decoration:none!important;color:inherit;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-size:12px;color:#64748b;font-weight:600;">
                    <span>Batches Tracked</span><span style="font-size:16px;">🏷️</span>
                </div>
                <div style="font-size:26px;font-weight:700;color:#0f172a;">${d.total_batches || 0}</div>
                <div style="font-size:11px;color:#94a3b8;margin-top:4px;">Active inventory lots</div>
            </a>
            <a href="/app/query-report/Inventory%20Status%20Report" class="productix-kpi-card" style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px;text-decoration:none!important;color:inherit;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-size:12px;color:#64748b;font-weight:600;">
                    <span>Low Stock Shortages</span><span style="font-size:16px;">⚠️</span>
                </div>
                <div style="font-size:26px;font-weight:700;color:${d.low_stock_count > 0 ? '#ef4444' : '#10b981'};">${d.low_stock_count || 0}</div>
                <div style="font-size:11px;color:#94a3b8;margin-top:4px;">Below safety reorder level</div>
            </a>
            <a href="/app/query-report/Batch%20Expiry%20Report" class="productix-kpi-card" style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px;text-decoration:none!important;color:inherit;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-size:12px;color:#64748b;font-weight:600;">
                    <span>Expiring Batches (≤7d)</span><span style="font-size:16px;">⏰</span>
                </div>
                <div style="font-size:26px;font-weight:700;color:${d.expiry_alert_count > 0 ? '#d97706' : '#10b981'};">${d.expiry_alert_count || 0}</div>
                <div style="font-size:11px;color:#94a3b8;margin-top:4px;">FEFO prioritization needed</div>
            </a>
            <a href="/app/query-report/Stock%20Ledger" class="productix-kpi-card" style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px;text-decoration:none!important;color:inherit;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-size:12px;color:#64748b;font-weight:600;">
                    <span>Stock Asset Value</span><span style="font-size:16px;">💰</span>
                </div>
                <div style="font-size:26px;font-weight:700;color:#0f172a;">$${valFormatted}</div>
                <div style="font-size:11px;color:#94a3b8;margin-top:4px;">Warehouse asset valuation</div>
            </a>
        `;
    } else if (role === 'purchase') {
        kpiHtml = `
            <a href="/app/supplier" class="productix-kpi-card" style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px;text-decoration:none!important;color:inherit;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-size:12px;color:#64748b;font-weight:600;">
                    <span>Active Suppliers</span><span style="font-size:16px;">🏢</span>
                </div>
                <div style="font-size:26px;font-weight:700;color:#0f172a;">${d.total_suppliers || 0}</div>
                <div style="font-size:11px;color:#94a3b8;margin-top:4px;">Verified chemical vendors</div>
            </a>
            <a href="/app/query-report/Purchasing%20Report" class="productix-kpi-card" style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px;text-decoration:none!important;color:inherit;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-size:12px;color:#64748b;font-weight:600;">
                    <span>GRN Receipts</span><span style="font-size:16px;">🚚</span>
                </div>
                <div style="font-size:26px;font-weight:700;color:#2563eb;">${d.total_grns || 0}</div>
                <div style="font-size:11px;color:#94a3b8;margin-top:4px;">Received shipments</div>
            </a>
            <a href="/app/query-report/Inventory%20Status%20Report" class="productix-kpi-card" style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px;text-decoration:none!important;color:inherit;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-size:12px;color:#64748b;font-weight:600;">
                    <span>Needs Reorder (Low)</span><span style="font-size:16px;">⚠️</span>
                </div>
                <div style="font-size:26px;font-weight:700;color:${d.low_stock_count > 0 ? '#ef4444' : '#10b981'};">${d.low_stock_count || 0}</div>
                <div style="font-size:11px;color:#94a3b8;margin-top:4px;">Items below min threshold</div>
            </a>
            <a href="/app/query-report/Recipe%20Costing" class="productix-kpi-card" style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px;text-decoration:none!important;color:inherit;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-size:12px;color:#64748b;font-weight:600;">
                    <span>Formulations Costed</span><span style="font-size:16px;">💵</span>
                </div>
                <div style="font-size:26px;font-weight:700;color:#0f172a;">${d.total_recipes || 0}</div>
                <div style="font-size:11px;color:#94a3b8;margin-top:4px;">BOM standard costs</div>
            </a>
            <a href="/app/query-report/Stock%20Ledger" class="productix-kpi-card" style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px;text-decoration:none!important;color:inherit;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-size:12px;color:#64748b;font-weight:600;">
                    <span>Inventory Asset Value</span><span style="font-size:16px;">💰</span>
                </div>
                <div style="font-size:26px;font-weight:700;color:#0f172a;">$${valFormatted}</div>
                <div style="font-size:11px;color:#94a3b8;margin-top:4px;">Current raw material value</div>
            </a>
        `;
    } else if (role === 'staff') {
        kpiHtml = `
            <a href="/app/production-order" class="productix-kpi-card" style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px;text-decoration:none!important;color:inherit;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-size:12px;color:#64748b;font-weight:600;">
                    <span>Production Runs Today</span><span style="font-size:16px;">⚡</span>
                </div>
                <div style="font-size:26px;font-weight:700;color:#2563eb;">${d.today_orders || 0}</div>
                <div style="font-size:11px;color:#94a3b8;margin-top:4px;">Scheduled daily batch runs</div>
            </a>
            <a href="/app/production-order" class="productix-kpi-card" style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px;text-decoration:none!important;color:inherit;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-size:12px;color:#64748b;font-weight:600;">
                    <span>Active In-Progress</span><span style="font-size:16px;">🏭</span>
                </div>
                <div style="font-size:26px;font-weight:700;color:#10b981;">${inProgressCount}</div>
                <div style="font-size:11px;color:#94a3b8;margin-top:4px;">Runs being executed</div>
            </a>
            <a href="/app/recipe" class="productix-kpi-card" style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px;text-decoration:none!important;color:inherit;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-size:12px;color:#64748b;font-weight:600;">
                    <span>Formulations Guide</span><span style="font-size:16px;">📖</span>
                </div>
                <div style="font-size:26px;font-weight:700;color:#0f172a;">${d.total_recipes || 0}</div>
                <div style="font-size:11px;color:#94a3b8;margin-top:4px;">Available recipe sheets</div>
            </a>
            <a href="/app/instruction-message" class="productix-kpi-card" style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px;text-decoration:none!important;color:inherit;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-size:12px;color:#64748b;font-weight:600;">
                    <span>Team Instruction Room</span><span style="font-size:16px;">💬</span>
                </div>
                <div style="font-size:26px;font-weight:700;color:#0f172a;">Active</div>
                <div style="font-size:11px;color:#94a3b8;margin-top:4px;">Floor notices &amp; bulletins</div>
            </a>
        `;
    } else {
        // Executive / Admin full 6 cards
        kpiHtml = `
            <a href="/app/recipe" class="productix-kpi-card" style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px;text-decoration:none!important;color:inherit;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-size:12px;color:#64748b;font-weight:600;">
                    <span>Total Formulations</span><span style="font-size:16px;">📖</span>
                </div>
                <div style="font-size:24px;font-weight:700;color:#0f172a;">${d.total_recipes || 0}</div>
                <div style="font-size:11px;color:#94a3b8;margin-top:4px;">Standard BOM formulations</div>
            </a>
            <a href="/app/production-order" class="productix-kpi-card" style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px;text-decoration:none!important;color:inherit;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-size:12px;color:#64748b;font-weight:600;">
                    <span>Production Today</span><span style="font-size:16px;">⚡</span>
                </div>
                <div style="font-size:24px;font-weight:700;color:#0f172a;">${d.today_orders || 0}</div>
                <div style="font-size:11px;color:#94a3b8;margin-top:4px;">${d.total_orders || 0} Total Lifetime Runs</div>
            </a>
            <a href="/app/item" class="productix-kpi-card" style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px;text-decoration:none!important;color:inherit;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-size:12px;color:#64748b;font-weight:600;">
                    <span>Raw Materials</span><span style="font-size:16px;">📦</span>
                </div>
                <div style="font-size:24px;font-weight:700;color:#0f172a;">${d.total_items || 0}</div>
                <div style="font-size:11px;color:#94a3b8;margin-top:4px;">${d.total_batches || 0} Batches Tracked</div>
            </a>
            <a href="/app/query-report/Stock%20Ledger" class="productix-kpi-card" style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px;text-decoration:none!important;color:inherit;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-size:12px;color:#64748b;font-weight:600;">
                    <span>Stock Asset Value</span><span style="font-size:16px;">💰</span>
                </div>
                <div style="font-size:24px;font-weight:700;color:#0f172a;">$${valFormatted}</div>
                <div style="font-size:11px;color:#94a3b8;margin-top:4px;">Factory inventory valuation</div>
            </a>
            <a href="/app/query-report/Inventory%20Status%20Report" class="productix-kpi-card" style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px;text-decoration:none!important;color:inherit;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-size:12px;color:#64748b;font-weight:600;">
                    <span>Low Stock Items</span><span style="font-size:16px;">⚠️</span>
                </div>
                <div style="font-size:24px;font-weight:700;color:${d.low_stock_count > 0 ? '#d97706' : '#10b981'};">${d.low_stock_count || 0}</div>
                <div style="font-size:11px;color:#94a3b8;margin-top:4px;">${d.low_stock_count > 0 ? 'Below safety threshold' : 'All stocks healthy'}</div>
            </a>
            <a href="/app/query-report/Batch%20Expiry%20Report" class="productix-kpi-card" style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px;text-decoration:none!important;color:inherit;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-size:12px;color:#64748b;font-weight:600;">
                    <span>Expiry Alerts</span><span style="font-size:16px;">⏰</span>
                </div>
                <div style="font-size:24px;font-weight:700;color:${d.expiry_alert_count > 0 ? '#ef4444' : '#10b981'};">${d.expiry_alert_count || 0}</div>
                <div style="font-size:11px;color:#94a3b8;margin-top:4px;">${d.expiry_alert_count > 0 ? 'Expiring in ≤ 7 days' : 'No near-term expiries'}</div>
            </a>
        `;
    }

    $('#px-kpi-cards').html(`
        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(180px, 1fr));gap:14px;margin-bottom:20px;">
            ${kpiHtml}
        </div>
    `);
}

function render_charts(d, role) {
    let orderCounts = d.order_status_counts || {};
    let labels = Object.keys(orderCounts);
    let values = Object.values(orderCounts);
    let hasOrderData = values.some(v => v > 0);
    const orderChartEl = $('#px-chart-orders');

    if (orderChartEl.length) {
        orderChartEl.empty();
        if (hasOrderData && typeof frappe.Chart !== 'undefined') {
            new frappe.Chart(orderChartEl[0], {
                data: {
                    labels: labels,
                    datasets: [{ values: values }]
                },
                type: 'donut',
                height: 220,
                colors: ['#f59e0b', '#3b82f6', '#10b981', '#ef4444'],
                maxSlices: 5
            });
        } else {
            orderChartEl.html(`
                <div style="text-align:center;color:#94a3b8;padding:30px 20px;">
                    <div style="font-size:28px;margin-bottom:6px;">🏭</div>
                    <div style="font-weight:600;font-size:13px;color:#64748b;">No Production Runs Recorded</div>
                    <div style="font-size:11px;margin-top:4px;"><a href="/app/production-order/new" class="btn btn-xs btn-primary mt-2">Create First Order</a></div>
                </div>
            `);
        }
    }

    let catMap = d.recipe_categories || {};
    let catLabels = Object.keys(catMap);
    let catValues = Object.values(catMap);
    const recipeChartEl = $('#px-chart-recipes');

    if (recipeChartEl.length) {
        recipeChartEl.empty();
        if (catValues.length > 0 && typeof frappe.Chart !== 'undefined') {
            new frappe.Chart(recipeChartEl[0], {
                data: {
                    labels: catLabels,
                    datasets: [{ name: 'Recipes', values: catValues }]
                },
                type: 'bar',
                height: 220,
                colors: ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#06b6d4'],
            });
        } else {
            recipeChartEl.html(`
                <div style="text-align:center;color:#94a3b8;padding:30px 20px;">
                    <div style="font-size:28px;margin-bottom:6px;">🧪</div>
                    <div style="font-weight:600;font-size:13px;color:#64748b;">No Formulations Configured</div>
                    <div style="font-size:11px;margin-top:4px;"><a href="/app/recipe/new" class="btn btn-xs btn-primary mt-2">Create Formulation</a></div>
                </div>
            `);
        }
    }
}

function render_hub_tabs(roleCtx, role) {
    let tabs = [
        { id: 'px-tab-production', label: '🧪 Recipe & Formulations', defaultActive: role === 'production' || role === 'admin' },
        { id: 'px-tab-inventory', label: '📦 Materials & Inventory', defaultActive: role === 'store' },
        { id: 'px-tab-purchasing', label: '🤝 Suppliers & Costing', defaultActive: role === 'purchase' },
        { id: 'px-tab-team', label: '👥 Team, Roles & Staff', defaultActive: role === 'admin' || role === 'staff' },
    ];

    // Ensure only one tab is active
    let activeFound = false;
    tabs.forEach(t => {
        if (t.defaultActive && !activeFound) {
            t.active = true;
            activeFound = true;
        } else {
            t.active = false;
        }
    });
    if (!activeFound) tabs[0].active = true;

    let tabButtonsHtml = tabs.map(t => `
        <button class="px-tab-btn ${t.active ? 'active' : ''}" data-target="#${t.id}" style="padding:8px 16px;border-radius:6px;border:1px solid ${t.active ? '#0f172a' : '#cbd5e1'};background:${t.active ? '#0f172a' : '#fff'};color:${t.active ? '#fff' : '#334155'};cursor:pointer;font-weight:600;font-size:13px;">
            ${t.label}
        </button>
    `).join('');

    $('#px-hub-tabs-container').html(`
        <div class="productix-hub-tabs" style="display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap;">
            ${tabButtonsHtml}
        </div>
    `);

    // Tab Contents
    let contentsHtml = `
        <!-- Tab 1: Recipe & Formulations -->
        <div id="px-tab-production" class="px-tab-content ${tabs[0].active ? 'active' : ''}" style="${tabs[0].active ? '' : 'display:none;'}">
            <div class="productix-features-grid" style="display:grid;grid-template-columns:repeat(auto-fill, minmax(200px, 1fr));gap:12px;">
                <a href="/app/recipe/new" class="px-feature-card ${roleCtx.can_create_recipe ? '' : 'px-card-disabled'}" style="padding:12px;background:#fff;border:1px solid #e2e8f0;border-radius:8px;text-decoration:none;color:inherit;display:flex;gap:12px;align-items:center;">
                    <div style="background:#eff6ff;color:#2563eb;font-size:18px;width:36px;height:36px;display:flex;align-items:center;justify-content:center;border-radius:6px;">➕</div>
                    <div>
                        <div style="font-weight:600;font-size:13px;color:#0f172a;">New Recipe</div>
                        <div style="font-size:11px;color:#64748b;">${roleCtx.can_create_recipe ? 'Create chemical BOM' : 'Requires Manager Role'}</div>
                    </div>
                </a>
                <a href="/app/recipe" class="px-feature-card" style="padding:12px;background:#fff;border:1px solid #e2e8f0;border-radius:8px;text-decoration:none;color:inherit;display:flex;gap:12px;align-items:center;">
                    <div style="background:#eff6ff;color:#3b82f6;font-size:18px;width:36px;height:36px;display:flex;align-items:center;justify-content:center;border-radius:6px;">📖</div>
                    <div>
                        <div style="font-weight:600;font-size:13px;color:#0f172a;">All Recipes</div>
                        <div style="font-size:11px;color:#64748b;">Formulations catalog</div>
                    </div>
                </a>
                <a href="/app/production-order/new" class="px-feature-card ${roleCtx.can_create_production_order ? '' : 'px-card-disabled'}" style="padding:12px;background:#fff;border:1px solid #e2e8f0;border-radius:8px;text-decoration:none;color:inherit;display:flex;gap:12px;align-items:center;">
                    <div style="background:#ecfdf5;color:#059669;font-size:18px;width:36px;height:36px;display:flex;align-items:center;justify-content:center;border-radius:6px;">⚡</div>
                    <div>
                        <div style="font-weight:600;font-size:13px;color:#0f172a;">New Production Run</div>
                        <div style="font-size:11px;color:#64748b;">${roleCtx.can_create_production_order ? 'Execute batch order' : 'Requires Production Role'}</div>
                    </div>
                </a>
                <a href="/app/production-order" class="px-feature-card" style="padding:12px;background:#fff;border:1px solid #e2e8f0;border-radius:8px;text-decoration:none;color:inherit;display:flex;gap:12px;align-items:center;">
                    <div style="background:#ecfdf5;color:#10b981;font-size:18px;width:36px;height:36px;display:flex;align-items:center;justify-content:center;border-radius:6px;">🏭</div>
                    <div>
                        <div style="font-weight:600;font-size:13px;color:#0f172a;">Production Queue</div>
                        <div style="font-size:11px;color:#64748b;">Track batch status</div>
                    </div>
                </a>
                <a href="/app/recipe-extra" class="px-feature-card" style="padding:12px;background:#fff;border:1px solid #e2e8f0;border-radius:8px;text-decoration:none;color:inherit;display:flex;gap:12px;align-items:center;">
                    <div style="background:#f5f3ff;color:#7c3aed;font-size:18px;width:36px;height:36px;display:flex;align-items:center;justify-content:center;border-radius:6px;">✨</div>
                    <div>
                        <div style="font-weight:600;font-size:13px;color:#0f172a;">Recipe Extras</div>
                        <div style="font-size:11px;color:#64748b;">Catalysts &amp; additives</div>
                    </div>
                </a>
                <a href="/app/consumption-log" class="px-feature-card" style="padding:12px;background:#fff;border:1px solid #e2e8f0;border-radius:8px;text-decoration:none;color:inherit;display:flex;gap:12px;align-items:center;">
                    <div style="background:#f5f3ff;color:#8b5cf6;font-size:18px;width:36px;height:36px;display:flex;align-items:center;justify-content:center;border-radius:6px;">📋</div>
                    <div>
                        <div style="font-weight:600;font-size:13px;color:#0f172a;">Consumption Logs</div>
                        <div style="font-size:11px;color:#64748b;">FEFO audit deduction</div>
                    </div>
                </a>
                <a href="/app/query-report/Production%20Ingredient%20Sheet" class="px-feature-card" style="padding:12px;background:#fff;border:1px solid #e2e8f0;border-radius:8px;text-decoration:none;color:inherit;display:flex;gap:12px;align-items:center;">
                    <div style="background:#fffbeb;color:#d97706;font-size:18px;width:36px;height:36px;display:flex;align-items:center;justify-content:center;border-radius:6px;">📑</div>
                    <div>
                        <div style="font-weight:600;font-size:13px;color:#0f172a;">Ingredient Sheet</div>
                        <div style="font-size:11px;color:#64748b;">Batching guide</div>
                    </div>
                </a>
                <a href="/app/query-report/Production%20Performance%20Report" class="px-feature-card" style="padding:12px;background:#fff;border:1px solid #e2e8f0;border-radius:8px;text-decoration:none;color:inherit;display:flex;gap:12px;align-items:center;">
                    <div style="background:#ecfeff;color:#0891b2;font-size:18px;width:36px;height:36px;display:flex;align-items:center;justify-content:center;border-radius:6px;">📈</div>
                    <div>
                        <div style="font-weight:600;font-size:13px;color:#0f172a;">Performance</div>
                        <div style="font-size:11px;color:#64748b;">Yield &amp; variance analytics</div>
                    </div>
                </a>
            </div>
        </div>

        <!-- Tab 2: Materials & Inventory -->
        <div id="px-tab-inventory" class="px-tab-content ${tabs[1].active ? 'active' : ''}" style="${tabs[1].active ? '' : 'display:none;'}">
            <div class="productix-features-grid" style="display:grid;grid-template-columns:repeat(auto-fill, minmax(200px, 1fr));gap:12px;">
                <a href="/app/item" class="px-feature-card" style="padding:12px;background:#fff;border:1px solid #e2e8f0;border-radius:8px;text-decoration:none;color:inherit;display:flex;gap:12px;align-items:center;">
                    <div style="background:#eff6ff;color:#2563eb;font-size:18px;width:36px;height:36px;display:flex;align-items:center;justify-content:center;border-radius:6px;">📦</div>
                    <div>
                        <div style="font-weight:600;font-size:13px;color:#0f172a;">Raw Materials</div>
                        <div style="font-size:11px;color:#64748b;">Chemical inventory</div>
                    </div>
                </a>
                <a href="/app/batch" class="px-feature-card" style="padding:12px;background:#fff;border:1px solid #e2e8f0;border-radius:8px;text-decoration:none;color:inherit;display:flex;gap:12px;align-items:center;">
                    <div style="background:#f5f3ff;color:#7c3aed;font-size:18px;width:36px;height:36px;display:flex;align-items:center;justify-content:center;border-radius:6px;">🏷️</div>
                    <div>
                        <div style="font-weight:600;font-size:13px;color:#0f172a;">Inventory Batches</div>
                        <div style="font-size:11px;color:#64748b;">Expiry &amp; lot tracking</div>
                    </div>
                </a>
                <a href="/app/purchase-receipt/new" class="px-feature-card ${roleCtx.can_receive_grn ? '' : 'px-card-disabled'}" style="padding:12px;background:#fff;border:1px solid #e2e8f0;border-radius:8px;text-decoration:none;color:inherit;display:flex;gap:12px;align-items:center;">
                    <div style="background:#ecfdf5;color:#059669;font-size:18px;width:36px;height:36px;display:flex;align-items:center;justify-content:center;border-radius:6px;">📥</div>
                    <div>
                        <div style="font-weight:600;font-size:13px;color:#0f172a;">Stock In</div>
                        <div style="font-size:11px;color:#64748b;">Receive ingredients &amp; batch</div>
                    </div>
                </a>
                <a href="/app/query-report/Purchasing%20Report" class="px-feature-card" style="padding:12px;background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;text-decoration:none;color:inherit;display:flex;gap:12px;align-items:center;">
                    <div style="background:#dbeafe;color:#1e40af;font-size:18px;width:36px;height:36px;display:flex;align-items:center;justify-content:center;border-radius:6px;">📜</div>
                    <div>
                        <div style="font-weight:600;font-size:13px;color:#1e40af;">GRN History</div>
                        <div style="font-size:11px;color:#3b82f6;">All receipts, batches &amp; rates</div>
                    </div>
                </a>
                <a href="/app/query-report/Inventory%20Status%20Report" class="px-feature-card" style="padding:12px;background:#fff;border:1px solid #e2e8f0;border-radius:8px;text-decoration:none;color:inherit;display:flex;gap:12px;align-items:center;">
                    <div style="background:#eff6ff;color:#3b82f6;font-size:18px;width:36px;height:36px;display:flex;align-items:center;justify-content:center;border-radius:6px;">📊</div>
                    <div>
                        <div style="font-weight:600;font-size:13px;color:#0f172a;">Inventory Status</div>
                        <div style="font-size:11px;color:#64748b;">Stock vs safety min</div>
                    </div>
                </a>
                <a href="/app/query-report/Batch%20Expiry%20Report" class="px-feature-card" style="padding:12px;background:#fff;border:1px solid #e2e8f0;border-radius:8px;text-decoration:none;color:inherit;display:flex;gap:12px;align-items:center;">
                    <div style="background:#fef2f2;color:#dc2626;font-size:18px;width:36px;height:36px;display:flex;align-items:center;justify-content:center;border-radius:6px;">⏰</div>
                    <div>
                        <div style="font-weight:600;font-size:13px;color:#0f172a;">Batch Expiry</div>
                        <div style="font-size:11px;color:#64748b;">Shelf-life alerts</div>
                    </div>
                </a>
            </div>
        </div>

        <!-- Tab 3: Suppliers & Costing -->
        <div id="px-tab-purchasing" class="px-tab-content ${tabs[2].active ? 'active' : ''}" style="${tabs[2].active ? '' : 'display:none;'}">
            <div class="productix-features-grid" style="display:grid;grid-template-columns:repeat(auto-fill, minmax(200px, 1fr));gap:12px;">
                <a href="/app/supplier/new" class="px-feature-card ${roleCtx.is_purchase || roleCtx.is_admin ? '' : 'px-card-disabled'}" style="padding:12px;background:#fff;border:1px solid #e2e8f0;border-radius:8px;text-decoration:none;color:inherit;display:flex;gap:12px;align-items:center;">
                    <div style="background:#ecfdf5;color:#059669;font-size:18px;width:36px;height:36px;display:flex;align-items:center;justify-content:center;border-radius:6px;">➕</div>
                    <div>
                        <div style="font-weight:600;font-size:13px;color:#0f172a;">New Supplier</div>
                        <div style="font-size:11px;color:#64748b;">Register vendor</div>
                    </div>
                </a>
                <a href="/app/supplier" class="px-feature-card" style="padding:12px;background:#fff;border:1px solid #e2e8f0;border-radius:8px;text-decoration:none;color:inherit;display:flex;gap:12px;align-items:center;">
                    <div style="background:#eff6ff;color:#2563eb;font-size:18px;width:36px;height:36px;display:flex;align-items:center;justify-content:center;border-radius:6px;">🏢</div>
                    <div>
                        <div style="font-weight:600;font-size:13px;color:#0f172a;">Supplier Directory</div>
                        <div style="font-size:11px;color:#64748b;">Active vendor profiles</div>
                    </div>
                </a>
                <a href="/app/query-report/Purchasing%20Report" class="px-feature-card" style="padding:12px;background:#fff;border:1px solid #e2e8f0;border-radius:8px;text-decoration:none;color:inherit;display:flex;gap:12px;align-items:center;">
                    <div style="background:#fffbeb;color:#d97706;font-size:18px;width:36px;height:36px;display:flex;align-items:center;justify-content:center;border-radius:6px;">📑</div>
                    <div>
                        <div style="font-weight:600;font-size:13px;color:#0f172a;">Purchasing Report</div>
                        <div style="font-size:11px;color:#64748b;">Spend by supplier</div>
                    </div>
                </a>
                <a href="/app/query-report/Recipe%20Costing" class="px-feature-card" style="padding:12px;background:#fff;border:1px solid #e2e8f0;border-radius:8px;text-decoration:none;color:inherit;display:flex;gap:12px;align-items:center;">
                    <div style="background:#ecfeff;color:#0891b2;font-size:18px;width:36px;height:36px;display:flex;align-items:center;justify-content:center;border-radius:6px;">💵</div>
                    <div>
                        <div style="font-weight:600;font-size:13px;color:#0f172a;">Recipe Costing</div>
                        <div style="font-size:11px;color:#64748b;">Formulation margins</div>
                    </div>
                </a>
            </div>
        </div>

        <!-- Tab 4: Team, Roles & Staff -->
        <div id="px-tab-team" class="px-tab-content ${tabs[3].active ? 'active' : ''}" style="${tabs[3].active ? '' : 'display:none;'}">
            <div class="productix-features-grid" style="display:grid;grid-template-columns:repeat(auto-fill, minmax(200px, 1fr));gap:12px;">
                <a href="/app/user" class="px-feature-card ${roleCtx.can_manage_roles ? '' : 'px-card-disabled'}" style="padding:12px;background:#fff;border:1px solid #e2e8f0;border-radius:8px;text-decoration:none;color:inherit;display:flex;gap:12px;align-items:center;">
                    <div style="background:#f5f3ff;color:#7c3aed;font-size:18px;width:36px;height:36px;display:flex;align-items:center;justify-content:center;border-radius:6px;">👤</div>
                    <div>
                        <div style="font-weight:600;font-size:13px;color:#0f172a;">Staff Directory</div>
                        <div style="font-size:11px;color:#64748b;">${roleCtx.can_manage_roles ? 'View and manage team users' : 'Admin only'}</div>
                    </div>
                </a>
                <a href="/app/instruction-message" class="px-feature-card" style="padding:12px;background:#fff;border:1px solid #e2e8f0;border-radius:8px;text-decoration:none;color:inherit;display:flex;gap:12px;align-items:center;">
                    <div style="background:#eff6ff;color:#2563eb;font-size:18px;width:36px;height:36px;display:flex;align-items:center;justify-content:center;border-radius:6px;">💬</div>
                    <div>
                        <div style="font-weight:600;font-size:13px;color:#0f172a;">Instruction Room</div>
                        <div style="font-size:11px;color:#64748b;">Team announcements</div>
                    </div>
                </a>
                <a href="/app/ai-agent-log" class="px-feature-card ${roleCtx.is_admin || roleCtx.is_production ? '' : 'px-card-disabled'}" style="padding:12px;background:#fff;border:1px solid #e2e8f0;border-radius:8px;text-decoration:none;color:inherit;display:flex;gap:12px;align-items:center;">
                    <div style="background:#ecfeff;color:#0891b2;font-size:18px;width:36px;height:36px;display:flex;align-items:center;justify-content:center;border-radius:6px;">🔍</div>
                    <div>
                        <div style="font-weight:600;font-size:13px;color:#0f172a;">System &amp; Audit Logs</div>
                        <div style="font-size:11px;color:#64748b;">Scan logs &amp; user history</div>
                    </div>
                </a>
            </div>
        </div>
    `;

    $('#px-hub-content-container').html(contentsHtml);

    // Tab click interaction
    $('#px-hub-tabs-container .px-tab-btn').on('click', function() {
        $('#px-hub-tabs-container .px-tab-btn').removeClass('active').css({'background':'#fff','color':'#334155','border-color':'#cbd5e1'});
        $('#px-hub-content-container .px-tab-content').hide();
        $(this).addClass('active').css({'background':'#0f172a','color':'#fff','border-color':'#0f172a'});
        let targetId = $(this).data('target');
        $(targetId).show();
    });
}

function load_recent_orders(orders) {
    if (!orders || orders.length === 0) {
        $('#px-orders-table-wrapper').html(`
            <div class="text-center text-muted p-4">
                <p style="margin-bottom:8px;">No formulation runs recorded yet.</p>
                <a href="/app/production-order/new" class="btn btn-xs btn-primary">➕ Start Production Run</a>
            </div>
        `);
        return;
    }

    let badgeMap = {
        'Pending': '<span class="badge" style="background:#fef3c7;color:#92400e;font-size:11px;padding:4px 8px;border-radius:4px;">⏳ Pending</span>',
        'In Progress': '<span class="badge" style="background:#dbeafe;color:#1e40af;font-size:11px;padding:4px 8px;border-radius:4px;">⚡ In Progress</span>',
        'Completed': '<span class="badge" style="background:#d1fae5;color:#065f46;font-size:11px;padding:4px 8px;border-radius:4px;">✅ Completed</span>',
        'Cancelled': '<span class="badge" style="background:#fee2e2;color:#991b1b;font-size:11px;padding:4px 8px;border-radius:4px;">❌ Cancelled</span>',
    };

    let rows = orders.map(o => {
        let creator = o.created_by_name || o.owner || '—';
        return `
            <tr>
                <td style="font-weight:600;"><a href="/app/production-order/${o.name}">${o.order_number || o.name}</a></td>
                <td>${o.recipe_name || '—'}</td>
                <td style="text-align:center;font-weight:700;">${o.quantity}</td>
                <td>${badgeMap[o.status] || o.status}</td>
                <td style="font-size:12px;color:#475569;">👤 ${creator}</td>
                <td style="text-align:right;">
                    <a href="/app/production-order/${o.name}" class="btn btn-xs btn-default">Open</a>
                </td>
            </tr>
        `;
    }).join('');

    $('#px-orders-table-wrapper').html(`
        <table class="table table-hover table-striped" style="margin-bottom:0;font-size:13px;">
            <thead>
                <tr style="background:#f8fafc;color:#475569;font-size:12px;text-transform:uppercase;">
                    <th>Order #</th>
                    <th>Formulation</th>
                    <th style="text-align:center;">Qty</th>
                    <th>Status</th>
                    <th>Created By</th>
                    <th style="text-align:right;">Action</th>
                </tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>
    `);
}

function render_activity_stream(activities) {
    if (!activities || activities.length === 0) {
        $('#px-activity-wrapper').html('<div class="text-center text-muted p-4">No recent activity logs.</div>');
        return;
    }

    let typeIconMap = {
        'Purchase Receipt': { icon: '🚚', bg: '#eff6ff', color: '#2563eb' },
        'Production Order': { icon: '🏭', bg: '#ecfdf5', color: '#059669' },
        'System': { icon: '⚙️', bg: '#f1f5f9', color: '#334155' },
        'Scheduled Scan': { icon: '🔍', bg: '#fffbeb', color: '#d97706' },
        'Manual Scan': { icon: '🔍', bg: '#fffbeb', color: '#d97706' },
        'Expiry Alert': { icon: '⏰', bg: '#fef2f2', color: '#dc2626' },
        'Low Stock Alert': { icon: '⚠️', bg: '#fffbeb', color: '#d97706' },
    };

    let itemsHtml = activities.map(act => {
        let style = typeIconMap[act.type] || { icon: '📋', bg: '#f8fafc', color: '#64748b' };
        let dateStr = (act.timestamp || '').split('.')[0];
        let linkHtml = act.link ? `<a href="${act.link}" style="text-decoration:none;color:inherit;"><strong>${act.title}</strong></a>` : `<strong>${act.title}</strong>`;

        return `
            <div class="px-activity-item">
                <div class="px-act-icon" style="background:${style.bg};color:${style.color};">
                    ${style.icon}
                </div>
                <div class="px-act-body">
                    <div class="px-act-header">
                        <span class="px-act-title">${linkHtml}</span>
                        <span class="px-act-time">${dateStr}</span>
                    </div>
                    <div class="px-act-desc">${act.details}</div>
                </div>
            </div>
        `;
    }).join('');

    $('#px-activity-wrapper').html(`
        <div class="px-activity-timeline">
            ${itemsHtml}
        </div>
    `);
}
