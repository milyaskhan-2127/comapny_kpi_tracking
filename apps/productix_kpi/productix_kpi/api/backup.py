import datetime
import gzip
import json
import os
import shutil
import frappe
from frappe import _
from frappe.utils import cint, get_site_path, get_url
from frappe.utils.data import convert_utc_to_system_timezone
from productix_kpi.kpi_tracking.security.permissions import is_kpi_admin


def _check_admin_permission():
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw(_("Please login to access backups."), frappe.AuthenticationError)

    user_roles = frappe.get_roles() or []
    if (
        user == "Administrator"
        or "System Manager" in user_roles
        or "Administrator" in user_roles
        or "KPI Admin" in user_roles
        or "Factory Admin" in user_roles
        or "Productix Admin" in user_roles
        or is_kpi_admin()
    ):
        return True

    frappe.throw(_("Access restricted: Only Administrators and System Managers can manage backups."), frappe.PermissionError)


def _format_size(size_in_bytes):
    if size_in_bytes >= 1024 * 1024 * 1024:
        return f"{size_in_bytes / (1024 * 1024 * 1024):.2f} GB"
    elif size_in_bytes >= 1024 * 1024:
        return f"{size_in_bytes / (1024 * 1024):.2f} MB"
    elif size_in_bytes >= 1024:
        return f"{size_in_bytes / 1024:.2f} KB"
    else:
        return f"{size_in_bytes} Bytes"


def _get_file_type(filename):
    fn = filename.lower()
    if "kpi_backup" in fn or "kpi_tracking" in fn or "kpi-" in fn or "-kpi" in fn:
        return {
            "key": "kpi_json",
            "label": "KPI Tracking JSON Backup",
            "badge_color": "purple",
            "icon": "target",
            "is_db": False
        }
    elif "-database.sql" in fn or fn.endswith(".sql.gz") or fn.endswith(".sql"):
        return {
            "key": "database",
            "label": "Database Backup",
            "badge_color": "blue",
            "icon": "database",
            "is_db": True
        }
    elif "-private-files" in fn:
        return {
            "key": "private_files",
            "label": "Private Files Archive",
            "badge_color": "purple",
            "icon": "lock",
            "is_db": False
        }
    elif "-files.tar" in fn or "-files." in fn:
        return {
            "key": "public_files",
            "label": "Public Files Archive",
            "badge_color": "green",
            "icon": "folder",
            "is_db": False
        }
    elif "site_config" in fn or fn.endswith(".json"):
        return {
            "key": "config",
            "label": "Site Configuration / JSON",
            "badge_color": "orange",
            "icon": "settings",
            "is_db": False
        }
    elif fn.endswith(".tar") or fn.endswith(".zip") or fn.endswith(".gz"):
        return {
            "key": "archive",
            "label": "Archive / Uploaded Backup",
            "badge_color": "grey",
            "icon": "archive",
            "is_db": False
        }
    else:
        return {
            "key": "other",
            "label": "Backup File",
            "badge_color": "grey",
            "icon": "file",
            "is_db": False
        }


@frappe.whitelist()
def get_backups_list():
    """Fetch all backup files in private/backups directory with metadata and download URLs."""
    _check_admin_permission()

    backup_dir = get_site_path("private", "backups")
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir, exist_ok=True)

    files_list = []
    total_size = 0
    db_count = 0
    files_count = 0

    try:
        entries = os.listdir(backup_dir)
    except Exception as e:
        frappe.log_error(f"Error listing backups directory: {e}", "Backup Manager")
        entries = []

    for item in entries:
        full_path = os.path.join(backup_dir, item)
        if os.path.isfile(full_path):
            try:
                st = os.stat(full_path)
                size_bytes = st.st_size
                mtime = st.st_mtime
                dt_obj = datetime.datetime.fromtimestamp(mtime)
                formatted_date = dt_obj.strftime("%Y-%m-%d %H:%M:%S")

                ft = _get_file_type(item)
                total_size += size_bytes
                if ft["key"] == "database":
                    db_count += 1
                else:
                    files_count += 1

                files_list.append({
                    "filename": item,
                    "type": ft["key"],
                    "type_label": ft["label"],
                    "badge_color": ft["badge_color"],
                    "icon": ft["icon"],
                    "is_db": ft["is_db"],
                    "can_restore": item.endswith(".sql") or item.endswith(".sql.gz") or item.endswith(".json"),
                    "size_bytes": size_bytes,
                    "size_formatted": _format_size(size_bytes),
                    "mtime": mtime,
                    "created_at": formatted_date,
                    "download_url": f"/api/method/productix_kpi.api.backup.download_backup_file?filename={item}"
                })
            except Exception as e:
                continue

    # Sort newest first
    files_list.sort(key=lambda x: x["mtime"], reverse=True)

    return {
        "success": True,
        "backups": files_list,
        "total_count": len(files_list),
        "db_count": db_count,
        "files_count": files_count,
        "total_size_formatted": _format_size(total_size),
        "latest_backup": files_list[0]["created_at"] if files_list else "No backups yet"
    }


