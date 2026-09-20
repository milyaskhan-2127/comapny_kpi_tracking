from __future__ import unicode_literals
from frappe import _


def get_data():
    return [
        {
            "label": _("Dashboards & AI Tools"),
            "items": [
                {
                    "type": "page",
                    "name": "kpi-company-overview",
                    "label": _("Company Overview"),
                    "description": _("Executive level KPI performance overview"),
                },
                {
                    "type": "page",
                    "name": "kpi-department-dashboard",
                    "label": _("Department Dashboard"),
                    "description": _("Departmental operational scorecard and metrics"),
                },
                {
                    "type": "page",
                    "name": "kpi-ai-assistant",
                    "label": _("AI Performance Assistant"),
                    "description": _("AI analysis and intelligent directives"),
                },
                {
                    "type": "page",
                    "name": "kpi-action-center",
                    "label": _("Action Center"),
                    "description": _("Management triage and operational alerts"),
                },
            ],
        },
        {
            "label": _("Data Entry & Operations"),
            "items": [
                {
                    "type": "page",
                    "name": "kpi-data-entry-page",
                    "label": _("Data Entry Portal"),
                    "description": _("Quick employee metric submission page"),
                },
                {
                    "type": "doctype",
                    "name": "KPI Data Entry",
                    "label": _("KPI Data Entries"),
                    "description": _("Direct KPI data submissions"),
                },
                {
                    "type": "doctype",
                    "name": "KPI Alert",
                    "label": _("KPI Alerts"),
                    "description": _("Operational alerts and notifications"),
                },
                {
                    "type": "doctype",
                    "name": "KPI Prediction",
                    "label": _("KPI Predictions"),
                    "description": _("Machine learning & regression projections"),
                },
            ],
        },
        {
            "label": _("Professional KPI Reports"),
            "items": [
                {
                    "type": "report",
                    "name": "KPI Performance and Variance Report",
                    "label": _("KPI Performance & Variance Report"),
                    "is_query_report": True,
                },
                {
                    "type": "report",
                    "name": "Department Performance Report",
                    "label": _("Department Performance Report"),
                    "is_query_report": True,
                },
                {
                    "type": "report",
                    "name": "KPI Trend and Forecast Report",
                    "label": _("KPI Trend & Forecast Report"),
                    "is_query_report": True,
                },
                {
                    "type": "report",
                    "name": "KPI Alert and Action Report",
                    "label": _("KPI Alert & Action Report"),
                    "is_query_report": True,
                },
                {
                    "type": "report",
                    "name": "KPI Data Quality and Completeness Report",
                    "label": _("KPI Data Quality & Completeness Report"),
                    "is_query_report": True,
                },
            ],
        },
        {
            "label": _("Configuration & Masters"),
            "items": [
                {
                    "type": "doctype",
                    "name": "KPI Definition",
                    "label": _("KPI Definitions"),
                    "description": _("Manage KPI library, thresholds and weights"),
                },
                {
                    "type": "doctype",
                    "name": "KPI Department",
                    "label": _("KPI Departments"),
                    "description": _("Configure tracking departments"),
                },
                {
                    "type": "doctype",
                    "name": "KPI Business Unit",
                    "label": _("KPI Business Units"),
                    "description": _("Configure tracking units and locations"),
                },
                {
                    "type": "doctype",
                    "name": "KPI User Assignment",
                    "label": _("KPI User Assignments"),
                    "description": _("Department and role assignments for staff"),
                },
                {
                    "type": "doctype",
                    "name": "KPI Settings",
                    "label": _("KPI Settings"),
                    "description": _("Global KPI engine parameters and defaults"),
                },
            ],
        },
    ]
