frappe.ui.form.on('Productix Settings', {
    refresh: function(frm) {
        frm.add_custom_button(__('Reload Module Registry'), function() {
            frappe.call({
                method: 'productix_core.modules.entitlement.reload_registry',
                callback: function(r) {
                    frappe.msgprint(__('Module registry reloaded.'));
                    frm.reload_doc();
                }
            });
        }, __('Modules'));
    }
});