@frappe.whitelist()
def take_immediate_backup(with_files=False, backup_type="all"):
    """
    Create a backup immediately in real-time and return direct download links.
    backup_type: 'all' (Database + Files), 'db' (Database only), 'files' (Files only)
    """
    _check_admin_permission()

    from frappe.utils.backups import backup

    include_files = bool(with_files or backup_type in ["all", "files", "1", 1, True, "true"])

    try:
        backup_result = backup(with_files=include_files)

        created_files = []
        main_download_url = None

        if backup_result:
            for key, file_path in backup_result.items():
                if file_path and isinstance(file_path, str):
                    filename = os.path.basename(file_path)
                    download_url = f"/api/method/productix_kpi.api.backup.download_backup_file?filename={filename}"
                    created_files.append({
                        "key": key,
                        "filename": filename,
                        "download_url": download_url
                    })
                    if "database" in key or filename.endswith(".sql.gz"):
                        main_download_url = download_url

        if not main_download_url and created_files:
            main_download_url = created_files[0]["download_url"]

        list_data = get_backups_list()

        return {
            "success": True,
            "message": _("Backup created successfully!"),
            "created_files": created_files,
            "main_download_url": main_download_url,
            "backups_data": list_data
        }
    except Exception as e:
        frappe.log_error(f"Error creating immediate backup: {e}", "Backup Manager")
        frappe.throw(_(f"Failed to create backup: {str(e)}"))


@frappe.whitelist()
def download_backup_file(filename):
    """Directly stream the requested backup file to the user's browser."""
    _check_admin_permission()

    if not filename:
        frappe.throw(_("Filename is required."))

    clean_filename = os.path.basename(filename)
    backup_dir = get_site_path("private", "backups")
    file_path = os.path.join(backup_dir, clean_filename)

    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        frappe.throw(_(f"Backup file '{clean_filename}' was not found on the server."), frappe.DoesNotExistError)

    try:
        with open(file_path, "rb") as f:
            file_content = f.read()

        frappe.local.response.filename = clean_filename
        frappe.local.response.filecontent = file_content
        frappe.local.response.type = "download"
    except Exception as e:
        frappe.log_error(f"Error reading backup file for download: {e}", "Backup Manager")
        frappe.throw(_(f"Could not read backup file: {str(e)}"))


@frappe.whitelist()
def delete_backup_file(filename):
    """Delete a specific backup file from private/backups."""
    _check_admin_permission()

    if not filename:
        frappe.throw(_("Filename is required."))

    clean_filename = os.path.basename(filename)
    backup_dir = get_site_path("private", "backups")
    file_path = os.path.join(backup_dir, clean_filename)

    if not os.path.exists(file_path):
        frappe.throw(_(f"File '{clean_filename}' does not exist."))

    try:
        os.remove(file_path)
        return {
            "success": True,
            "message": _(f"Backup file '{clean_filename}' deleted successfully."),
            "backups_data": get_backups_list()
        }
    except Exception as e:
        frappe.log_error(f"Error deleting backup file: {e}", "Backup Manager")
        frappe.throw(_(f"Failed to delete backup file: {str(e)}"))


