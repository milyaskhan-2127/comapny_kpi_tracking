"""
Productix override for Purchase Receipt.
Extends ERPNext's Purchase Receipt to:
- Auto-create and auto-increment Batch records per line when receiving goods
- Ensure serial number requirements do not block submission
- Link supplier to batch records
"""
import frappe
from erpnext.stock.doctype.purchase_receipt.purchase_receipt import PurchaseReceipt


class ProductixPurchaseReceipt(PurchaseReceipt):

    def validate(self):
        from productix_recipe.recipe_management.utils.grn_utils import before_purchase_receipt_validate
        before_purchase_receipt_validate(self)
        super().validate()

    def on_submit(self):
        super().on_submit()
        from productix_recipe.recipe_management.utils.grn_utils import on_purchase_receipt_submit
        on_purchase_receipt_submit(self)
