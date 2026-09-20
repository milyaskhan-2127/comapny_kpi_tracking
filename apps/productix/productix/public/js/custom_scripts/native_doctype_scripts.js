// ============================================================
// Productix — Custom Scripts for ERPNext native DocTypes
// Item (Ingredient), Supplier, Batch, Purchase Receipt
// ============================================================

// ─────────────────────────────────────────────
// ITEM (Ingredient)
// ─────────────────────────────────────────────
frappe.ui.form.on('Item', {
    refresh: function(frm) {
        // Show stock info panel for batch-tracked items
        if (!frm.is_new() && frm.doc.has_batch_no) {
            frm.add_custom_button(__('View Batches'), function() {
                frappe.route_options = { item: frm.doc.name };
                frappe.set_route('List', 'Batch');
            }, __('Inventory'));

            frm.add_custom_button(__('Stock Ledger'), function() {
                frappe.route_options = { item_code: frm.doc.name };
                frappe.set_route('query-report', 'Stock Ledger');
            }, __('Inventory'));

            frm.add_custom_button(__('Inventory Status'), function() {
                frappe.route_options = { item_code: frm.doc.name };
                frappe.set_route('query-report', 'Inventory Status Report');
            }, __('Inventory'));

            // Show live stock summary
            frappe.call({
                method: 'productix.api.inventory.get_item_stock_info',
                args: { item_code: frm.doc.name },
                callback: function(r) {
                    if (!r.message) return;
                    const info = r.message;
                    const is_low = info.is_low_stock;
                    const color = is_low ? '#fef2f2' : '#f0fdf4';
                    const border = is_low ? '#fca5a5' : '#86efac';
                    const text_color = is_low ? '#991b1b' : '#065f46';
                    const icon = is_low ? '⚠️' : '✅';

                    frm.set_intro(
                        `<div style="background:${color};border:1px solid ${border};border-radius:8px;
                                     padding:12px 16px;color:${text_color}">
                            ${icon} <strong>Usable Stock:</strong> ${(info.usable_stock || 0).toFixed(2)} ${info.unit || ''}
                            &nbsp;|&nbsp;
                            <strong>Min:</strong> ${(info.min_stock_qty || 0).toFixed(2)}
                            &nbsp;|&nbsp;
                            <strong>Active Batches:</strong> ${info.active_batches || 0}
                            ${is_low ? ' &nbsp; <strong>⚠️ LOW STOCK</strong>' : ''}
                        </div>`,
                        false
                    );
                }
            });
        }

        // Ensure batch tracking is on for all productix items
        if (!frm.doc.has_batch_no) {
            frm.set_intro(
                '<div style="background:#fffbeb;border:1px solid #fde68a;border-radius:6px;padding:8px 12px;color:#92400e;font-size:13px;">💡 Enable <strong>"Has Batch No"</strong> and <strong>"Has Expiry Date"</strong> for automated FEFO stock management.</div>',
                false
            );
        }
    },

    has_batch_no: function(frm) {
        if (frm.doc.has_batch_no) {
            frm.set_value('has_expiry_date', 1);
            frappe.show_alert({
                message: 'Auto-enabled "Has Expiry Date" for batch-level FEFO tracking.',
                indicator: 'green'
            }, 5);
        }
    }
});

// ─────────────────────────────────────────────
// SUPPLIER
// ─────────────────────────────────────────────
frappe.ui.form.on('Supplier', {
    refresh: function(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__('GRN History'), function() {
                frappe.route_options = { supplier: frm.doc.name };
                frappe.set_route('List', 'Purchase Receipt');
            }, __('View'));

            frm.add_custom_button(__('Batch Traceability'), function() {
                frappe.route_options = { supplier: frm.doc.name };
                frappe.set_route('List', 'Batch');
            }, __('View'));

            frm.add_custom_button(__('Purchasing Report'), function() {
                frappe.route_options = { supplier: frm.doc.name };
                frappe.set_route('query-report', 'Purchasing Report');
            }, __('View'));

            // Status indicator
            const status = frm.doc.supplier_status || 'Active';
            frm.page.set_indicator(status, status === 'Active' ? 'green' : 'grey');
        }
    },

    supplier_status: function(frm) {
        const status = frm.doc.supplier_status || 'Active';
        frm.page.set_indicator(status, status === 'Active' ? 'green' : 'grey');
    }
});

