import frappe
import json
from frappe.model.document import Document
from frappe.utils import flt, now_datetime, nowdate, random_string


class ProductionOrder(Document):

    def autoname(self):
        if not self.order_number:
            date_str = nowdate().replace("-", "")
            self.order_number = f"PO-{date_str}-{random_string(4).upper()}"
        self.name = self.order_number

    def before_insert(self):
        if not self.order_number:
            self.autoname()
        if not self.status:
            self.status = "Pending"
        if not self.get("created_by_user"):
            self.created_by_user = frappe.session.user
        if not self.get("created_by_name"):
            self.created_by_name = frappe.utils.get_fullname(frappe.session.user) or frappe.session.user

    def after_insert(self):
        try:
            from productix.alerts.doctype.ai_agent_log.ai_agent_log import log_event
            user_name = self.created_by_name or frappe.utils.get_fullname(frappe.session.user) or frappe.session.user
            log_event(
                action_type="System",
                status="Info",
                details=f"Production Order {self.order_number} created by {user_name} ({frappe.session.user}) for {self.quantity} unit(s) of '{self.recipe_name or self.recipe}'. Total Cost: ${flt(self.total_cost):,.2f}.",
                items_affected=self.recipe_name or self.recipe or "",
            )
        except Exception:
            pass

    def before_save(self):
        if not self.order_number:
            if self.name:
                self.order_number = self.name
            else:
                self.autoname()
        self._calculate_cost()
        if not self.get("created_by_user"):
            self.created_by_user = self.owner or frappe.session.user
        if not self.get("created_by_name"):
            self.created_by_name = frappe.utils.get_fullname(self.created_by_user) or self.created_by_user

    def validate(self):
        if flt(self.quantity) <= 0:
            frappe.throw("Quantity must be greater than zero.")
        self._calculate_cost()

    def _calculate_cost(self):
        if not self.recipe:
            return
        recipe = frappe.get_cached_doc("Recipe", self.recipe)
        qty = flt(self.quantity) or 1
        self.base_cost = flt(recipe.bom_cost) * qty
        extras_total = sum(
            flt(e.quantity) * self._get_unit_cost(e.ingredient)
            for e in (self.order_extras or []) if e.ingredient
        )
        self.extras_cost = extras_total * qty
        self.total_cost = self.base_cost + self.extras_cost

    def _get_unit_cost(self, item_code):
        if not item_code:
            return 0.0
        price = frappe.db.get_value("Item Price",
            {"item_code": item_code, "price_list": "Standard Buying"}, "price_list_rate")
        if not price:
            price = frappe.db.get_value("Item", item_code, "valuation_rate")
        return flt(price)

    @frappe.whitelist()
    def validate_stock(self):
        """
        Check stock availability for this production order instance.
        """
        return check_order_stock(self.recipe, self.quantity, self.order_extras)

    @frappe.whitelist()
    def start_production(self):
        if self.status != "Pending":
            frappe.throw(f"Cannot start — order is currently '{self.status}'.")

        from productix.recipe_management.utils.fefo_utils import consume_stock_fefo
        result = consume_stock_fefo(
            self.recipe,
            self.quantity,
            self.name,
            self.order_extras
        )

        errors = result.get("errors", []) if isinstance(result, dict) else result
        if errors:
            frappe.throw(
                "Cannot start production — insufficient stock:\n<ul>" +
                "".join(f"<li>{e}</li>" for e in errors) +
                "</ul>"
            )

        stock_entry_name = result.get("stock_entry") if isinstance(result, dict) else None
        if stock_entry_name:
            self.db_set("stock_entry", stock_entry_name)

        user = frappe.session.user
        user_name = frappe.utils.get_fullname(user) or user
        self.db_set("started_by_name", user_name)
        self.db_set("status", "In Progress", update_modified=True)

        try:
            from productix.alerts.doctype.ai_agent_log.ai_agent_log import log_event
            log_event(
                action_type="System",
                status="Success",
                details=f"Production run started on {self.order_number} ({self.recipe_name or self.recipe}) by {user_name} ({user}). Stock deducted via Stock Entry {stock_entry_name or ''}.",
                items_affected=self.recipe_name or self.recipe or "",
            )
        except Exception:
            pass

        frappe.msgprint(
            f"✅ Production started. Stock deducted using FEFO via Stock Entry {stock_entry_name or ''}.",
            indicator="green", alert=True
        )

    @frappe.whitelist()
    def complete_production(self):
        if self.status != "In Progress":
            frappe.throw("Order must be 'In Progress' to complete.")
        user = frappe.session.user
        user_name = frappe.utils.get_fullname(user) or user
        self.db_set("completed_by_name", user_name)
        self.db_set("status", "Completed", update_modified=True)

        try:
            from productix.alerts.doctype.ai_agent_log.ai_agent_log import log_event
            log_event(
                action_type="System",
                status="Success",
                details=f"Production Order {self.order_number} ({self.recipe_name or self.recipe}, Qty: {self.quantity}) marked COMPLETED by {user_name} ({user}).",
                items_affected=self.recipe_name or self.recipe or "",
            )
        except Exception:
            pass

        frappe.msgprint("✅ Production order completed successfully.", indicator="green", alert=True)

    @frappe.whitelist()
    def cancel_production(self):
        if self.status not in ("Pending", "In Progress"):
            frappe.throw("Only Pending or In Progress orders can be cancelled.")

        user = frappe.session.user
        user_name = frappe.utils.get_fullname(user) or user
        self.db_set("completed_by_name", f"Cancelled by {user_name}")

        # If In Progress and stock was deducted, reverse the Stock Entry
        if self.status == "In Progress":
            if self.stock_entry and frappe.db.exists("Stock Entry", self.stock_entry):
                try:
                    se = frappe.get_doc("Stock Entry", self.stock_entry)
                    if se.docstatus == 1:
                        se.cancel()
                except Exception as e:
                    frappe.logger().warning(f"Stock Entry cancel rollback: {e}")
                    frappe.db.set_value("Stock Entry", self.stock_entry, "docstatus", 2)

            self.db_set("status", "Cancelled", update_modified=True)
            try:
                from productix.alerts.doctype.ai_agent_log.ai_agent_log import log_event
                log_event(
                    action_type="System",
                    status="Warning",
                    details=f"Production Order {self.order_number} ({self.recipe_name or self.recipe}) CANCELLED by {user_name} ({user}). Stock restored.",
                    items_affected=self.recipe_name or self.recipe or "",
                )
            except Exception:
                pass
            frappe.msgprint("Production order cancelled and stock restored to inventory.", indicator="orange", alert=True)
        else:
            self.db_set("status", "Cancelled", update_modified=True)
            try:
                from productix.alerts.doctype.ai_agent_log.ai_agent_log import log_event
                log_event(
                    action_type="System",
                    status="Warning",
                    details=f"Pending Production Order {self.order_number} was cancelled by {user_name} ({user}).",
                    items_affected=self.recipe_name or self.recipe or "",
                )
            except Exception:
                pass
            frappe.msgprint("Production order cancelled.", indicator="orange", alert=True)

    def on_trash(self):
        if self.status == "In Progress":
            frappe.throw(
                "Cannot delete an In Progress production order. Cancel it first to reverse stock."
            )
        if self.status == "Completed":
            frappe.throw(
                "Cannot delete a Completed production order."
            )
        # Clean up any linked consumption logs
        frappe.db.delete("Consumption Log", {"production_order": self.name})


@frappe.whitelist()
def check_order_stock(recipe, quantity=1, order_extras=None):
    """
    Standalone whitelisted method to check stock availability for any recipe and quantity.
    Accessible from client-side JS on new unsaved forms without requiring doc persistence.
    """
    if not recipe:
        return {"is_ready": True, "ingredients": [], "shortages": [], "message": ""}

    if isinstance(order_extras, str):
        try:
            order_extras = json.loads(order_extras)
        except Exception:
            order_extras = []

    from productix.recipe_management.utils.fefo_utils import check_availability
    ingredients = check_availability(recipe, quantity, order_extras)
    shortages = [i for i in ingredients if not i.get("is_available")]
    return {
        "is_ready": len(shortages) == 0,
        "ingredients": ingredients,
        "shortages": shortages,
        "message": (
            "✅ All ingredients available in stock."
            if not shortages else
            f"⚠️ Insufficient stock for {len(shortages)} ingredient(s)."
        )
    }


def has_permission(doc=None, ptype="read", user=None, *args, **kwargs):
    return True
