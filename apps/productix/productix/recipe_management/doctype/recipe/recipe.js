frappe.ui.form.on('Recipe', {
    refresh: function(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__('⚡ New Production Run'), function() {
                frappe.new_doc('Production Order', {
                    recipe: frm.doc.name,
                    recipe_name: frm.doc.recipe_name,
                });
            }).addClass('btn-primary');

            frm.add_custom_button(__('Production History'), function() {
                frappe.route_options = { recipe: frm.doc.name };
                frappe.set_route('List', 'Production Order');
            }, __('View'));

            frm.add_custom_button(__('Ingredient Sheet'), function() {
                let latest_order = null;
                frappe.db.get_list('Production Order', {
                    filters: { recipe: frm.doc.name, status: ['in', ['Pending', 'In Progress']] },
                    fields: ['name'],
                    order_by: 'production_date desc',
                    limit: 1
                }).then(orders => {
                    if (orders.length) {
                        frappe.route_options = { production_order: orders[0].name };
                        frappe.set_route('query-report', 'Production Ingredient Sheet');
                    } else {
                        frappe.msgprint('No active production orders found for this recipe.');
                    }
                });
            }, __('View'));

            frm.add_custom_button(__('Costing Report'), function() {
                frappe.route_options = { recipe_name: frm.doc.name };
                frappe.set_route('query-report', 'Recipe Costing');
            }, __('View'));
        }

        frm.set_intro(
            `<div style="font-size:13px;color:#1e40af;"><strong>Recipe:</strong> ${frm.doc.recipe_name || 'New Recipe'} &nbsp;|&nbsp; <strong>Serving Size:</strong> ${frm.doc.serving_size || 1} ${frm.doc.unit || 'Portion'}</div>`,
            false
        );
    },

    serving_size: function(frm) {
        frm.trigger('recalc');
    },

    validate: function(frm) {
        if (!frm.doc.items || frm.doc.items.length === 0) {
            frappe.msgprint({ message: 'Please add at least one ingredient to the recipe BOM.', indicator: 'red' });
            frappe.validated = false;
        }
    },

    recalc: function(frm) {
        let total = 0;
        (frm.doc.items || []).forEach(i => total += flt(i.amount || 0));
        (frm.doc.extras || []).forEach(e => total += flt(e.extra_cost || 0));
        let serving = flt(frm.doc.serving_size) || 1;
        frm.set_value('bom_cost', round_number(total, 2));
        frm.set_value('cost_per_serving', round_number(total / serving, 2));
    }
});

frappe.ui.form.on('Recipe Item', {
    ingredient: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.ingredient) {
            frappe.db.get_value('Item', row.ingredient, ['item_name', 'stock_uom', 'valuation_rate']).then(r => {
                if (r.message) {
                    let rate = flt(r.message.valuation_rate) || 0;
                    frappe.model.set_value(cdt, cdn, 'ingredient_name', r.message.item_name);
                    frappe.model.set_value(cdt, cdn, 'unit', r.message.stock_uom);
                    frappe.model.set_value(cdt, cdn, 'unit_cost', rate);
                    frappe.model.set_value(cdt, cdn, 'amount', (flt(row.quantity) || 1) * rate);
                    frm.trigger('recalc');
                }
            });
        }
    },
    quantity: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        let cost = flt(row.unit_cost) || 0;
        frappe.model.set_value(cdt, cdn, 'amount', (flt(row.quantity) || 0) * cost);
        frm.trigger('recalc');
    },
    items_remove: function(frm) {
        frm.trigger('recalc');
    }
});

frappe.ui.form.on('Recipe Extra', {
    ingredient: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.ingredient) {
            frappe.db.get_value('Item', row.ingredient, ['item_name', 'stock_uom', 'valuation_rate']).then(r => {
                if (r.message) {
                    let rate = flt(r.message.valuation_rate) || 0;
                    frappe.model.set_value(cdt, cdn, 'ingredient_name', r.message.item_name);
                    frappe.model.set_value(cdt, cdn, 'unit', r.message.stock_uom);
                    frappe.model.set_value(cdt, cdn, 'extra_cost', (flt(row.quantity) || 1) * rate);
                    frm.trigger('recalc');
                }
            });
        }
    },
    quantity: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.ingredient) {
            frappe.db.get_value('Item', row.ingredient, 'valuation_rate').then(r => {
                let rate = flt(r.message && r.message.valuation_rate) || 0;
                frappe.model.set_value(cdt, cdn, 'extra_cost', (flt(row.quantity) || 0) * rate);
                frm.trigger('recalc');
            });
        }
    },
    extra_cost: function(frm) {
        frm.trigger('recalc');
    },
    extras_remove: function(frm) {
        frm.trigger('recalc');
    }
});

function round_number(num, decimals=2) {
    return Math.round((num + Number.EPSILON) * Math.pow(10, decimals)) / Math.pow(10, decimals);
}
