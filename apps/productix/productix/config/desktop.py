from frappe import _

def get_data():
    return [
        {
            "module_name": "Recipe Management",
            "color": "#e74c3c",
            "icon": "octicon octicon-repo",
            "label": _("Recipe Management"),
            "type": "module",
        },
        {
            "module_name": "Subscription Management",
            "color": "#3498db",
            "icon": "octicon octicon-key",
            "label": _("Subscription"),
            "type": "module",
        },
        {
            "module_name": "Instruction Room",
            "color": "#27ae60",
            "icon": "octicon octicon-comment-discussion",
            "label": _("Instruction Room"),
            "type": "module",
        },
        {
            "module_name": "Alerts",
            "color": "#f39c12",
            "icon": "octicon octicon-bell",
            "label": _("Alerts"),
            "type": "module",
        },
        {
            "module_name": "KPI Tracking",
            "color": "#4C51BF",
            "icon": "octicon octicon-graph",
            "label": _("KPI Tracking"),
            "type": "module",
        },
    ]
