// Productix Recipe — global module script (loaded via app_include_js).
// Attaches recipe functions onto the shared `productix` global provided by
// productix_core (never overwrite the whole object).

frappe.provide('productix');

Object.assign(productix, {
    trigger_scan: function() {
        frappe.call({
            method: 'productix_recipe.api.inventory.trigger_manual_scan',
            callback: function() {
                frappe.show_alert({ message: __('Inventory scan completed!'), indicator: 'green' });
            }
        });
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
            method: 'productix_recipe.api.inventory.get_item_stock_info',
            args: { item_code: item_code },
            callback: function(r) {
                if (callback) callback(r.message);
            }
        });
    },
});

frappe.ready(function() {
    if (frappe.session && frappe.session.user && frappe.session.user !== 'Guest') {
        productix.enhance_list_views();
    }
});

$(document).ready(function() {
    $('.productix-dashboard-wrapper').remove();
});

$(document).on('page-change', function() {
    $('.productix-dashboard-wrapper').remove();
});