frappe.listview_settings['Production Order'] = {
    add_fields: ['status', 'recipe_name', 'quantity', 'production_date', 'total_cost'],
    get_indicator: function(doc) {
        let status_color = {
            'Pending': 'orange',
            'In Progress': 'blue',
            'Completed': 'green',
            'Cancelled': 'red'
        };
        return [__(doc.status || 'Pending'), status_color[doc.status] || 'grey', 'status,=,' + doc.status];
    },
    hide_name_column: false
};