@frappe.whitelist()
def upload_backup_file():
    """
    Handle uploading a backup file (.sql, .sql.gz, .tar, .json, .zip) to private/backups.
    """
    _check_admin_permission()

    if "file" not in frappe.request.files:
        frappe.throw(_("No file was uploaded."))

    uploaded_file = frappe.request.files["file"]
    original_filename = uploaded_file.filename

    if not original_filename:
        frappe.throw(_("Invalid filename."))

    clean_filename = os.path.basename(original_filename)
    allowed_extensions = (".sql.gz", ".sql", ".tar", ".gz", ".json", ".zip", ".tar.gz")

    if not any(clean_filename.lower().endswith(ext) for ext in allowed_extensions):
        frappe.throw(_(f"Invalid file type. Allowed formats: {', '.join(allowed_extensions)}"))

    backup_dir = get_site_path("private", "backups")
    os.makedirs(backup_dir, exist_ok=True)

    target_path = os.path.join(backup_dir, clean_filename)

    # If file with same name exists, prepend timestamp
    if os.path.exists(target_path):
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_")
        clean_filename = f"{ts}{clean_filename}"
        target_path = os.path.join(backup_dir, clean_filename)

    try:
        uploaded_file.save(target_path)
        file_size = os.path.getsize(target_path)

        return {
            "success": True,
            "message": _(f"Backup '{clean_filename}' uploaded successfully ({_format_size(file_size)})."),
            "filename": clean_filename,
            "size_formatted": _format_size(file_size),
            "backups_data": get_backups_list()
        }
    except Exception as e:
        frappe.log_error(f"Error saving uploaded backup: {e}", "Backup Manager")
        frappe.throw(_(f"Failed to save uploaded backup: {str(e)}"))


@frappe.whitelist()
def restore_backup_file(filename, confirm=0):
    """
    Restore database records from an uploaded or available .sql, .sql.gz, or .json backup file.

    Fail-fast guard: the caller MUST pass confirm=1. Any preview
    (preview_backup_file) must be shown to the user first; this method
    refuses to touch the database otherwise.
    """
    _check_admin_permission()

    if not filename:
        frappe.throw(_("Filename is required."))

    if not cint(confirm):
        frappe.throw(_("Restore cancelled: validation required. "
                       "Call preview_backup_file first, then confirm with confirm=1."))

    clean_filename = os.path.basename(filename)
    backup_dir = get_site_path("private", "backups")
    file_path = os.path.join(backup_dir, clean_filename)

    if not os.path.exists(file_path):
        frappe.throw(_(f"Backup file '{clean_filename}' was not found."))

    try:
        count_restored = 0
        skipped_note = ""
        if clean_filename.endswith(".sql.gz"):
            with gzip.open(file_path, "rt", encoding="utf-8", errors="ignore") as f:
                sql_text = f.read()
            count_restored = _execute_sql_dump(sql_text)
        elif clean_filename.endswith(".sql"):
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                sql_text = f.read()
            count_restored = _execute_sql_dump(sql_text)
        elif clean_filename.endswith(".json"):
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
            restored_stats = _restore_json_data(data)
            count_restored = restored_stats["inserted"] + restored_stats["skipped"]
            skipped_note = f" ({restored_stats['skipped']} records skipped)" if restored_stats.get("skipped") else ""
        else:
            frappe.throw(_("Direct restore supports .sql, .sql.gz, or .json backup files."))

        frappe.db.commit()
        frappe.clear_cache()

        return {
            "success": True,
            "message": _(f"Backup '{clean_filename}' restored successfully ({count_restored} queries/records executed{skipped_note})!"),
            "backups_data": get_backups_list()
        }
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(f"Error restoring backup: {e}", "Backup Manager")
        frappe.throw(_(f"Failed to restore backup: {str(e)}"))


