import frappe
from frappe.model.document import Document
import re


def _normalize_code(value):
    """Sanitize a department code/name fragment to ^[A-Z][A-Z0-9_]*$."""
    raw = (value or "").upper().strip()
    raw = raw.replace("&", "AND").replace("-", "_").replace(" ", "_")
    cleaned = re.sub(r'[^A-Z0-9_]', '', raw)
    cleaned = re.sub(r'_+', '_', cleaned).strip('_')
    if not cleaned or not cleaned[0].isalpha():
        cleaned = f"DEP_{cleaned}" if cleaned else "DEP_NEW"
    return cleaned


# Tables that carry a plain Link column `department` -> KPI Department.
# They are updated defensively on rename so the canonical department name
# propagates everywhere even if frappe.rename_doc misses a table.
_RENAME_PROPAGATION_TABLES = [
    "KPI Definition",
    "KPI Data Entry",
    "KPI Alert",
    "KPI Prediction",
    "KPI User Assignment",
    "KPI Operational Table",
    "KPI Operational Data",
    "Machine",
    "KPI Business Unit",
    "KPI CEO Department Access",
    "KPI CEO KPI Access",
]


class KPIDepartment(Document):
    def validate(self):
        name = (self.department_name or "").strip()
        if not name:
            frappe.throw("Department Name is required")
        self.department_name = name

        if self.location:
            self.location = self.location.strip()

        # Department names must be unique (case-insensitive) — single source of truth.
        dup = frappe.db.sql("""
            SELECT name FROM `tabKPI Department`
            WHERE LOWER(TRIM(department_name)) = LOWER(%s) AND name != %s
            LIMIT 1
        """, (name, self.name or ""))
        if dup:
            frappe.throw(
                f"Department '{name}' already exists. Department names must be unique."
            )

        # Derive a canonical code from the name (optionally disambiguated by location).
        code_seed = name
        if self.location:
            code_seed += f" {self.location}"
        base_code = _normalize_code(code_seed)

        prior = (self.department_code or "").strip()
        prior_clean = _normalize_code(prior) if prior else ""

        if prior_clean and (prior_clean.startswith(base_code) or base_code.startswith(prior_clean)):
            self.department_code = prior_clean
        else:
            self.department_code = base_code

        self.department_code = self._unique_code(self.department_code)

        if not re.match(r'^[A-Z][A-Z0-9_]*$', self.department_code):
            frappe.throw(
                "Department Code must start with a letter and contain only uppercase letters, numbers, and underscores"
            )

        if self.weight is not None:
            try:
                self.weight = float(self.weight)
                if self.weight < 0:
                    frappe.throw("Department Weight cannot be negative")
            except ValueError:
                self.weight = 1.0
        else:
            self.weight = 1.0

    def _unique_code(self, code):
        candidate = code
        suffix = 2
        while True:
            exists = frappe.db.sql("""
                SELECT name FROM `tabKPI Department`
                WHERE department_code = %s AND name != %s
                LIMIT 1
            """, (candidate, self.name or ""))
            if not exists:
                return candidate
            candidate = f"{code}_{suffix}"
            suffix += 1

    def on_trash(self):
        if frappe.flags.in_test:
            return
        dept = self.name
        refs = []
        checks = [
            ("KPI Definition", "active KPI Definitions"),
            ("Machine", "linked Machines"),
            ("KPI User Assignment", "user assignments"),
            ("KPI Data Entry", "data entries"),
            ("KPI Alert", "alerts"),
            ("KPI Prediction", "predictions"),
            ("KPI Operational Table", "operational tables"),
            ("KPI Operational Data", "operational data"),
        ]
        for dt, label in checks:
            if not frappe.db.table_exists(dt):
                continue
            count = frappe.db.count(dt, {"department": dept})
            if count:
                refs.append(f"{count} {label}")
        if refs:
            frappe.throw(
                f"Cannot delete department '{dept}': it is referenced by {', '.join(refs)}. "
                "Deactivate the department instead, or remove the references first."
            )

    def after_rename(self, old, new, merge=False):
        """Propagate department (name == code) renames to every dependent table."""
        if merge or not old or old == new:
            return
        self._propagate_department_rename(old, new)

    @staticmethod
    def _propagate_department_rename(old, new):
        for dt in _RENAME_PROPAGATION_TABLES:
            try:
                if not frappe.db.table_exists(dt):
                    continue
                cols = frappe.db.get_table_columns(dt)
                if "department" not in cols:
                    continue
                frappe.db.sql(
                    "UPDATE `tab{}` SET department = %s WHERE department = %s".format(dt),
                    (new, old),
                )
            except Exception:
                continue

    def get_disambiguated_name(self):
        label = self.department_name or self.name
        if self.location:
            label += f" — {self.location}"
        code = self.department_code or self.name
        if code and code != label:
            label += f" [{code}]"
        return label