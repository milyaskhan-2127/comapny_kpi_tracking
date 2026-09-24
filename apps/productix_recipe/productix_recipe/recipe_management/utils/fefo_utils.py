"""
FEFO (First Expired, First Out) utility functions.
Used by Production Order to deduct stock dynamically in proper expiry order.
"""
import frappe
from frappe.utils import flt, getdate, today, add_days


def get_sorted_batches_fefo(item_code, warehouse=None):
    """
    Return active, non-empty batches sorted FEFO:
      1. Batches WITH expiry date, sorted earliest first
      2. Batches WITHOUT expiry date
    Expired batches are excluded.
    Returns: list of (batch_name, expiry_date, available_qty, warehouse_name)
    """
    today_date = getdate(today())
    conditions = "AND sle.is_cancelled = 0 AND b.disabled = 0"
    conditions += " AND (b.has_expiry = 0 OR b.expiry_date IS NULL OR b.expiry_date >= %s)"
    args = [item_code, str(today_date)]

    if warehouse:
        is_group = frappe.db.get_value("Warehouse", warehouse, "is_group")
        if not is_group:
            conditions += " AND sle.warehouse = %s"
            args.append(warehouse)

    res = frappe.db.sql(f"""
        SELECT sle.batch_no, sle.warehouse, b.expiry_date, b.has_expiry, IFNULL(SUM(sle.actual_qty), 0) as available_qty
        FROM `tabStock Ledger Entry` sle
        JOIN `tabBatch` b ON b.name = sle.batch_no
        WHERE sle.item_code = %s {conditions}
        GROUP BY sle.batch_no, sle.warehouse, b.expiry_date, b.has_expiry
        HAVING available_qty > 0
    """, tuple(args), as_dict=True)

    with_expiry = []
    without_expiry = []

    for row in res:
        b_name = row["batch_no"]
        exp = row["expiry_date"]
        has_exp = row.get("has_expiry", 1)
        qty = flt(row["available_qty"])
        wh = row["warehouse"]

        if exp and has_exp != 0:
            with_expiry.append((b_name, exp, qty, wh))
        else:
            without_expiry.append((b_name, None, qty, wh))

    # Sort with_expiry earliest date first (FEFO)
    with_expiry.sort(key=lambda x: getdate(x[1]))

    # If no stock ledger entries found with batch, fallback to Batch documents with available warehouse
    if not with_expiry and not without_expiry:
        batches = frappe.get_all("Batch", filters={"item": item_code, "disabled": 0}, fields=["name", "expiry_date", "has_expiry", "batch_qty"])
        def_wh = warehouse or _get_warehouse_with_stock(item_code) or _get_first_warehouse()
        for b in batches:
            qty = flt(b.batch_qty)
            if qty <= 0:
                continue
            if b.expiry_date and b.get("has_expiry") != 0:
                if getdate(b.expiry_date) < today_date:
                    continue
                with_expiry.append((b.name, b.expiry_date, qty, def_wh))
            else:
                without_expiry.append((b.name, None, qty, def_wh))
        with_expiry.sort(key=lambda x: getdate(x[1]))

    return with_expiry + without_expiry


def _get_batch_qty_in_warehouse(item_code, batch_no, warehouse=None):
    """Get actual stock qty for a batch from Stock Ledger."""
    conditions = "AND sle.is_cancelled = 0"
    args = [item_code, batch_no]

    if warehouse:
        is_group = frappe.db.get_value("Warehouse", warehouse, "is_group")
        if not is_group:
            conditions += " AND sle.warehouse = %s"
            args.append(warehouse)

    result = frappe.db.sql(f"""
        SELECT IFNULL(SUM(actual_qty), 0)
        FROM `tabStock Ledger Entry` sle
        WHERE sle.item_code = %s AND sle.batch_no = %s {conditions}
    """, tuple(args))
    return flt(result[0][0]) if result else 0.0


