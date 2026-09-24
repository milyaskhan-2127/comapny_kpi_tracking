"""
Productix override for Batch DocType.
Allows flexible expiry management (non-expiring lots when has_expiry is unchecked),
and supports batch certificate attachment / tracking.
"""
import frappe
from frappe.utils import add_days, flt, today

try:
    from erpnext.stock.doctype.batch.batch import Batch
    BASE_CLASS = Batch
except Exception:
    from frappe.model.document import Document
    BASE_CLASS = Document


class ProductixBatch(BASE_CLASS):

    def set_expiry_date(self):
        # If user explicitly specified no expiry, allow batch without expiry date
        if self.get("has_expiry") == 0 or self.get("has_expiry") is False:
            self.expiry_date = None
            return

        if self.expiry_date:
            return

        has_expiry_date, shelf_life_in_days = frappe.db.get_value(
            "Item", self.item, ["has_expiry_date", "shelf_life_in_days"]
        )

        if has_expiry_date and shelf_life_in_days:
            posting_date = today()
            if (
                self.reference_doctype in ["Stock Entry", "Purchase Receipt", "Purchase Invoice"]
                and self.reference_name
            ):
                posting_date = frappe.db.get_value(
                    self.reference_doctype, self.reference_name, "posting_date"
                ) or today()
            self.expiry_date = add_days(posting_date, flt(shelf_life_in_days))
