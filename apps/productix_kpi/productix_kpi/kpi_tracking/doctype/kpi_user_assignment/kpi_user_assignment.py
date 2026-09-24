import frappe
from frappe.model.document import Document


class KPIUserAssignment(Document):
    def validate(self):
        if not self.user:
            frappe.throw("User is required")

        role_str = str(self.role or "").strip()
        is_admin = role_str in ("Admin", "KPI Admin", "System Manager")

        # Select compatible option based on doctype field definition
        field_opts = (self.meta.get_field("role").options or "").split("\n")
        if is_admin:
            self.role = "Admin" if "Admin" in field_opts else ("KPI Admin" if "KPI Admin" in field_opts else role_str)
        else:
            self.role = "Employee" if "Employee" in field_opts else ("KPI Contributor" if "KPI Contributor" in field_opts else role_str)

        # If role is Employee, department is strictly required
        if not is_admin:
            if not self.department:
                frappe.throw("Department is required for Employee role")
            if not frappe.db.exists("KPI Department", {"name": self.department, "is_active": 1}):
                frappe.throw(f"Active Department '{self.department}' does not exist")

        # Ensure single active department for non-admin user
        if self.is_active and not is_admin:
            existing = frappe.db.get_all(
                "KPI User Assignment",
                filters={
                    "user": self.user,
                    "is_active": 1,
                    "name": ["!=", self.name or ""],
                },
                fields=["name", "department", "role"]
            )
            for e in existing:
                frappe.db.set_value("KPI User Assignment", e.name, "is_active", 0)

    def on_update(self):
        self._sync_user_roles()

    def on_trash(self):
        self._remove_assigned_roles()

    def _sync_user_roles(self):
        if not self.user or not frappe.db.exists("User", self.user):
            return

        user_doc = frappe.get_doc("User", self.user)
        is_admin = self.role in ("Admin", "KPI Admin")

        if self.is_active:
            target_role = "KPI Admin" if is_admin else "KPI Contributor"
            other_role = "KPI Contributor" if is_admin else "KPI Admin"

            # Remove opposite role if present
            user_doc.roles = [r for r in user_doc.roles if r.role != other_role]

            # Add target role if missing
            if target_role not in [r.role for r in user_doc.roles]:
                user_doc.append("roles", {"role": target_role})

            # Ensure Desk User is assigned so user can log in
            if "Desk User" not in [r.role for r in user_doc.roles]:
                user_doc.append("roles", {"role": "Desk User"})

            # For Employee, strictly remove any Recipe / Manufacturing / System Manager roles
            if not is_admin:
                recipe_and_admin_roles = {
                    "System Manager", "Administrator", "Factory Admin",
                    "Assistant System Administrator", "Production Manager",
                    "Store Keeper", "Purchase Manager"
                }
                user_doc.roles = [r for r in user_doc.roles if r.role not in recipe_and_admin_roles]

            user_doc.save(ignore_permissions=True)
        else:
            has_other_active = frappe.db.exists("KPI User Assignment", {
                "user": self.user,
                "is_active": 1,
                "name": ["!=", self.name]
            })
            if not has_other_active:
                self._remove_assigned_roles()

    def _remove_assigned_roles(self):
        if not self.user or not frappe.db.exists("User", self.user):
            return
        user_doc = frappe.get_doc("User", self.user)
        kpi_roles = {"KPI Admin", "KPI Employee", "KPI Manager", "KPI Contributor"}
        user_doc.roles = [r for r in user_doc.roles if r.role not in kpi_roles]
        user_doc.save(ignore_permissions=True)
