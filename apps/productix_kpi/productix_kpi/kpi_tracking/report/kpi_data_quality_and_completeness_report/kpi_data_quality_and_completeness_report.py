import frappe
from frappe import _
from frappe.utils import flt, getdate, today
from productix_kpi.kpi_tracking.report.report_utils import (
    get_authorized_departments_for_report,
    get_status_badge,
)
from productix_kpi.kpi_tracking.services.period_engine import get_current_period


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart(data)
    summary = get_summary(data)
    return columns, data, None, chart, summary


def get_columns():
    return [
        {"label": _("Department"), "fieldname": "department_name", "fieldtype": "Data", "width": 140},
        {"label": _("KPI"), "fieldname": "kpi_name", "fieldtype": "Data", "width": 170},
        {"label": _("KPI Code"), "fieldname": "kpi", "fieldtype": "Link", "options": "KPI Definition", "width": 130},
        {"label": _("Frequency"), "fieldname": "frequency", "fieldtype": "Data", "width": 100},
        {"label": _("Reporting Period"), "fieldname": "period", "fieldtype": "Data", "width": 120},
        {"label": _("Expected Entries"), "fieldname": "expected_entries", "fieldtype": "Int", "width": 120},
        {"label": _("Submitted Entries"), "fieldname": "submitted_entries", "fieldtype": "Int", "width": 120},
        {"label": _("Missing Entries"), "fieldname": "missing_entries", "fieldtype": "Int", "width": 110},
        {"label": _("Complete Entries"), "fieldname": "complete_entries", "fieldtype": "Int", "width": 120},
        {"label": _("Incomplete Entries"), "fieldname": "incomplete_entries", "fieldtype": "Int", "width": 130},
        {"label": _("Invalid Values"), "fieldname": "invalid_values", "fieldtype": "Int", "width": 110},
        {"label": _("Null / Missing Values"), "fieldname": "null_values", "fieldtype": "Int", "width": 140},
        {"label": _("Last Submission"), "fieldname": "last_submission", "fieldtype": "Datetime", "width": 150},
        {"label": _("Data Completeness %"), "fieldname": "completeness_pct", "fieldtype": "Percent", "width": 140},
        {"label": _("Data Quality Status"), "fieldname": "quality_status", "fieldtype": "Data", "width": 140},
        {"label": _("Diagnosis / Issues"), "fieldname": "diagnosis", "fieldtype": "Data", "width": 260},
    ]


