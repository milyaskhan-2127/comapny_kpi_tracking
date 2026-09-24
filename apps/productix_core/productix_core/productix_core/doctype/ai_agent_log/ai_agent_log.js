frappe.ui.form.on('AI Agent Log', {
    refresh: function(frm) {
        // The manual inventory scan lives in the Recipe module — only expose
        // the trigger when that module is installed and enabled on this site.
        if (frappe.user.has_role(['Productix Admin', 'Productix Assistant Admin', 'System Manager'])
            && (typeof productix.is_module_enabled === 'function')
            && productix.is_module_enabled('recipe')) {
            frm.add_custom_button(__('🔍 Trigger Manual Scan'), function() {
                frappe.confirm('Run an inventory scan now?', () => {
                    frappe.call({
                        method: 'productix_recipe.api.inventory.trigger_manual_scan',
                        callback: () => frappe.set_route('List', 'AI Agent Log')
                    });
                });
            }, __('Actions')).addClass('btn-primary');
        }

        // Color indicator by status
        let colors = { Success: 'green', Failed: 'red', Warning: 'orange', Info: 'blue' };
        frm.page.set_indicator(frm.doc.status, colors[frm.doc.status] || 'grey');
    }
});