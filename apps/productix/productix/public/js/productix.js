// Productix ERP Global JavaScript & Utilities

frappe.provide('productix');

productix = {
    version: '1.0.0',

    init: function() {
        $('.productix-dashboard-wrapper').remove();
        productix.check_subscription_status();
        productix.enhance_list_views();
        productix.setup_kpi_route_guards();
        productix.filter_employee_kpi_navigation();
    },

    setup_kpi_route_guards: function() {
        if (!frappe.router) return;

        const FORBIDDEN_SLUGS = [
            'kpi-company-overview',
            'kpi_company_overview',
            'kpi-action-center',
            'kpi_action_center',
            'kpi-formula-builder',
            'kpi_formula_builder',
            'kpi-setup-wizard',
            'kpi_setup_wizard',
            'kpi-ai-assistant',
            'kpi_ai_assistant',
            'backups',
            'kpi-definition',
            'kpi_definition',
            'kpi definition',
            'kpi-formula',
            'kpi_formula',
            'kpi formula',
            'kpi-template',
            'kpi_template',
            'kpi template',
            'kpi-prediction',
            'kpi_prediction',
            'kpi prediction',
            'kpi-operational-data',
            'kpi_operational_data',
            'kpi operational data',
            'kpi-department',
            'kpi_department',
            'kpi department',
            'kpi-business-unit',
            'kpi_business_unit',
            'kpi business unit',
            'kpi-variable',
            'kpi_variable',
            'kpi variable',
            'kpi-operational-table',
            'kpi_operational_table',
            'kpi operational table',
            'kpi-settings',
            'kpi_settings',
            'kpi settings',
            'kpi-user-assignment',
            'kpi_user_assignment',
            'kpi user assignment',
            'kpi-performance-and-variance-report',
            'kpi performance and variance report',
            'department-performance-report',
            'department performance report',
            'kpi-trend-and-forecast-report',
            'kpi trend and forecast report',
            'kpi-alert-and-action-report',
            'kpi alert and action report',
            'kpi-data-quality-and-completeness-report',
            'kpi data quality and completeness report',
            'company-tracking-system',
            'company tracking system',
            'kpi-tracking',
            'kpi tracking'
        ];

        function normalize(str) {
            if (!str) return '';
            return String(str).toLowerCase().trim().replace(/_/g, '-');
        }

        function redirectToDepartmentDashboard(alertMessage) {
            if (alertMessage) {
                frappe.show_alert({ message: alertMessage, indicator: 'blue' });
            }
            frappe.call({
                method: 'productix.kpi_tracking.api.dashboard.get_user_context',
                callback: function(r) {
                    if (r.message && r.message.assigned_department) {
                        frappe.set_route('kpi-department-dashboard', { department: r.message.assigned_department });
                    } else {
                        frappe.set_route('kpi-department-dashboard');
                    }
                }
            });
        }

        function isForbidden(routeItem) {
            if (!routeItem) return false;
            const norm = normalize(routeItem);
            const plain = String(routeItem).toLowerCase().trim();
            for (let i = 0; i < FORBIDDEN_SLUGS.length; i++) {
                const f = FORBIDDEN_SLUGS[i];
                if (norm === normalize(f) || plain === f) {
                    return true;
                }
            }
            return false;
        }

        function enforce_route() {
            const user = frappe.session.user;
            if (!user || user === 'Guest') return;

            const user_roles = frappe.user_roles || (frappe.boot && frappe.boot.user && frappe.boot.user.roles) || [];
            const has_role = function(r) {
                if (Array.isArray(user_roles) && user_roles.includes(r)) return true;
                if (frappe.user && typeof frappe.user.has_role === 'function') return frappe.user.has_role(r);
                if (frappe.boot && frappe.boot.user && Array.isArray(frappe.boot.user.roles)) return frappe.boot.user.roles.includes(r);
                return false;
            };

            const is_admin = user === 'Administrator' ||
                             has_role('System Manager') ||
                             has_role('KPI Admin') ||
                             has_role('Administrator') ||
                             has_role('Productix Admin') ||
                             has_role('Factory Admin') ||
                             has_role('Assistant System Administrator');

            if (is_admin) return;

            const is_ceo = has_role('KPI CEO');
            const route = frappe.get_route() || [];
            if (route.length === 0) return;

            if (is_ceo) {
                const CEO_FORBIDDEN = [
                    'backups',
                    'kpi-data-entry-page',
                    'kpi_data_entry_page',
                    'kpi-setup-wizard',
                    'kpi_setup_wizard',
                    'kpi-formula-builder',
                    'kpi_formula_builder'
                ];
                for (let i = 0; i < route.length; i++) {
                    const norm = normalize(route[i]);
                    if (CEO_FORBIDDEN.includes(norm)) {
                        redirectToDepartmentDashboard(__('Access restricted: Backup and Data Entry are reserved for administrators.'));
                        return;
                    }
                }
                return;
            }

            for (let i = 0; i < route.length; i++) {
                if (isForbidden(route[i])) {
                    redirectToDepartmentDashboard(__('Access redirected to your Department Dashboard.'));
                    return;
                }
            }
        }

        frappe.router.on('change', enforce_route);
        setTimeout(enforce_route, 100);
    },

    filter_employee_kpi_navigation: function() {
        function sanitizeUI() {
            const user = frappe.session && frappe.session.user;
            if (!user || user === 'Guest') return;

            const user_roles = frappe.user_roles || (frappe.boot && frappe.boot.user && frappe.boot.user.roles) || [];
            const has_role = function(r) {
                if (Array.isArray(user_roles) && user_roles.includes(r)) return true;
                if (frappe.user && typeof frappe.user.has_role === 'function') return frappe.user.has_role(r);
                if (frappe.boot && frappe.boot.user && Array.isArray(frappe.boot.user.roles)) return frappe.boot.user.roles.includes(r);
                return false;
            };

            const is_admin = user === 'Administrator' ||
                             has_role('System Manager') ||
                             has_role('KPI Admin') ||
                             has_role('Administrator') ||
                             has_role('Productix Admin') ||
                             has_role('Factory Admin') ||
                             has_role('Assistant System Administrator');

            if (is_admin) return;

            const is_ceo = has_role('KPI CEO');
            // CEOs keep visibility of their permitted dashboards; employees get
            // the minimal data-entry experience. Backups/Data Entry remain hidden for CEOs.
            const allowedLabels = is_ceo
                ? [
                    'company overview',
                    'department dashboard',
                    'machine health',
                    'machine health dashboard',
                    'machine',
                    'machine type',
                    'machine reading',
                    'machine health log',
                    'kpi alert',
                    'ai performance assistant',
                    'ai assistant',
                    'action center',
                    'kpi reports',
                    'performance & variance',
                    'department performance',
                    'trend & forecast',
                    'alert & action',
                    'data quality'
                ]
                : [
                    'department dashboard',
                    'kpi data entry',
                    'kpi alert'
                ];

            function isAllowed(text) {
                if (!text) return false;
                const clean = text.toLowerCase().trim();
                for (let i = 0; i < allowedLabels.length; i++) {
                    if (clean === allowedLabels[i] || clean.includes(allowedLabels[i])) {
                        return true;
                    }
                }
                return false;
            }

            $('.widget-card, .shortcut-widget-box, .links-card, .desk-sidebar-item').each(function() {
                const $el = $(this);
                const title = $el.find('.widget-title, .shortcut-label, .link-text, .item-anchor').text().trim();
                const route = $el.attr('data-route') || $el.find('a').attr('href') || '';

                const isKpiRelated = route.includes('kpi') || title.toLowerCase().includes('kpi') ||
                                     title.toLowerCase().includes('department') || title.toLowerCase().includes('company') ||
                                     title.toLowerCase().includes('formula') || title.toLowerCase().includes('prediction');

                if (isKpiRelated) {
                    if (!isAllowed(title) && !isAllowed(route)) {
                        $el.hide();
                    }
                }
            });
        }

        $(document).on('page-change ajaxComplete', function() {
            sanitizeUI();
        });
        setInterval(sanitizeUI, 1000);
    },

    trigger_scan: function() {
        frappe.call({
            method: 'productix.alerts.doctype.ai_agent_log.ai_agent_log.trigger_manual_scan',
            callback: function() {
                frappe.show_alert({ message: __('Inventory scan completed!'), indicator: 'green' });
            }
        });
    },

    check_subscription_status: function() {
        if (frappe.session.user === 'Guest') return;

        frappe.call({
            method: 'productix.api.subscription.get_subscription_status',
            callback: function(r) {
                if (r.message && r.message.expired) {
                    productix.show_subscription_warning(r.message.valid_until);
                } else if (r.message && r.message.expiring_soon) {
                    productix.show_expiry_notice(r.message.days_left, r.message.valid_until);
                }
            }
        });
    },

    show_subscription_warning: function(valid_until) {
        if ($('#productix-subscription-warning').length === 0) {
            $('body').prepend(
                `<div id="productix-subscription-warning" style="background:#dc2626;color:#fff;text-align:center;padding:8px;font-weight:600;font-size:13px;position:sticky;top:0;z-index:9999;">
                    ⚠️ Your subscription expired on ${valid_until}.
                    Read-only mode active. Contact support to renew.
                </div>`
            );
        }
    },

    show_expiry_notice: function(days_left, valid_until) {
        frappe.show_alert({
            message: `Your subscription expires in ${days_left} day(s) on ${valid_until}. Please renew soon.`,
            indicator: 'orange'
        }, 8);
    },

    enhance_list_views: function() {
        $(document).on('frappe.ui.form.ListRenderer.ready', function() {
            productix.colorize_status_cells();
        });
    },

    colorize_status_cells: function() {
        $('.list-row').each(function() {
            let statusCell = $(this).find('[data-fieldname="status"]');
            let status = statusCell.text().trim();
            let colorMap = {
                'Pending': 'orange',
                'In Progress': 'blue',
                'Completed': 'green',
                'Cancelled': 'red',
                'Active': 'green',
                'Inactive': 'grey',
                'Expired': 'red',
            };
            if (colorMap[status]) {
                statusCell.html(
                    `<span class="indicator ${colorMap[status]}">${status}</span>`
                );
            }
        });
    },

    format_number: function(n, decimals=2) {
        return parseFloat(n || 0).toFixed(decimals).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    },

    get_stock_info: function(item_code, callback) {
        frappe.call({
            method: 'productix.api.inventory.get_item_stock_info',
            args: { item_code: item_code },
            callback: function(r) {
                if (callback) callback(r.message);
            }
        });
    },
};

$(document).ready(function() {
    $('.productix-dashboard-wrapper').remove();
    if (frappe && frappe.session && frappe.session.user !== 'Guest') {
        productix.init();
    }
});

$(document).on('page-change', function() {
    $('.productix-dashboard-wrapper').remove();
});
