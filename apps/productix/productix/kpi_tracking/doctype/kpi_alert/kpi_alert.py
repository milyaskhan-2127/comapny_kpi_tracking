import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime
from productix.kpi_tracking.security.permissions import (
    is_kpi_admin,
    get_user_authorized_department,
)


class KPIAlert(Document):
    def validate(self):
        user = frappe.session.user
        if self.flags.ignore_permissions or frappe.flags.in_test or is_kpi_admin(user):
            return

        # Employees cannot create new alerts directly from Desk
        if self.is_new():
            frappe.throw(
                "Access denied: Only administrators can create new KPI alerts.",
                frappe.PermissionError
            )

        # Existing alert modification check for employees
        user_dept = get_user_authorized_department(user)
        if self.department and self.department != user_dept:
            frappe.throw(
                f"Access denied: You are only authorized to update alerts for department '{user_dept}'.",
                frappe.PermissionError
            )

        old_doc = self.get_doc_before_save()
        if old_doc and old_doc.department != self.department:
            frappe.throw(
                "Access denied: You cannot reassign this alert to another department.",
                frappe.PermissionError
            )

    def on_trash(self):
        user = frappe.session.user
        if self.flags.ignore_permissions or frappe.flags.in_test or is_kpi_admin(user):
            return

        frappe.throw(
            "Access denied: Only administrators have permission to delete KPI alerts.",
            frappe.PermissionError
        )

    @frappe.whitelist()
    def resolve(self):
        user = frappe.session.user
        if not is_kpi_admin(user):
            user_dept = get_user_authorized_department(user)
            if self.department and self.department != user_dept:
                frappe.throw(
                    f"Access denied: You cannot resolve alerts for department '{self.department}'.",
                    frappe.PermissionError
                )

        self.status = "Resolved"
        self.resolved_at = now_datetime()
        self.resolved_by = user
        self.save(ignore_permissions=True)
        self.flags.ignore_permissions = False
        return {"status": "ok", "message": "Alert resolved."}

    @frappe.whitelist()
    def acknowledge(self):
        user = frappe.session.user
        if not is_kpi_admin(user):
            user_dept = get_user_authorized_department(user)
            if self.department and self.department != user_dept:
                frappe.throw(
                    f"Access denied: You cannot acknowledge alerts for department '{self.department}'.",
                    frappe.PermissionError
                )

        self.status = "Acknowledged"
        self.save(ignore_permissions=True)
        self.flags.ignore_permissions = False
        return {"status": "ok", "message": "Alert acknowledged."}
