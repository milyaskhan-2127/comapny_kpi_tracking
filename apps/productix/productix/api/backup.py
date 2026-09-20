import datetime
import gzip
import json
import os
import shutil
import frappe
from frappe import _
from frappe.utils import cint, get_site_path, get_url
from frappe.utils.data import convert_utc_to_system_timezone
from productix.kpi_tracking.security.permissions import is_kpi_admin


def _check_admin_permission():
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw(_("Please login to access backups."), frappe.AuthenticationError)

    if user == "Administrator" or "System Manager" in frappe.get_roles() or is_kpi_admin():
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
    if "-database.sql" in fn or fn.endswith(".sql.gz") or fn.endswith(".sql"):
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
            "label": "Site Configuration",
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
                    "download_url": f"/api/method/productix.api.backup.download_backup_file?filename={item}"
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
                    download_url = f"/api/method/productix.api.backup.download_backup_file?filename={filename}"
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
def restore_backup_file(filename):
    """
    Restore database records from an uploaded or available .sql, .sql.gz, or .json backup file.
    """
    _check_admin_permission()

    if not filename:
        frappe.throw(_("Filename is required."))

    clean_filename = os.path.basename(filename)
    backup_dir = get_site_path("private", "backups")
    file_path = os.path.join(backup_dir, clean_filename)

    if not os.path.exists(file_path):
        # Also check root apps directory
        alt_path = os.path.join("/home/frappe/frappe-bench/apps/productix", clean_filename)
        if os.path.exists(alt_path):
            file_path = alt_path
        else:
            frappe.throw(_(f"Backup file '{clean_filename}' was not found."))

    try:
        count_restored = 0
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
            count_restored = _restore_json_data(data)
        else:
            frappe.throw(_("Direct restore supports .sql, .sql.gz, or .json backup files."))

        frappe.db.commit()
        frappe.clear_cache()

        return {
            "success": True,
            "message": _(f"Backup '{clean_filename}' restored successfully ({count_restored} queries/records executed)!"),
            "backups_data": get_backups_list()
        }
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(f"Error restoring backup: {e}", "Backup Manager")
        frappe.throw(_(f"Failed to restore backup: {str(e)}"))


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
    statements = sql_text.split(";\n")
    executed = 0
    for stmt in statements:
        s = stmt.strip()
        if s and not s.startswith("--") and not s.startswith("/*"):
            try:
                frappe.db.sql(s)
                executed += 1
            except Exception:
                pass
    frappe.db.sql("SET FOREIGN_KEY_CHECKS=1;")
    frappe.db.commit()
    return executed


def _restore_json_data(data):
    """Restore from JSON backup data by completely overriding existing records (no merge)."""
    frappe.db.sql("SET FOREIGN_KEY_CHECKS=0;")
    count = 0

    # Clean existing records first to guarantee full overwrite instead of merge
    if "kpi_data_entries" in data:
        frappe.db.sql("TRUNCATE TABLE `tabKPI Data Entry`;")
        frappe.db.sql("TRUNCATE TABLE `tabKPI Data Entry Value`;")
    if "kpi_alerts" in data:
        frappe.db.sql("TRUNCATE TABLE `tabKPI Alert`;")
    if "kpi_predictions" in data:
        frappe.db.sql("TRUNCATE TABLE `tabKPI Prediction`;")
    if "kpi_operational_data" in data:
        frappe.db.sql("TRUNCATE TABLE `tabKPI Operational Data`;")
        frappe.db.sql("TRUNCATE TABLE `tabKPI Operational Data Value`;")

    # 1. KPI Data Entries
    for e in data.get("kpi_data_entries", []):
        try:
            frappe.db.sql(
                """INSERT INTO `tabKPI Data Entry` (`name`, `creation`, `modified`, `modified_by`, `owner`, `docstatus`, `kpi`, `department`, `entry_date`, `period`, `actual_value`, `target_value`, `achievement_percentage`, `status`, `entered_by`)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (e.get("name"), e.get("creation") or e.get("entry_date"), e.get("modified") or e.get("entry_date"), "Administrator", "Administrator", 1, e.get("kpi"), e.get("department"), e.get("entry_date"), e.get("period"), e.get("actual_value"), e.get("target_value"), e.get("achievement_percentage"), e.get("status"), "Administrator")
            )
            count += 1
        except Exception:
            pass

    # 2. KPI Alerts
    for a in data.get("kpi_alerts", []):
        try:
            frappe.db.sql(
                """INSERT INTO `tabKPI Alert` (`name`, `creation`, `modified`, `modified_by`, `owner`, `docstatus`, `alert_type`, `subject`, `severity`, `status`, `department`, `kpi`, `trigger_period`, `message`, `trigger_value`, `threshold_value`, `sender`, `sender_name`, `sender_role`)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (a.get("name"), a.get("creation"), a.get("creation"), "Administrator", "Administrator", 0, a.get("alert_type"), a.get("subject"), a.get("severity"), a.get("status"), a.get("department"), a.get("kpi"), a.get("trigger_period"), a.get("message"), a.get("trigger_value"), a.get("threshold_value"), "Administrator", "System Intelligence Agent", "System")
            )
            count += 1
        except Exception:
            pass

    # 3. KPI Predictions
    for p in data.get("kpi_predictions", []):
        try:
            frappe.db.sql(
                """INSERT INTO `tabKPI Prediction` (`name`, `creation`, `modified`, `modified_by`, `owner`, `docstatus`, `kpi`, `department`, `prediction_date`, `target_period`, `predicted_value`, `actual_value`, `variance`, `variance_percentage`, `accuracy`, `status`, `confidence`)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (p.get("name"), p.get("prediction_date"), p.get("prediction_date"), "Administrator", "Administrator", 0, p.get("kpi"), p.get("department"), p.get("prediction_date"), p.get("target_period"), p.get("predicted_value"), p.get("actual_value"), p.get("variance"), p.get("variance_percentage"), p.get("accuracy"), p.get("status"), p.get("confidence"))
            )
            count += 1
        except Exception:
            pass

    frappe.db.sql("SET FOREIGN_KEY_CHECKS=1;")
    frappe.db.commit()
    return count