// ─────────────────────────────────────────────
// BATCH (Inventory Batch)
// ─────────────────────────────────────────────
frappe.listview_settings['Batch'] = {
    add_fields: ['expiry_date', 'disabled', 'item', 'batch_qty', 'certificate_file', 'has_expiry'],
    get_indicator: function(doc) {
        let today = frappe.datetime.get_today();
        if (doc.disabled) {
            return [__('Disabled'), 'grey', 'disabled,=,1'];
        }
        if (!doc.expiry_date || doc.has_expiry === 0) {
            return [__('No Expiry'), 'blue', 'expiry_date,is,not set'];
        }
        let daysLeft = frappe.datetime.get_diff(doc.expiry_date, today);
        if (daysLeft < 0) {
            return [__('Expired'), 'red', 'expiry_date,<,' + today];
        } else if (daysLeft <= 7) {
            return [__('Expiring in ' + daysLeft + 'd'), 'orange', 'expiry_date,<=,' + frappe.datetime.add_days(today, 7)];
        } else {
            return [__('Healthy'), 'green', 'expiry_date,>,' + frappe.datetime.add_days(today, 7)];
        }
    },
    formatters: {
        certificate_file: function(value) {
            if (value) {
                return `<a href="${value}" target="_blank" onclick="event.stopPropagation();" class="badge" style="background:#dbeafe;color:#1e40af;text-decoration:none;padding:3px 8px;border-radius:4px;font-size:11px;font-weight:600;">📄 View COA</a>`;
            }
            return `<span style="color:#94a3b8;font-size:11px;">—</span>`;
        }
    }
};

frappe.ui.form.on('Batch', {
    refresh: function(frm) {
        if (!frm.is_new()) {
            let today = frappe.datetime.get_today();
            let hasExpiry = frm.doc.has_expiry !== 0 && frm.doc.expiry_date;
            let expiry = frm.doc.expiry_date;
            let daysLeft = expiry ? frappe.datetime.get_diff(expiry, today) : null;
            let certUrl = frm.doc.certificate_file || frm.doc.certificate_url;

            // Certificate Action Button
            if (certUrl) {
                frm.add_custom_button(__('📄 View Certificate / COA'), function() {
                    window.open(certUrl, '_blank');
                }).addClass('btn-primary');
            }

            let certBadgeHtml = certUrl
                ? `&nbsp;|&nbsp; 📄 <a href="${certUrl}" target="_blank" style="color:inherit;text-decoration:underline;font-weight:600;">View Batch Certificate</a>`
                : `&nbsp;|&nbsp; <span style="opacity:0.8;">(No Certificate Attached)</span>`;

            if (hasExpiry && expiry) {
                if (daysLeft < 0) {
                    frm.set_intro(
                        `<div style="background:#fef2f2;border:1px solid #fca5a5;border-radius:6px;padding:8px 12px;color:#991b1b;font-size:13px;">
                            🔴 <strong>EXPIRED</strong> on ${expiry} (${Math.abs(daysLeft)} days ago)
                            ${certBadgeHtml}
                        </div>`,
                        false
                    );
                    frm.page.set_indicator('Expired', 'red');
                } else if (daysLeft <= 7) {
                    frm.set_intro(
                        `<div style="background:#fffbeb;border:1px solid #fde68a;border-radius:6px;padding:8px 12px;color:#92400e;font-size:13px;">
                            🟠 Expiring in <strong>${daysLeft} days</strong> on ${expiry}
                            ${certBadgeHtml}
                        </div>`,
                        false
                    );
                    frm.page.set_indicator(`Expiring in ${daysLeft}d`, 'orange');
                } else {
                    frm.set_intro(
                        `<div style="background:#f0fdf4;border:1px solid #86efac;border-radius:6px;padding:8px 12px;color:#166534;font-size:13px;">
                            🟢 Healthy — expires ${expiry} (${daysLeft} days)
                            ${certBadgeHtml}
                        </div>`,
                        false
                    );
                    frm.page.set_indicator('Healthy', 'green');
                }
            } else {
                frm.set_intro(
                    `<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:8px 12px;color:#475569;font-size:13px;">
                        ℹ️ <strong>No Expiry Date Configured</strong> (Non-perishable lot)
                        ${certBadgeHtml}
                    </div>`,
                    false
                );
                frm.page.set_indicator('No Expiry', 'blue');
            }

            frm.add_custom_button(__('Stock Ledger'), function() {
                frappe.route_options = { batch_no: frm.doc.name };
                frappe.set_route('query-report', 'Stock Ledger');
            }, __('View'));
        }
    },

    has_expiry: function(frm) {
        if (!frm.doc.has_expiry) {
            frm.set_value('expiry_date', null);
        }
    }
});

