frappe.ui.form.on('AI Agent Log', {
    refresh: function(frm) {
        if (frappe.user.has_role(['Productix Admin', 'Productix Assistant Admin', 'System Manager'])) {
            frm.add_custom_button(__('🔍 Trigger Manual Scan'), function() {
                frappe.confirm('Run an inventory scan now?', () => {
                    frappe.call({
                        method: 'productix.alerts.doctype.ai_agent_log.ai_agent_log.trigger_manual_scan',
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