@frappe.whitelist()
def preview_backup_file(filename):
    """
    Dry-run preview of a backup file BEFORE any restore.

    - For .json KPI backups: reports exact doctype -> record counts.
    - For .sql/.sql.gz dumps: reports the raw statement count.
    Returns metadata only; never touches the database.
    """
    _check_admin_permission()

    if not filename:
        frappe.throw(_("Filename is required."))

    clean_filename = os.path.basename(filename)
    backup_dir = get_site_path("private", "backups")
    file_path = os.path.join(backup_dir, clean_filename)

    if not os.path.exists(file_path):
        frappe.throw(_(f"Backup file '{clean_filename}' was not found."))

    size_bytes = os.path.getsize(file_path)

    result = {
        "filename": clean_filename,
        "size_formatted": _format_size(size_bytes),
        "kind": "other",
        "exists": True,
    }

    try:
        if clean_filename.endswith(".sql.gz"):
            with gzip.open(file_path, "rt", encoding="utf-8", errors="ignore") as f:
                sql_text = f.read()
            result["kind"] = "sql"
            stmts = [s.strip() for s in sql_text.split(";\n") if s.strip()]
            result["statement_count"] = len(stmts)
            result["note"] = "Executes the database dump with foreign key checks disabled. Entire tables are replaced."
            return result

        if clean_filename.endswith(".sql"):
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                sql_text = f.read()
            result["kind"] = "sql"
            stmts = [s.strip() for s in sql_text.split(";\n") if s.strip()]
            result["statement_count"] = len(stmts)
            result["note"] = "Executes the database dump with foreign key checks disabled. Entire tables are replaced."
            return result

        if clean_filename.endswith(".json"):
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
            result["kind"] = "json"
            result["note"] = "Restores KPI Tracking configuration + operational records. Recipe Management is never included."
            counts = {}
            if isinstance(data, dict):
                meta = data.get("export_metadata") or {}
                counts = meta.get("doctype_counts") or {}
                if not counts:
                    # Fall back to top-level keys
                    for key, val in data.items():
                        if isinstance(val, list):
                            counts[key] = len(val)
            result["doctype_counts"] = counts
            result["total_records"] = sum(v for v in counts.values() if isinstance(v, int))
            result["exported_at"] = (data.get("export_metadata") or {}).get("created_at")
            return result
    except (json.JSONDecodeError, OSError) as e:
        frappe.throw(_(f"Cannot read '{clean_filename}' as a valid backup: {str(e)}"))

    result["note"] = "This file is not a .sql / .sql.gz / .json backup and cannot be restored directly."
    return result


def _execute_sql_dump(sql_text):
    """Execute SQL statements with foreign key checks toggled."""
    import subprocess
    # Attempt fast pipe through mysql/mariadb client
    db_name = frappe.conf.db_name
    db_password = frappe.conf.db_password
    db_host = frappe.conf.db_host or "mariadb"
    db_port = str(frappe.conf.db_port or 3306)

    try:
        cmd = ["mariadb", f"-h{db_host}", f"-P{db_port}", f"-u{db_name}", f"-p{db_password}", db_name]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = proc.communicate(input=f"SET FOREIGN_KEY_CHECKS=0;\n{sql_text}\nSET FOREIGN_KEY_CHECKS=1;\n")
        if proc.returncode == 0:
            frappe.db.commit()
            return sql_text.count(";\n")
    except Exception:
        pass

    # Fallback to direct frappe.db.sql
    frappe.db.sql("SET FOREIGN_KEY_CHECKS=0;")
    executed = 0
    try:
        statements = sql_text.split(";\n")
        for stmt in statements:
            s = stmt.strip()
            if s and not s.startswith("--") and not s.startswith("/*"):
                try:
                    frappe.db.sql(s)
                    executed += 1
                except Exception:
                    pass
        frappe.db.commit()
    finally:
        frappe.db.sql("SET FOREIGN_KEY_CHECKS=1;")
    return executed


