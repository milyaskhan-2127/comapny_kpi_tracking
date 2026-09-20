frappe.ui.form.on('Productix License', {
    refresh: function(frm) {
        if (!frm.is_new()) {
            let today = frappe.datetime.get_today();
            let isExpired = frm.doc.valid_until && frm.doc.valid_until < today;
            let daysLeft = frm.doc.valid_until
                ? frappe.datetime.get_diff(frm.doc.valid_until, today)
                : -999;
            let isExpiringSoon = !isExpired && daysLeft >= 0 && daysLeft <= 7;

            if (isExpired) {
                frm.set_intro(
                    `<div class="productix-alert productix-alert-danger">
                        ⚠️ License EXPIRED on ${frm.doc.valid_until}.
                        Renew to restore full write access.
                    </div>`,
                    false
                );
                frm.page.set_indicator('Expired', 'red');
            } else if (isExpiringSoon) {
                frm.set_intro(
                    `<div class="productix-alert productix-alert-warning">
                        ⏰ License expires in ${daysLeft} day(s) on ${frm.doc.valid_until}.
                        Please renew soon.
                    </div>`,
                    false
                );
                frm.page.set_indicator('Expiring Soon', 'orange');
            } else {
                frm.set_intro(
                    `<div class="productix-alert productix-alert-success">
                        ✅ License active. Valid until ${frm.doc.valid_until}
                        (${daysLeft} days remaining).
                    </div>`,
                    false
                );
                frm.page.set_indicator('Active', 'green');
            }

            // Renew button
            frm.add_custom_button(__('Renew License (+12 months)'), function() {
                frappe.prompt([
                    {label: 'Payment Reference', fieldname: 'payment_ref', fieldtype: 'Data',
                     description: 'Optional — payment transaction ID for audit trail'},
                ], (values) => {
                    frm.call('renew', {
                        months: 12,
                        payment_ref: values.payment_ref || null,
                        webhook_id: null,
                    }).then(r => {
                        if (r.message && r.message.renewed) {
                            frappe.show_alert({ message: `License renewed until ${r.message.valid_until}`, indicator: 'green' });
                            frm.reload_doc();
                        }
                    });
                }, 'Renew License');
            }, __('Actions')).addClass('btn-primary');
        }
    },

    before_save: function(frm) {
        // Auto-generate key if empty (new doc)
        if (frm.is_new() && !frm.doc.license_key) {
            frm.set_value('license_key', frappe.utils.get_random(32).toUpperCase());
        }
    }
});