def get_data(filters):
    allowed_depts, active_dept = get_authorized_departments_for_report(filters)

    kpi_filters = {"is_active": 1, "department": ["in", allowed_depts]}
    if filters.get("kpi"):
        kpi_filters["name"] = filters.get("kpi")
    if filters.get("frequency") and filters.get("frequency") != "All":
        kpi_filters["frequency"] = filters.get("frequency")

    kpis = frappe.db.get_all(
        "KPI Definition",
        filters=kpi_filters,
        fields=[
            "name", "kpi_name", "department", "frequency", "target_value",
            "allow_negative", "minimum_acceptable", "direction", "source_type",
            "measurement_type"
        ],
        order_by="department asc, kpi_name asc",
    )

    if not kpis:
        return []

    dept_names = {}
    for d in frappe.db.get_all("KPI Department", fields=["name", "department_name"]):
        dept_names[d.name] = d.department_name or d.name

    # Pre-fetch input definitions for all KPIs
    kpi_inputs_map = {}
    all_inputs = frappe.db.get_all(
        "KPI Input Definition",
        fields=["parent", "field_name", "label", "field_type", "is_required", "minimum_value", "maximum_value"]
    )
    for inp in all_inputs:
        kpi_inputs_map.setdefault(inp.parent, []).append(inp)

    period_filter = filters.get("period")
    status_filter = filters.get("status")

    data = []

    for kpi in kpis:
        dept_code = kpi.department
        dept_display = dept_names.get(dept_code, dept_code)
        freq = kpi.frequency or "Daily"
        target_period = period_filter or get_current_period(freq, getdate(today()))

        # Check submitted entries for this KPI, dept, period
        entries = frappe.db.get_all(
            "KPI Data Entry",
            filters={"kpi": kpi.name, "department": dept_code, "period": target_period, "docstatus": 1},
            fields=["name", "actual_value", "target_value", "achievement_percentage", "status", "creation", "modified"],
            order_by="creation desc"
        )

        expected_count = 1
        submitted_count = len(entries)
        missing_count = max(0, expected_count - submitted_count)

        kpi_req_inputs = [i for i in kpi_inputs_map.get(kpi.name, []) if i.get("is_required")]
        total_req_inputs = len(kpi_req_inputs)

        complete_count = 0
        incomplete_count = 0
        invalid_count = 0
        null_count = 0
        diagnosis_notes = []

        if not entries:
            null_count = 1
            completeness_pct = 0.0
            quality_status = "Missing"
            diagnosis_notes.append("No entry submitted for period.")
            last_sub = None
        else:
            entry = entries[0]
            last_sub = entry.creation
            actual = entry.actual_value

            # Check actual value validity
            if actual is None:
                null_count += 1
                invalid_count += 1
                diagnosis_notes.append("Actual value is null/missing.")
            else:
                act_flt = flt(actual)
                if not kpi.allow_negative and act_flt < 0:
                    invalid_count += 1
                    diagnosis_notes.append(f"Negative value ({act_flt}) disallowed.")

                if kpi.minimum_acceptable is not None and act_flt < flt(kpi.minimum_acceptable) and kpi.direction != "Lower is Better":
                    diagnosis_notes.append(f"Value below minimum threshold ({kpi.minimum_acceptable}).")

            # Check child table input values if configured
            if total_req_inputs > 0:
                child_vals = frappe.db.get_all(
                    "KPI Data Entry Value",
                    filters={"parent": entry.name, "parenttype": "KPI Data Entry"},
                    fields=["field_name", "value"]
                )
                submitted_field_names = {cv.field_name: cv for cv in child_vals}

                valid_input_count = 0
                for req_inp in kpi_req_inputs:
                    fname = req_inp.field_name
                    cv = submitted_field_names.get(fname)
                    if not cv or cv.value is None:
                        incomplete_count += 1
                        diagnosis_notes.append(f"Missing required field '{req_inp.label or fname}'.")
                    else:
                        val_num = flt(cv.value)
                        if req_inp.minimum_value is not None and val_num < flt(req_inp.minimum_value):
                            invalid_count += 1
                            diagnosis_notes.append(f"Field '{req_inp.label or fname}' below minimum allowed ({req_inp.minimum_value}).")
                        elif req_inp.maximum_value is not None and val_num > flt(req_inp.maximum_value):
                            invalid_count += 1
                            diagnosis_notes.append(f"Field '{req_inp.label or fname}' exceeds maximum allowed ({req_inp.maximum_value}).")
                        else:
                            valid_input_count += 1

                completeness_pct = round((valid_input_count / total_req_inputs) * 100.0, 1)
            else:
                completeness_pct = 100.0 if (actual is not None and invalid_count == 0) else (50.0 if actual is not None else 0.0)

            if invalid_count > 0:
                quality_status = "Invalid"
            elif incomplete_count > 0:
                quality_status = "Incomplete"
            elif null_count > 0:
                quality_status = "Missing"
            elif completeness_pct < 100.0:
                quality_status = "Needs Review"
            else:
                complete_count = 1
                quality_status = "Complete"
                diagnosis_notes.append("All input records valid & complete.")

        # Apply status filter
        if status_filter and status_filter != "All" and quality_status != status_filter:
            continue

        data.append({
            "department_name": dept_display,
            "department": dept_code,
            "kpi_name": kpi.kpi_name,
            "kpi": kpi.name,
            "frequency": freq,
            "period": target_period,
            "expected_entries": expected_count,
            "submitted_entries": submitted_count,
            "missing_entries": missing_count,
            "complete_entries": complete_count,
            "incomplete_entries": incomplete_count,
            "invalid_values": invalid_count,
            "null_values": null_count,
            "last_submission": last_sub,
            "completeness_pct": completeness_pct,
            "quality_status": quality_status,
            "diagnosis": "; ".join(diagnosis_notes) if diagnosis_notes else "Verified OK",
        })

    return data


def get_chart(data):
    if not data:
        return None

    status_counts = {
        "Complete": sum(1 for d in data if d["quality_status"] == "Complete"),
        "Incomplete": sum(1 for d in data if d["quality_status"] == "Incomplete"),
        "Missing": sum(1 for d in data if d["quality_status"] == "Missing"),
        "Invalid": sum(1 for d in data if d["quality_status"] == "Invalid"),
        "Needs Review": sum(1 for d in data if d["quality_status"] == "Needs Review"),
    }

    labels = [k for k, v in status_counts.items() if v > 0]
    values = [status_counts[k] for k in labels]

    if not values:
        return None

    return {
        "data": {
            "labels": labels,
            "datasets": [
                {"name": _("KPI Quality Breakdown"), "values": values}
            ],
        },
        "type": "donut",
        "title": _("KPI Data Quality & Completeness Breakdown"),
        "colors": ["#27ae60", "#f39c12", "#e74c3c", "#c0392b", "#3498db"],
    }


def get_summary(data):
    if not data:
        return []

    total = len(data)
    complete = sum(1 for d in data if d["quality_status"] == "Complete")
    incomplete = sum(1 for d in data if d["quality_status"] == "Incomplete")
    missing = sum(1 for d in data if d["quality_status"] == "Missing")
    invalid = sum(1 for d in data if d["quality_status"] == "Invalid")

    comp_values = [flt(d["completeness_pct"]) for d in data]
    avg_completeness = round(sum(comp_values) / len(comp_values), 1) if comp_values else 0.0

    return [
        {"label": _("Total Audited KPIs"), "value": total, "datatype": "Int", "indicator": "blue"},
        {"label": _("Fully Complete"), "value": complete, "datatype": "Int", "indicator": "green"},
        {"label": _("Incomplete Submissions"), "value": incomplete, "datatype": "Int", "indicator": "orange" if incomplete > 0 else "green"},
        {"label": _("Missing Submissions"), "value": missing, "datatype": "Int", "indicator": "red" if missing > 0 else "green"},
        {"label": _("Invalid Data Entries"), "value": invalid, "datatype": "Int", "indicator": "red" if invalid > 0 else "green"},
        {"label": _("Overall Completeness"), "value": f"{avg_completeness}%", "datatype": "Data", "indicator": "green" if avg_completeness >= 80 else ("orange" if avg_completeness >= 60 else "red")},
    ]