@frappe.whitelist()
def export_kpi_json_backup():
    """
    Dedicated KPI Tracking JSON Export.
    Exports all KPI Tracking configuration and operational records with JSON schema versioning.
    STRICT MANDATE: Excludes all Recipe Management DocTypes and data.
    """
    _check_admin_permission()

    backup_dir = get_site_path("private", "backups")
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"KPI_Backup_{timestamp}.json"
    file_path = os.path.join(backup_dir, filename)

    # 1. KPI Settings (Single)
    kpi_settings = frappe.get_single("KPI Settings").as_dict()

    # 2. Departments
    departments = frappe.db.get_all("KPI Department", fields=["*"])

    # 3. Business Units
    business_units = frappe.db.get_all("KPI Business Unit", fields=["*"])

    # 4. Variables
    variables = frappe.db.get_all("KPI Variable", fields=["*"])

    # 5. Formulas + child variables
    formulas = []
    for f in frappe.db.get_all("KPI Formula", fields=["*"]):
        child_vars = frappe.db.get_all("KPI Formula Variable", filters={"parent": f["name"]}, fields=["*"])
        f["variables"] = child_vars
        formulas.append(f)

    # 6. Templates + child items
    templates = []
    for t in frappe.db.get_all("KPI Template", fields=["*"]):
        items = frappe.db.get_all("KPI Template Item", filters={"parent": t["name"]}, fields=["*"])
        t["items"] = items
        templates.append(t)

    # 7. Definitions + child input definitions
    definitions = []
    for d in frappe.db.get_all("KPI Definition", fields=["*"]):
        inputs = frappe.db.get_all("KPI Input Definition", filters={"parent": d["name"]}, fields=["*"])
        d["inputs"] = inputs
        definitions.append(d)

    # 8. Operational Tables + child tables
    op_tables = []
    for ot in frappe.db.get_all("KPI Operational Table", fields=["*"]):
        vars_child = frappe.db.get_all("KPI Operational Table Variable", filters={"parent": ot["name"]}, fields=["*"])
        cust_child = frappe.db.get_all("KPI Operational Table Customer", filters={"parent": ot["name"]}, fields=["*"])
        ot["variables"] = vars_child
        ot["customers"] = cust_child
        op_tables.append(ot)

    # 9. User Assignments
    assignments = frappe.db.get_all("KPI User Assignment", fields=["*"])

    # 10. Data Entries + child values
    entries = []
    for de in frappe.db.get_all("KPI Data Entry", fields=["*"], order_by="entry_date asc"):
        vals = frappe.db.get_all("KPI Data Entry Value", filters={"parent": de["name"]}, fields=["*"])
        de["input_values"] = vals
        entries.append(de)

    # 11. Operational Data + child values
    op_data = []
    for od in frappe.db.get_all("KPI Operational Data", fields=["*"], order_by="entry_date asc"):
        od_vals = frappe.db.get_all("KPI Operational Data Value", filters={"parent": od["name"]}, fields=["*"])
        od["values"] = od_vals
        op_data.append(od)

    # 12. Alerts
    alerts = frappe.db.get_all("KPI Alert", fields=["*"], order_by="creation asc")

    # 13. Predictions
    predictions = frappe.db.get_all("KPI Prediction", fields=["*"], order_by="prediction_date asc")

    # 14. Machine Types + parameters
    machine_types = []
    if frappe.db.table_exists("Machine Type"):
        for mt in frappe.db.get_all("Machine Type", fields=["*"]):
            if frappe.db.table_exists("Machine Type Parameter"):
                mt_params = frappe.db.get_all("Machine Type Parameter", filters={"parent": mt["name"]}, fields=["*"])
                mt["parameters"] = mt_params
            machine_types.append(mt)

    # 15. Machines + linked KPIs
    machines = []
    if frappe.db.table_exists("Machine"):
        for m in frappe.db.get_all("Machine", fields=["*"]):
            if frappe.db.table_exists("Machine KPI Link"):
                m_links = frappe.db.get_all("Machine KPI Link", filters={"parent": m["name"]}, fields=["*"])
                m["linked_kpis"] = m_links
            machines.append(m)

    # 16. Machine Readings + child values
    machine_readings = []
    if frappe.db.table_exists("Machine Reading"):
        for mr in frappe.db.get_all("Machine Reading", fields=["*"], order_by="reading_date asc"):
            if frappe.db.table_exists("Machine Reading Value"):
                rvals = frappe.db.get_all("Machine Reading Value", filters={"parent": mr["name"]}, fields=["*"])
                mr["readings"] = rvals
                mr["reading_values"] = rvals
            machine_readings.append(mr)

    # 17. Machine Health Logs
    machine_health_logs = []
    if frappe.db.table_exists("Machine Health Log"):
        machine_health_logs = frappe.db.get_all("Machine Health Log", fields=["*"], order_by="log_date asc")

    backup_payload = {
        "export_metadata": {
            "title": "Productix KPI Tracking & Machine Health Dedicated JSON Backup",
            "version": "2.2",
            "app": "productix_kpi_tracking",
            "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "exported_by": frappe.session.user,
            "total_records": len(departments) + len(definitions) + len(entries) + len(alerts) + len(predictions) + len(machines) + len(machine_readings) + len(machine_health_logs),
            "doctype_counts": {
                "kpi_departments": len(departments),
                "kpi_definitions": len(definitions),
                "kpi_data_entries": len(entries),
                "kpi_alerts": len(alerts),
                "kpi_predictions": len(predictions),
                "kpi_operational_tables": len(op_tables),
                "kpi_user_assignments": len(assignments),
                "machine_types": len(machine_types),
                "machines": len(machines),
                "machine_readings": len(machine_readings),
                "machine_health_logs": len(machine_health_logs),
            }
        },
        "kpi_settings": kpi_settings,
        "kpi_departments": departments,
        "kpi_business_units": business_units,
        "kpi_variables": variables,
        "kpi_formulas": formulas,
        "kpi_templates": templates,
        "kpi_definitions": definitions,
        "kpi_operational_tables": op_tables,
        "kpi_user_assignments": assignments,
        "kpi_data_entries": entries,
        "kpi_operational_data": op_data,
        "kpi_alerts": alerts,
        "kpi_predictions": predictions,
        "machine_types": machine_types,
        "machines": machines,
        "machine_readings": machine_readings,
        "machine_health_logs": machine_health_logs,
    }

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(backup_payload, f, indent=2, default=str)

    file_size = os.path.getsize(file_path)
    download_url = f"/api/method/productix_kpi.api.backup.download_backup_file?filename={filename}"

    return {
        "success": True,
        "message": _(f"KPI Tracking JSON Backup generated successfully ({_format_size(file_size)})"),
        "filename": filename,
        "download_url": download_url,
        "size_formatted": _format_size(file_size),
        "backups_data": get_backups_list(),
    }


