frappe.ui.form.on('Production Order', {
    refresh: function(frm) {
        // Status indicator color
        let colors = {
            'Pending': 'orange',
            'In Progress': 'blue',
            'Completed': 'green',
            'Cancelled': 'grey'
        };
        frm.page.set_indicator(frm.doc.status || 'Pending', colors[frm.doc.status] || 'grey');

        if (!frm.is_new()) {
            // Action buttons based on status
            if (frm.doc.status === 'Pending') {
                frm.add_custom_button(__('▶ Start Production'), function() {
                    frappe.confirm(
                        'Confirm start? Required ingredients will be automatically allocated and deducted using FEFO (First Expired, First Out) batch priority.',
                        () => frm.call('start_production').then(() => frm.reload_doc())
                    );
                }).addClass('btn-primary');

                frm.add_custom_button(__('✕ Cancel Order'), function() {
                    frappe.confirm('Cancel this pending production order?', () =>
                        frm.call('cancel_production').then(() => frm.reload_doc())
                    );
                }).addClass('btn-danger');
            }

            if (frm.doc.status === 'In Progress') {
                frm.add_custom_button(__('✔ Mark Complete'), function() {
                    frappe.confirm('Mark this production run as Completed?', () =>
                        frm.call('complete_production').then(() => frm.reload_doc())
                    );
                }).addClass('btn-success');

                frm.add_custom_button(__('↺ Revert / Cancel'), function() {
                    frappe.confirm('Cancel this in-progress run and return all deducted stock back to inventory?', () =>
                        frm.call('cancel_production').then(() => frm.reload_doc())
                    );
                }).addClass('btn-danger');
            }

            // View Stock Entry (if stock was deducted)
            if (frm.doc.stock_entry) {
                frm.add_custom_button(__('Stock Entry'), function() {
                    frappe.set_route('Form', 'Stock Entry', frm.doc.stock_entry);
                }, __('View'));
            }

            // View Ingredient Sheet
            frm.add_custom_button(__('Ingredient Sheet'), function() {
                frappe.route_options = { production_order: frm.doc.name };
                frappe.set_route('query-report', 'Production Ingredient Sheet');
            }, __('View'));

            // View Consumption Log
            frm.add_custom_button(__('Consumption Log'), function() {
                frappe.route_options = { production_order: frm.doc.name };
                frappe.set_route('List', 'Consumption Log');
            }, __('View'));
        }

        // Live stock check
        if (frm.doc.recipe && (!frm.doc.status || frm.doc.status === 'Pending')) {
            frm.trigger('check_stock_availability');
        }
    },

    recipe: function(frm) {
        if (!frm.doc.recipe) {
            frm.clear_table('order_extras');
            frm.refresh_field('order_extras');
            frm.set_intro('');
            return;
        }

        // Load recipe extras as default order extras
        frappe.db.get_doc('Recipe', frm.doc.recipe).then(recipe => {
            frm.clear_table('order_extras');
            (recipe.extras || []).forEach(e => {
                let row = frm.add_child('order_extras');
                row.recipe_extra = e.name;
                row.extra_name = e.extra_name;
                row.ingredient = e.ingredient;
                row.ingredient_name = e.ingredient_name;
                row.base_quantity = e.quantity;
                row.quantity = e.quantity;
                row.unit = e.unit;
                row.portion_multiplier = '1x';
            });
            frm.refresh_field('order_extras');

            _recalculate(frm);
            frm.trigger('check_stock_availability');
        });
    },

    quantity: function(frm) {
        _recalculate(frm);
        if (frm.doc.recipe && (!frm.doc.status || frm.doc.status === 'Pending')) {
            frm.trigger('check_stock_availability');
        }
    },

    check_stock_availability: function(frm) {
        if (!frm.doc.recipe) return;

        frappe.call({
            method: 'productix.recipe_management.doctype.production_order.production_order.check_order_stock',
            args: {
                recipe: frm.doc.recipe,
                quantity: frm.doc.quantity || 1,
                order_extras: frm.doc.order_extras || []
            },
            callback: function(r) {
                if (!r.message) return;
                let res = r.message;
                if (res.is_ready) {
                    frm.set_intro(
                        `<div style="background:#f0fdf4;border:1px solid #86efac;border-radius:6px;padding:8px 14px;color:#166534;font-size:13px;">
                            🟢 <strong>Stock Available:</strong> All ingredients are in stock and ready for production.
                        </div>`,
                        false
                    );
                } else {
                    let shortageList = (res.shortages || []).map(s =>
                        `• <strong>${s.ingredient_name || s.ingredient}</strong>: need ${s.required} ${s.unit}, have ${s.available} ${s.unit} (short by ${s.shortage} ${s.unit})`
                    ).join('<br>');
                    frm.set_intro(
                        `<div style="background:#fef2f2;border:1px solid #fca5a5;border-radius:6px;padding:8px 14px;color:#991b1b;font-size:13px;">
                            ⚠️ <strong>Insufficient Stock:</strong><br>${shortageList}
                        </div>`,
                        false
                    );
                }
            }
        });
    }
});

frappe.ui.form.on('Production Order Extra', {
    portion_multiplier: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        let multiplier = parseInt((row.portion_multiplier || '1x').replace('x', '')) || 1;
        frappe.model.set_value(cdt, cdn, 'quantity', (row.base_quantity || 0) * multiplier);
        _recalculate(frm);
    },
    quantity: function(frm) {
        _recalculate(frm);
    }
});

function _recalculate(frm) {
    if (frm.doc.recipe) {
        frappe.db.get_value('Recipe', frm.doc.recipe, 'bom_cost').then(r => {
            if (r.message) {
                let qty = flt(frm.doc.quantity) || 1;
                let base = flt(r.message.bom_cost || 0) * qty;
                frm.set_value('base_cost', base);
                frm.set_value('total_cost', base + flt(frm.doc.extras_cost || 0));
            }
        });
    }
}