def get_usable_stock(item_code, warehouse=None):
    """
    Sum of all non-expired batch quantities for an item.
    This is the 'usable' stock for production planning.
    """
    today_date = getdate(today())
    conditions = "AND sle.is_cancelled = 0 AND b.disabled = 0"
    conditions += " AND (b.has_expiry = 0 OR b.expiry_date IS NULL OR b.expiry_date >= %s)"
    args = [item_code, str(today_date)]

    if warehouse:
        is_group = frappe.db.get_value("Warehouse", warehouse, "is_group")
        if not is_group:
            conditions += " AND sle.warehouse = %s"
            args.append(warehouse)

    result = frappe.db.sql(f"""
        SELECT IFNULL(SUM(sle.actual_qty), 0)
        FROM `tabStock Ledger Entry` sle
        JOIN `tabBatch` b ON b.name = sle.batch_no
        WHERE sle.item_code = %s {conditions}
    """, tuple(args))
    stock_qty = flt(result[0][0]) if result else 0.0

    if stock_qty <= 0:
        b_res = frappe.db.sql(f"""
            SELECT IFNULL(SUM(batch_qty), 0)
            FROM `tabBatch`
            WHERE item = %s AND disabled = 0 AND (has_expiry = 0 OR expiry_date IS NULL OR expiry_date >= %s)
        """, (item_code, str(today_date)))
        stock_qty = flt(b_res[0][0]) if b_res else 0.0

    if stock_qty <= 0:
        bin_res = frappe.db.sql("""
            SELECT IFNULL(SUM(actual_qty), 0) FROM `tabBin` WHERE item_code = %s
        """, (item_code,))
        stock_qty = flt(bin_res[0][0]) if bin_res else 0.0

    return stock_qty


def check_availability(recipe_name, quantity, order_extras=None, warehouse=None):
    """
    Check stock availability for all ingredients in a recipe.
    Returns list of shortage / availability dicts.
    """
    if not recipe_name:
        return []

    recipe = frappe.get_doc("Recipe", recipe_name)
    multiplier = flt(quantity) or 1
    items_to_check = []

    for i in recipe.items:
        if i.ingredient:
            items_to_check.append((i.ingredient, flt(i.quantity) * multiplier))

    if order_extras:
        for e in order_extras:
            ing = getattr(e, "ingredient", None) or (e.get("ingredient") if isinstance(e, dict) else None)
            qty = getattr(e, "quantity", None) or (e.get("quantity") if isinstance(e, dict) else 0)
            if ing and qty:
                items_to_check.append((ing, flt(qty) * multiplier))

    seen = {}
    for ingredient_code, required_qty in items_to_check:
        seen[ingredient_code] = seen.get(ingredient_code, 0) + required_qty

    details = []
    for ingredient_code, required_qty in seen.items():
        available = get_usable_stock(ingredient_code, warehouse)
        item_doc = frappe.get_cached_doc("Item", ingredient_code)
        shortage = max(0.0, required_qty - available)
        details.append({
            "ingredient": ingredient_code,
            "ingredient_name": item_doc.item_name or ingredient_code,
            "required": round(required_qty, 3),
            "available": round(available, 3),
            "shortage": round(shortage, 3),
            "unit": item_doc.stock_uom,
            "is_available": shortage <= 0,
        })

    return details


def consume_stock_fefo(recipe_name, quantity, production_order_name, order_extras=None, warehouse=None):
    """
    Deduct stock from inventory using FEFO logic.
    Creates a Material Issue Stock Entry.
    Returns dict {"errors": list_of_errors, "stock_entry": stock_entry_name}.
    """
    recipe = frappe.get_doc("Recipe", recipe_name)
    multiplier = flt(quantity) or 1

    requirements = {}
    for item in recipe.items:
        if item.ingredient:
            requirements[item.ingredient] = requirements.get(item.ingredient, 0) + flt(item.quantity) * multiplier

    if order_extras:
        for e in order_extras:
            ing = getattr(e, "ingredient", None) or (e.get("ingredient") if isinstance(e, dict) else None)
            qty = getattr(e, "quantity", None) or (e.get("quantity") if isinstance(e, dict) else 0)
            if ing and qty:
                requirements[ing] = requirements.get(ing, 0) + flt(qty) * multiplier

    # Pre-check all ingredients
    errors = []
    for ingredient_code, required_qty in requirements.items():
        available = get_usable_stock(ingredient_code, warehouse)
        if available < required_qty:
            item_name = frappe.db.get_value("Item", ingredient_code, "item_name") or ingredient_code
            errors.append(
                f"{item_name} ({ingredient_code}): need {required_qty:.2f}, have {available:.2f}"
            )

    if errors:
        return {"errors": errors, "stock_entry": None}

    # Determine default fallback warehouse
    default_warehouse = warehouse
    if not default_warehouse or frappe.db.get_value("Warehouse", default_warehouse, "is_group"):
        default_warehouse = (
            frappe.db.get_single_value("Stock Settings", "default_warehouse")
            or _get_first_warehouse()
        )

    # Build Stock Entry items using FEFO with dynamic warehouse deduction
    se_items = []
    for ingredient_code, required_qty in requirements.items():
        batches = get_sorted_batches_fefo(ingredient_code, warehouse)
        remaining = required_qty
        uom = frappe.db.get_value("Item", ingredient_code, "stock_uom")

        for (batch_name, _, batch_qty, batch_wh) in batches:
            if remaining <= 0:
                break

            consume_qty = min(flt(batch_qty), remaining)

            se_items.append({
                "item_code": ingredient_code,
                "qty": consume_qty,
                "s_warehouse": batch_wh or default_warehouse,
                "batch_no": batch_name,
                "use_serial_batch_fields": 1,
                "uom": uom,
                "stock_uom": uom,
                "conversion_factor": 1,
                "serial_no": "",
            })

            _log_consumption(production_order_name, ingredient_code, batch_name, consume_qty, uom)
            remaining -= consume_qty

        # Dynamic fallback if remaining > 0 (for non-batched items or unbatched portion)
        if remaining > 0:
            active_wh = _get_warehouse_with_stock(ingredient_code) or default_warehouse
            active_batch = frappe.db.get_value("Batch", {"item": ingredient_code, "disabled": 0}, "name")
            se_items.append({
                "item_code": ingredient_code,
                "qty": remaining,
                "s_warehouse": active_wh,
                "batch_no": active_batch or "",
                "use_serial_batch_fields": 1 if active_batch else 0,
                "uom": uom,
                "stock_uom": uom,
                "conversion_factor": 1,
                "serial_no": "",
            })
            _log_consumption(production_order_name, ingredient_code, active_batch, remaining, uom)
            remaining = 0

    if not se_items:
        return {"errors": ["No stock entries to create — check inventory."], "stock_entry": None}

    # Create and submit Stock Entry
    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type = "Material Issue"
    se.purpose = "Material Issue"
    company = (
        frappe.defaults.get_user_default("Company")
        or frappe.db.get_value("Company", {}, "name")
        or frappe.db.get_single_value("Global Defaults", "default_company")
    )
    if company:
        se.company = company
    se.remarks = f"FEFO Consumption — Production Order: {production_order_name}"
    se.posting_date = frappe.utils.today()
    se.posting_time = frappe.utils.nowtime()

    for item in se_items:
        if company and not item.get("company"):
            item["company"] = company
        se.append("items", item)

    se.insert(ignore_permissions=True)
    try:
        se.submit()
    except Exception as e:
        frappe.logger().warning(f"Stock Entry submit notice: {e}")

    return {"errors": [], "stock_entry": se.name}