def _safe_insert_records(doctype, records, stats=None):
    """
    Safely and dynamically insert a list of record dicts into doctype's table.
    Filters dict keys to columns that actually exist in the DB table to avoid schema mismatch.
    Returns the number of rows inserted. If `stats` (dict) is provided, increments
    stats["inserted"] / stats["skipped"] as applicable for caller-side reporting.
    """
    if not frappe.db.table_exists(doctype) or not records:
        return 0
    cols = set(frappe.db.get_table_columns(doctype))
    count = 0
    table = f"tab{doctype}"
    for rec in records:
        if not isinstance(rec, dict):
            if stats is not None:
                stats["skipped"] += 1
            continue
        data = {k: v for k, v in rec.items() if k in cols and not isinstance(v, (list, dict))}
        if not data:
            if stats is not None:
                stats["skipped"] += 1
            continue
        col_names = list(data.keys())
        placeholders = ", ".join(["%s"] * len(col_names))
        quoted_cols = ", ".join([f"`{c}`" for c in col_names])
        values = [data[c] for c in col_names]
        sql = f"INSERT INTO `{table}` ({quoted_cols}) VALUES ({placeholders})"
        try:
            frappe.db.sql(sql, values)
            count += 1
            if stats is not None:
                stats["inserted"] += 1
        except Exception:
            if stats is not None:
                stats["skipped"] += 1
    return count


