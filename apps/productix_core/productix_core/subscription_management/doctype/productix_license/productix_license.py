import frappe
from frappe.model.document import Document
from frappe.utils import getdate, today, add_months, now_datetime, random_string


class ProductixLicense(Document):

    def autoname(self):
        if not self.license_key:
            self.license_key = self._generate_key()
        self.name = self.license_key

    def before_insert(self):
        if not self.license_key:
            self.autoname()
        if not self.activated_on:
            self.activated_on = today()

    def _generate_key(self):
        """Generate a unique UUID-style license key."""
        import uuid
        return str(uuid.uuid4()).upper()

    def validate(self):
        if self.is_active and self.valid_until:
            if getdate(self.valid_until) < getdate(today()):
                self.is_active = 0
                frappe.msgprint(
                    "License date is in the past — marked as Inactive.",
                    indicator="orange"
                )

    def is_valid(self):
        """Check if this license is currently valid."""
        return (
            bool(self.is_active) and
            bool(self.valid_until) and
            getdate(self.valid_until) >= getdate(today())
        )

    def days_remaining(self):
        if not self.valid_until:
            return -1
        return (getdate(self.valid_until) - getdate(today())).days

    @frappe.whitelist()
    def renew(self, months=12, payment_ref=None, webhook_id=None):
        """
        Renew the license by N months.
        Idempotent: same webhook_id will not double-renew.
        """
        months = int(months)

        # Idempotency check
        if webhook_id and self.last_webhook_id == str(webhook_id):
            frappe.msgprint(
                "This webhook was already processed — no duplicate renewal applied.",
                indicator="blue"
            )
            return {"renewed": False, "reason": "duplicate_webhook"}

        # Base date: extend from current valid_until or today
        base = self.valid_until if self.valid_until else today()
        new_expiry = add_months(getdate(base), months)

        self.valid_until = new_expiry
        self.is_active = 1
        self.last_renewed_on = today()
        self.renewal_count = (self.renewal_count or 0) + 1

        if payment_ref:
            self.last_payment_ref = str(payment_ref)
        if webhook_id:
            self.last_webhook_id = str(webhook_id)

        self.save(ignore_permissions=True)
        frappe.db.commit()

        frappe.msgprint(
            f"✅ License renewed successfully until {new_expiry}.",
            indicator="green"
        )
        return {"renewed": True, "valid_until": str(new_expiry)}