// ─────────────────────────────────────────────
// PURCHASE RECEIPT (GRN)
// ─────────────────────────────────────────────
frappe.listview_settings['Purchase Receipt'] = {
    add_fields: ['supplier', 'status', 'posting_date', 'grand_total', 'shipment_certificate', 'received_by_name'],
    formatters: {
        shipment_certificate: function(value) {
            if (value) {
                return `<a href="${value}" target="_blank" onclick="event.stopPropagation();" class="badge" style="background:#dbeafe;color:#1e40af;text-decoration:none;padding:3px 8px;border-radius:4px;font-size:11px;font-weight:600;">📄 View COA</a>`;
            }
            return `<span style="color:#94a3b8;font-size:11px;">—</span>`;
        }
    }
};

frappe.ui.form.on('Purchase Receipt', {
    refresh: function(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__('GRN History'), function() {
                frappe.set_route('query-report', 'Purchasing Report');
            }, __('View'));

            frm.add_custom_button(__('Batch Expiry Report'), function() {
                frappe.set_route('query-report', 'Batch Expiry Report');
            }, __('View'));
        }

        let certUrl = frm.doc.shipment_certificate;
        if (certUrl) {
            frm.add_custom_button(__('📄 View Shipment COA'), function() {
                window.open(certUrl, '_blank');
            }).addClass('btn-primary');
        }

        frm.set_intro(
            '<div style="color:#2563eb;font-weight:500;">📦 <strong>Goods Received Note (GRN):</strong> Batch numbers are auto-generated. You can enter an Expiry Date and upload a Quality Certificate (COA) per item row or attach a master shipment certificate. Both are optional.</div>',
            false
        );
    },

    validate: function(frm) {
        let today = frappe.datetime.get_today();
        (frm.doc.items || []).forEach((item, idx) => {
            if (item.has_expiry && item.expiry_date && item.expiry_date < today) {
                frappe.msgprint({
                    message: `Row ${idx + 1}: Expiry date (${item.expiry_date}) for <b>${item.item_code}</b> cannot be in the past.`,
                    indicator: 'red',
                    title: 'Invalid Expiry Date'
                });
                frappe.validated = false;
            }
        });
    }
});

frappe.ui.form.on('Purchase Receipt Item', {
    item_code: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.item_code) {
            frappe.db.get_value('Item', row.item_code, ['has_expiry_date', 'has_batch_no']).then(r => {
                if (r && r.message) {
                    let hasExp = r.message.has_expiry_date ? 1 : 0;
                    frappe.model.set_value(cdt, cdn, 'has_expiry', hasExp);
                    if (!hasExp) {
                        frappe.model.set_value(cdt, cdn, 'expiry_date', null);
                    }
                }
            });
        }
    },

    has_expiry: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!row.has_expiry) {
            frappe.model.set_value(cdt, cdn, 'expiry_date', null);
        }
    },

    expiry_date: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.expiry_date) {
            let today = frappe.datetime.get_today();
            let daysLeft = frappe.datetime.get_diff(row.expiry_date, today);
            if (daysLeft < 0) {
                frappe.show_alert({
                    message: `⚠️ Expiry date for row ${row.idx} is in the past!`,
                    indicator: 'red'
                }, 5);
            } else if (daysLeft <= 7) {
                frappe.show_alert({
                    message: `⚠️ Item in row ${row.idx} expires in only ${daysLeft} day(s)!`,
                    indicator: 'orange'
                }, 5);
            }
        }
    }
});

// ─────────────────────────────────────────────
// USER (Staff / User Creation with Direct Password)
// ─────────────────────────────────────────────
frappe.ui.form.on('User', {
    onload: function(frm) {
        if (frm.is_new()) {
            frm.set_value('send_welcome_email', 0);
            if (frm.fields_dict['new_password']) {
                frm.set_df_property('new_password', 'hidden', 0);
            }
        }
    },
    refresh: function(frm) {
        if (frm.is_new()) {
            frm.set_value('send_welcome_email', 0);
            if (frm.fields_dict['new_password']) {
                frm.set_df_property('new_password', 'hidden', 0);
            }
            frm.set_intro(
                '<div style="background:#f0fdf4;border:1px solid #86efac;border-radius:6px;padding:10px 14px;color:#166534;font-size:13px;">' +
                '🔑 <strong>Direct Password Creation:</strong> Enter the user password in the Password field. The account is created ready for immediate login without email verification.' +
                '</div>',
                false
            );
        }
    }
});