def _restore_json_data(data):
    """
    Restore KPI tracking configuration and operational records from JSON.
    Maintains relational dependency order and supports schema changes seamlessly.
    Always re-enables foreign key checks (try/finally). Returns
    {"inserted": n, "skipped": n}.
    """
    stats = {"inserted": 0, "skipped": 0}
    frappe.db.sql("SET FOREIGN_KEY_CHECKS=0;")
    try:
        # 1. KPI Settings
        if "kpi_settings" in data and isinstance(data["kpi_settings"], dict):
            try:
                settings_doc = frappe.get_doc("KPI Settings")
                for k, v in data["kpi_settings"].items():
                    if k not in ("name", "doctype", "modified", "creation", "modified_by", "owner"):
                        if hasattr(settings_doc, k):
                            setattr(settings_doc, k, v)
                settings_doc.save(ignore_permissions=True)
                stats["inserted"] += 1
            except Exception:
                stats["skipped"] += 1

        # 2. Departments
        if "kpi_departments" in data:
            frappe.db.sql("DELETE FROM `tabKPI Department`;")
            stats["inserted"] += _safe_insert_records("KPI Department", data.get("kpi_departments", []), stats)

        # 3. Business Units
        if "kpi_business_units" in data:
            frappe.db.sql("DELETE FROM `tabKPI Business Unit`;")
            stats["inserted"] += _safe_insert_records("KPI Business Unit", data.get("kpi_business_units", []), stats)

        # 4. Variables
        if "kpi_variables" in data:
            frappe.db.sql("DELETE FROM `tabKPI Variable`;")
            stats["inserted"] += _safe_insert_records("KPI Variable", data.get("kpi_variables", []), stats)

        # 5. Formulas & Variables
        if "kpi_formulas" in data:
            frappe.db.sql("DELETE FROM `tabKPI Formula`;")
            frappe.db.sql("DELETE FROM `tabKPI Formula Variable`;")
            stats["inserted"] += _safe_insert_records("KPI Formula", data.get("kpi_formulas", []), stats)
            for f in data.get("kpi_formulas", []):
                child_vars = f.get("variables", [])
                for cv in child_vars:
                    if not cv.get("parent"):
                        cv["parent"] = f.get("name")
                    if not cv.get("parenttype"):
                        cv["parenttype"] = "KPI Formula"
                    if not cv.get("parentfield"):
                        cv["parentfield"] = "variables"
                _safe_insert_records("KPI Formula Variable", child_vars, stats)

        # 6. Templates & Items
        if "kpi_templates" in data:
            frappe.db.sql("DELETE FROM `tabKPI Template`;")
            frappe.db.sql("DELETE FROM `tabKPI Template Item`;")
            stats["inserted"] += _safe_insert_records("KPI Template", data.get("kpi_templates", []), stats)
            for t in data.get("kpi_templates", []):
                items = t.get("items", [])
                for it in items:
                    if not it.get("parent"):
                        it["parent"] = t.get("name")
                    if not it.get("parenttype"):
                        it["parenttype"] = "KPI Template"
                    if not it.get("parentfield"):
                        it["parentfield"] = "items"
                _safe_insert_records("KPI Template Item", items, stats)

        # 7. KPI Definitions & Inputs
        if "kpi_definitions" in data:
            frappe.db.sql("DELETE FROM `tabKPI Definition`;")
            frappe.db.sql("DELETE FROM `tabKPI Input Definition`;")
            stats["inserted"] += _safe_insert_records("KPI Definition", data.get("kpi_definitions", []), stats)
            for kd in data.get("kpi_definitions", []):
                inputs = kd.get("inputs", [])
                for ki in inputs:
                    if not ki.get("parent"):
                        ki["parent"] = kd.get("name")
                    if not ki.get("parenttype"):
                        ki["parenttype"] = "KPI Definition"
                    if not ki.get("parentfield"):
                        ki["parentfield"] = "inputs"
                _safe_insert_records("KPI Input Definition", inputs, stats)

        # 8. User Assignments
        if "kpi_user_assignments" in data:
            frappe.db.sql("DELETE FROM `tabKPI User Assignment`;")
            stats["inserted"] += _safe_insert_records("KPI User Assignment", data.get("kpi_user_assignments", []), stats)

        # 9. Data Entries & Child Values
        if "kpi_data_entries" in data:
            frappe.db.sql("DELETE FROM `tabKPI Data Entry`;")
            frappe.db.sql("DELETE FROM `tabKPI Data Entry Value`;")
            stats["inserted"] += _safe_insert_records("KPI Data Entry", data.get("kpi_data_entries", []), stats)
            for e in data.get("kpi_data_entries", []):
                vals = e.get("input_values", [])
                for iv in vals:
                    if not iv.get("parent"):
                        iv["parent"] = e.get("name")
                    if not iv.get("parenttype"):
                        iv["parenttype"] = "KPI Data Entry"
                    if not iv.get("parentfield"):
                        iv["parentfield"] = "input_values"
                _safe_insert_records("KPI Data Entry Value", vals, stats)

        # 10. Alerts
        if "kpi_alerts" in data:
            frappe.db.sql("DELETE FROM `tabKPI Alert`;")
            stats["inserted"] += _safe_insert_records("KPI Alert", data.get("kpi_alerts", []), stats)

        # 11. Predictions
        if "kpi_predictions" in data:
            frappe.db.sql("DELETE FROM `tabKPI Prediction`;")
            stats["inserted"] += _safe_insert_records("KPI Prediction", data.get("kpi_predictions", []), stats)

        # 12. Operational Tables & Child Rows
        if "kpi_operational_tables" in data:
            frappe.db.sql("DELETE FROM `tabKPI Operational Table`;")
            frappe.db.sql("DELETE FROM `tabKPI Operational Table Variable`;")
            frappe.db.sql("DELETE FROM `tabKPI Operational Table Customer`;")
            stats["inserted"] += _safe_insert_records("KPI Operational Table", data.get("kpi_operational_tables", []), stats)
            for ot in data.get("kpi_operational_tables", []):
                vars_child = ot.get("variables", [])
                for vc in vars_child:
                    if not vc.get("parent"):
                        vc["parent"] = ot.get("name")
                    if not vc.get("parenttype"):
                        vc["parenttype"] = "KPI Operational Table"
                    if not vc.get("parentfield"):
                        vc["parentfield"] = "variables"
                _safe_insert_records("KPI Operational Table Variable", vars_child, stats)

                cust_child = ot.get("customers", [])
                for cc in cust_child:
                    if not cc.get("parent"):
                        cc["parent"] = ot.get("name")
                    if not cc.get("parenttype"):
                        cc["parenttype"] = "KPI Operational Table"
                    if not cc.get("parentfield"):
                        cc["parentfield"] = "customers"
                _safe_insert_records("KPI Operational Table Customer", cust_child, stats)

        # 13. Operational Data & Child Values
        if "kpi_operational_data" in data:
            frappe.db.sql("DELETE FROM `tabKPI Operational Data`;")
            frappe.db.sql("DELETE FROM `tabKPI Operational Data Value`;")
            stats["inserted"] += _safe_insert_records("KPI Operational Data", data.get("kpi_operational_data", []), stats)
            for od in data.get("kpi_operational_data", []):
                od_vals = od.get("values", [])
                for ov in od_vals:
                    if not ov.get("parent"):
                        ov["parent"] = od.get("name")
                    if not ov.get("parenttype"):
                        ov["parenttype"] = "KPI Operational Data"
                    if not ov.get("parentfield"):
                        ov["parentfield"] = "values"
                _safe_insert_records("KPI Operational Data Value", od_vals, stats)

        # 14. Machine Types & Parameters
        if "machine_types" in data and frappe.db.table_exists("Machine Type"):
            frappe.db.sql("DELETE FROM `tabMachine Type`;")
            if frappe.db.table_exists("Machine Type Parameter"):
                frappe.db.sql("DELETE FROM `tabMachine Type Parameter`;")
            stats["inserted"] += _safe_insert_records("Machine Type", data.get("machine_types", []), stats)
            for mt in data.get("machine_types", []):
                params = mt.get("parameters", [])
                for p in params:
                    if not p.get("parent"):
                        p["parent"] = mt.get("name")
                    if not p.get("parenttype"):
                        p["parenttype"] = "Machine Type"
                    if not p.get("parentfield"):
                        p["parentfield"] = "parameters"
                if frappe.db.table_exists("Machine Type Parameter"):
                    _safe_insert_records("Machine Type Parameter", params, stats)

        # 15. Machines & Linked KPIs
        if "machines" in data and frappe.db.table_exists("Machine"):
            frappe.db.sql("DELETE FROM `tabMachine`;")
            if frappe.db.table_exists("Machine KPI Link"):
                frappe.db.sql("DELETE FROM `tabMachine KPI Link`;")
            stats["inserted"] += _safe_insert_records("Machine", data.get("machines", []), stats)
            for m in data.get("machines", []):
                links = m.get("linked_kpis", [])
                for lk in links:
                    if not lk.get("parent"):
                        lk["parent"] = m.get("name")
                    if not lk.get("parenttype"):
                        lk["parenttype"] = "Machine"
                    if not lk.get("parentfield"):
                        lk["parentfield"] = "linked_kpis"
                if frappe.db.table_exists("Machine KPI Link"):
                    _safe_insert_records("Machine KPI Link", links, stats)

        # 16. Machine Readings & Child Values
        if "machine_readings" in data:
            if frappe.db.table_exists("Machine Reading"):
                frappe.db.sql("DELETE FROM `tabMachine Reading`;")
                stats["inserted"] += _safe_insert_records("Machine Reading", data.get("machine_readings", []), stats)
            if frappe.db.table_exists("Machine Reading Value"):
                frappe.db.sql("DELETE FROM `tabMachine Reading Value`;")
                for mr in data.get("machine_readings", []):
                    rvals = mr.get("readings") or mr.get("reading_values", [])
                    for rv in rvals:
                        if not rv.get("parent"):
                            rv["parent"] = mr.get("name")
                        if not rv.get("parenttype"):
                            rv["parenttype"] = "Machine Reading"
                        if not rv.get("parentfield"):
                            rv["parentfield"] = "readings"
                    _safe_insert_records("Machine Reading Value", rvals, stats)

        # 17. Machine Health Logs
        if "machine_health_logs" in data and frappe.db.table_exists("Machine Health Log"):
            frappe.db.sql("DELETE FROM `tabMachine Health Log`;")
            stats["inserted"] += _safe_insert_records("Machine Health Log", data.get("machine_health_logs", []), stats)

        frappe.db.commit()
    finally:
        frappe.db.sql("SET FOREIGN_KEY_CHECKS=1;")

    return stats
