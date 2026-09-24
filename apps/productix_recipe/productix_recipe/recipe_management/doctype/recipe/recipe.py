import frappe
from frappe.model.document import Document
from frappe.utils import flt


class Recipe(Document):

    def before_insert(self):
        if not self.get("created_by_name"):
            self.created_by_name = frappe.utils.get_fullname(frappe.session.user) or frappe.session.user
        self.calculate_cost()

    def after_insert(self):
        try:
            from productix_core.productix_core.doctype.ai_agent_log.ai_agent_log import log_event
            user_name = self.created_by_name or frappe.utils.get_fullname(frappe.session.user) or frappe.session.user
            log_event(
                action_type="System",
                status="Info",
                details=f"New Recipe Formulation '{self.recipe_name}' ({self.category or 'General'}) created by {user_name} ({frappe.session.user}) with {len(self.items)} BOM items. Standard Cost: ${flt(self.bom_cost):,.2f}.",
                items_affected=self.recipe_name,
            )
        except Exception:
            pass

    def before_save(self):
        user_name = frappe.utils.get_fullname(frappe.session.user) or frappe.session.user
        self.modified_by_name = user_name
        if not self.get("created_by_name"):
            self.created_by_name = user_name
        self.calculate_cost()

    def validate(self):
        if not self.items:
            frappe.throw("Recipe must have at least one ingredient in the BOM.")
        if flt(self.serving_size) <= 0:
            frappe.throw("Serving size must be greater than zero.")
        self.calculate_cost()

    def calculate_cost(self):
        total = 0.0

        for item in self.items:
            unit_cost = self._get_item_price(item.ingredient)
            item.unit_cost = unit_cost
            item.amount = round(flt(item.quantity) * unit_cost, 4)
            total += item.amount

        for extra in self.extras:
            if extra.ingredient:
                unit_cost = self._get_item_price(extra.ingredient)
                if not extra.extra_cost or extra.extra_cost == 0:
                    extra.extra_cost = round(flt(extra.quantity) * unit_cost, 4)
            total += flt(extra.extra_cost)

        self.bom_cost = round(total, 2)
        serving_size = flt(self.serving_size)
        self.cost_per_serving = round(total / serving_size, 2) if serving_size > 0 else 0.0

    def _get_item_price(self, item_code):
        if not item_code:
            return 0.0
        price = frappe.db.get_value(
            "Item Price",
            {"item_code": item_code, "price_list": "Standard Buying"},
            "price_list_rate"
        )
        if not price:
            price = frappe.db.get_value("Item", item_code, "valuation_rate")
        return flt(price)

    def on_trash(self):
        # Block deletion if active production orders exist
        linked_orders = frappe.db.count("Production Order", {
            "recipe": self.name,
            "status": ["in", ["Pending", "In Progress"]]
        })
        if linked_orders:
            frappe.throw(
                f"Cannot delete Recipe '{self.recipe_name}' — it has {linked_orders} active Production Order(s)."
            )


def has_permission(doc=None, ptype="read", user=None, *args, **kwargs):
    return True