def _log_consumption(production_order_name, ingredient_code, batch_name, qty, uom):
    """Create a Consumption Log record for audit trail."""
    try:
        order_number = frappe.db.get_value("Production Order", production_order_name, "order_number") or production_order_name
        frappe.get_doc({
            "doctype": "Consumption Log",
            "production_order": production_order_name,
            "order_number": order_number,
            "ingredient": ingredient_code,
            "batch": batch_name,
            "planned_quantity": qty,
            "actual_quantity": qty,
            "difference": 0.0,
            "unit": uom,
        }).insert(ignore_permissions=True)
    except Exception as e:
        frappe.log_error(f"Consumption log failed: {e}", "Productix FEFO")


def _get_warehouse_with_stock(item_code):
    """Find the warehouse holding actual stock for an item."""
    res = frappe.db.sql("""
        SELECT warehouse FROM `tabBin` WHERE item_code = %s AND actual_qty > 0 ORDER BY actual_qty DESC LIMIT 1
    """, (item_code,), as_dict=True)
    if res:
        return res[0]["warehouse"]
    sle_res = frappe.db.sql("""
        SELECT warehouse FROM `tabStock Ledger Entry` WHERE item_code = %s AND is_cancelled = 0 GROUP BY warehouse HAVING SUM(actual_qty) > 0 LIMIT 1
    """, (item_code,), as_dict=True)
    if sle_res:
        return sle_res[0]["warehouse"]
    return None


def _get_first_warehouse():
    """Dynamically get the main raw material / stores warehouse."""
    stores = frappe.get_all("Warehouse", filters={"disabled": 0, "is_group": 0, "warehouse_name": ["like", "%Stores%"]}, limit=1, pluck="name")
    if stores:
        return stores[0]
    def_wh = frappe.db.get_single_value("Stock Settings", "default_warehouse")
    if def_wh:
        return def_wh
    result = frappe.get_all("Warehouse", filters={"disabled": 0, "is_group": 0}, limit=1, pluck="name")
    if result:
        return result[0]
    return "Stores - T"


def apply_fefo_on_stock_entry(doc, method=None):
    """
    Hook: before Stock Entry save.
    If purpose is Material Issue and batch_no is not set, auto-select FEFO batch.
    """
    if doc.purpose != "Material Issue":
        return

    for item in doc.items:
        if not item.batch_no and item.item_code:
            batches = get_sorted_batches_fefo(item.item_code, item.s_warehouse)
            if batches:
                item.batch_no = batches[0][0]
                if not item.s_warehouse and len(batches[0]) >= 4 and batches[0][3]:
                    item.s_warehouse = batches[0][3]
                item.use_serial_batch_fields = 1

