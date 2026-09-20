frappe.ui.form.on('Instruction Message', {
    refresh: function(frm) {
        frm.set_intro(
            '<div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:6px;padding:10px 14px;color:#1e40af;font-size:13px;">' +
            '📢 <strong>Instruction Room &amp; Team Bulletin:</strong> Post messages, shift instructions, or batch notes. ' +
            'Choose <strong>All Staff</strong> to broadcast or <strong>Specific User</strong> to tag someone. ' +
            'Notifications automatically route to the top navbar 🔔 notification bell.' +
            '</div>',
            false
        );

        // Clear all button for admins
        if (frappe.user.has_role(['Factory Admin', 'Productix Admin', 'Productix Assistant Admin', 'System Manager', 'Administrator'])) {
            frm.add_custom_button(__('🗑 Clear All Messages'), function() {
                frappe.confirm(
                    'Delete ALL instruction room messages and notification logs? This cannot be undone.',
                    () => frappe.call({
                        method: 'productix.instruction_room.doctype.instruction_message.instruction_message.clear_all_messages',
                        callback: () => frappe.set_route('List', 'Instruction Message')
                    })
                );
            }).addClass('btn-danger');
        }

        // Mark notifications as read when visiting this message
        frappe.call({
            method: 'productix.instruction_room.doctype.instruction_message.instruction_message.mark_all_read',
        });
    },

    onload: function(frm) {
        if (!frm.doc.sender) {
            frm.set_value('sender', frappe.session.user);
        }
        if (!frm.doc.tag_target) {
            frm.set_value('tag_target', 'All Staff');
        }
    },

    tag_target: function(frm) {
        if (frm.doc.tag_target === 'All Staff') {
            frm.set_value('tagged_user', null);
        }
    }
});
