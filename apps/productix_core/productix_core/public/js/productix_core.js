// Productix Core — shared global namespace, subscription/license checks and
// module-entitlement helpers. Loaded on every page (app_include_js).
// Other productix apps attach their own methods onto the shared `productix`
// global — never overwrite the whole object.

frappe.provide('productix');

Object.assign(productix, {
    version: '1.0.0',

    // True when a productix module is enabled on this site (boot payload).
    is_module_enabled: function(moduleKey) {
        var modules = (frappe.boot && frappe.boot.productix_modules) || [];
        return modules.indexOf(moduleKey) !== -1;
    },

    check_subscription_status: function() {
        if (frappe.session.user === 'Guest') return;

        frappe.call({
            method: 'productix_core.api.subscription.get_subscription_status',
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
    }
});

frappe.ready(function() {
    if (frappe.session && frappe.session.user && frappe.session.user !== 'Guest') {
        productix.check_subscription_status();
    }
});