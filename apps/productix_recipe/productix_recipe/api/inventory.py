import frappe
from frappe.utils import flt, getdate, today, add_days


@frappe.whitelist()
def get_user_role_context():
    """
    Dynamically resolve the active user's permissions and role context based on live database permissions.
    """
    user = frappe.session.user if frappe.session else "Guest"
    user_roles = frappe.get_roles(user) if user != "Guest" else []
    full_name = frappe.utils.get_fullname(user) if user != "Guest" else "Guest"

    # Dynamic permission checks directly using Frappe's permission engine
    can_create_recipe = frappe.has_permission("Recipe", "create", user=user) if user != "Guest" else False
    can_read_recipe = frappe.has_permission("Recipe", "read", user=user) if user != "Guest" else False
    can_create_production_order = frappe.has_permission("Production Order", "create", user=user) if user != "Guest" else False
    can_read_production_order = frappe.has_permission("Production Order", "read", user=user) if user != "Guest" else False
    can_receive_grn = frappe.has_permission("Purchase Receipt", "create", user=user) if user != "Guest" else False
    can_read_grn = frappe.has_permission("Purchase Receipt", "read", user=user) if user != "Guest" else False
    can_manage_roles = (frappe.has_permission("Role", "create", user=user) or frappe.has_permission("User", "create", user=user)) if user != "Guest" else False
    can_adjust_stock = frappe.has_permission("Stock Entry", "create", user=user) if user != "Guest" else False
    can_read_item = frappe.has_permission("Item", "read", user=user) if user != "Guest" else False
    can_read_batch = frappe.has_permission("Batch", "read", user=user) if user != "Guest" else False
    can_read_supplier = frappe.has_permission("Supplier", "read", user=user) if user != "Guest" else False
    can_create_supplier = frappe.has_permission("Supplier", "create", user=user) if user != "Guest" else False
    can_view_audit = frappe.has_permission("AI Agent Log", "read", user=user) if user != "Guest" else False

    is_factory_admin = bool(set(user_roles) & {"Administrator", "System Manager", "Factory Admin", "Productix Admin"})
    is_asst_admin = bool(set(user_roles) & {"Assistant System Administrator", "Productix Assistant Admin"}) and not is_factory_admin
    is_production = bool(set(user_roles) & {"Production Manager", "Productix Production Manager", "Manufacturing Manager", "Production User"}) and not is_factory_admin and not is_asst_admin
    is_store = bool(set(user_roles) & {"Store Keeper", "Productix Store Keeper", "Stock Manager", "Stock User"}) and not is_factory_admin and not is_asst_admin
    is_purchase = bool(set(user_roles) & {"Purchase Manager", "Productix Purchase Manager", "Purchase User", "Purchase Master Manager"}) and not is_factory_admin and not is_asst_admin
    is_staff = not (is_factory_admin or is_asst_admin or is_production or is_store or is_purchase)

    primary_role = "factory_admin" if is_factory_admin else (
        "asst_admin" if is_asst_admin else (
            "production" if is_production else (
                "store" if is_store else (
                    "purchase" if is_purchase else "staff"
                )
            )
        )
    )

    role_labels = {
        "factory_admin": "Factory Admin",
        "asst_admin": "Assistant System Administrator",
        "production": "Production Manager",
        "store": "Store Keeper",
        "purchase": "Purchase Manager",
        "staff": "General Staff / Auditor",
    }

    return {
        "user": user,
        "full_name": full_name,
        "roles": user_roles,
        "primary_role": primary_role,
        "primary_role_label": role_labels.get(primary_role, "Factory User"),
        "is_factory_admin": is_factory_admin,
        "is_asst_admin": is_asst_admin,
        "is_admin": is_factory_admin or is_asst_admin,
        "is_production": is_production,
        "is_store": is_store,
        "is_purchase": is_purchase,
        "is_staff": is_staff,
        "can_create_recipe": can_create_recipe,
        "can_read_recipe": can_read_recipe,
        "can_create_production_order": can_create_production_order,
        "can_read_production_order": can_read_production_order,
        "can_receive_grn": can_receive_grn,
        "can_read_grn": can_read_grn,
        "can_manage_roles": can_manage_roles,
        "can_adjust_stock": can_adjust_stock,
        "can_read_item": can_read_item,
        "can_read_batch": can_read_batch,
        "can_read_supplier": can_read_supplier,
        "can_create_supplier": can_create_supplier,
        "can_view_audit": can_view_audit,
    }


@frappe.whitelist()
def get_item_stock_info(item_code):
    """Return usable stock, batch count, low-stock status for an ingredient."""
    from productix_recipe.recipe_management.utils.fefo_utils import get_usable_stock

    today_date = getdate(today())
    usable = get_usable_stock(item_code)

    item = frappe.get_cached_doc("Item", item_code)
    min_qty = flt(item.min_stock_qty)

    active_batches = frappe.db.count("Batch", {"item": item_code, "disabled": 0})
    expiring = frappe.db.count("Batch", {
        "item": item_code, "disabled": 0,
        "expiry_date": ["between", [str(today_date), str(add_days(today_date, 7))]]
    })

    return {
        "item_code": item_code,
        "item_name": item.item_name,
        "usable_stock": usable,
        "min_stock_qty": min_qty,
        "is_low_stock": usable < min_qty if min_qty > 0 else False,
        "active_batches": active_batches,
        "expiring_batches": expiring,
        "unit": item.stock_uom,
    }


@frappe.whitelist()
def get_dashboard_kpis(role_override=None):
    """Return all KPI data tailored for the Recipe Management custom dashboard and role views."""
    today_date = getdate(today())
    alert_window = str(add_days(today_date, 7))

    role_ctx = get_user_role_context()
    active_role = role_override or role_ctx.get("primary_role", "admin")

    total_recipes = frappe.db.count("Recipe")
    total_orders = frappe.db.count("Production Order")
    today_orders = frappe.db.count("Production Order", {
        "production_date": ["like", f"{today()}%"]
    })
    total_items = frappe.db.count("Item", {"disabled": 0})
    total_batches = frappe.db.count("Batch", {"disabled": 0})
    total_suppliers = frappe.db.count("Supplier", {"disabled": 0})
    total_grns = frappe.db.count("Purchase Receipt", {"docstatus": 1})
    total_users = frappe.db.count("User", {"enabled": 1, "name": ["not in", ["Guest", "Administrator"]]})

    # Calculate stock value and low stock items
    items = frappe.get_all("Item", filters={"disabled": 0},
        fields=["name", "min_stock_qty", "valuation_rate", "stock_uom", "item_name"])

    low_stock = 0
    low_stock_items = []
    total_stock_value = 0.0

    for item in items:
        from productix_recipe.recipe_management.utils.fefo_utils import get_usable_stock
        usable = get_usable_stock(item.name)
        val_rate = flt(item.valuation_rate) or 1.0
        total_stock_value += usable * val_rate
        min_qty = flt(item.min_stock_qty) or 0
        if min_qty > 0 and usable < min_qty:
            low_stock += 1
            low_stock_items.append({
                "item_code": item.name,
                "item_name": item.item_name,
                "current": usable,
                "min": min_qty,
                "shortage": min_qty - usable,
                "unit": item.stock_uom,
            })

    # Expiry alerts
    expiry_alerts = frappe.db.count("Batch", {
        "disabled": 0,
        "expiry_date": ["between", [str(today_date), alert_window]]
    })
    expired_count = frappe.db.count("Batch", {
        "disabled": 0,
        "expiry_date": ["<", str(today_date)]
    })

    # Production orders breakdown
    order_status_counts = {}
    statuses = ["Pending", "In Progress", "Completed", "Cancelled"]
    for s in statuses:
        order_status_counts[s] = frappe.db.count("Production Order", {"status": s})

    # Recent production orders (for dashboard table)
    recent_orders = []
    try:
        recent_orders = frappe.get_all(
            "Production Order",
            fields=["name", "order_number", "recipe_name", "quantity", "status", "production_date", "created_by_name", "owner"],
            order_by="creation desc",
            limit=8,
        )
    except Exception as e:
        frappe.logger().warning(f"Could not fetch recent orders: {e}")

    # Recipe category breakdown (for category chart)
    recipe_categories = {}
    try:
        cats = frappe.db.sql("""
            SELECT IFNULL(category, 'General') as cat, COUNT(*) as cnt
            FROM `tabRecipe`
            GROUP BY category
        """, as_dict=True)
        for c in cats:
            recipe_categories[c.cat] = int(c.cnt)
    except Exception as e:
        frappe.logger().warning(f"Could not fetch recipe categories: {e}")

    # Recent activity history
    recent_activity = get_activity_history(limit=8)

    return {
        "role_context": role_ctx,
        "active_role": active_role,
        "total_recipes": total_recipes,
        "total_orders": total_orders,
        "today_orders": today_orders,
        "total_items": total_items,
        "total_batches": total_batches,
        "total_suppliers": total_suppliers,
        "total_grns": total_grns,
        "total_users": total_users,
        "low_stock_count": low_stock,
        "low_stock_items": low_stock_items[:8],
        "expiry_alert_count": expiry_alerts + expired_count,
        "expired_count": expired_count,
        "expiring_soon_count": expiry_alerts,
        "total_stock_value": round(total_stock_value, 2),
        "order_status_counts": order_status_counts,
        "recipe_categories": recipe_categories,
        "recent_orders": recent_orders,
        "recent_activity": recent_activity,
    }


@frappe.whitelist()
def get_activity_history(limit=20):
    """
    Aggregate live activity logs showing what user performed which action
    across Purchase Receipts, Production Orders, Recipes, and System Logs.
    """
    activities = []

    # 1. From AI Agent Log / Audit Log
    logs = frappe.get_all("AI Agent Log",
        fields=["name", "action_type", "status", "details", "items_affected", "log_timestamp"],
        order_by="log_timestamp desc",
        limit=limit
    )
    for l in logs:
        activities.append({
            "type": l.action_type or "Audit",
            "title": l.action_type or "System Action",
            "status": l.status or "Info",
            "details": l.details or "",
            "timestamp": str(l.log_timestamp or ""),
            "doc_name": l.name,
            "link": f"/app/ai-agent-log/{l.name}",
        })

    # 2. From recent Purchase Receipts
    grns = frappe.get_all("Purchase Receipt",
        fields=["name", "supplier", "posting_date", "creation", "owner", "received_by_name", "received_by_user", "grand_total"],
        order_by="creation desc",
        limit=limit
    )
    for g in grns:
        user_display = g.received_by_name or frappe.utils.get_fullname(g.owner) or g.owner
        activities.append({
            "type": "Purchase Receipt",
            "title": f"GRN #{g.name}",
            "status": "Success",
            "details": f"Goods received from '{g.supplier}' by {user_display} (${flt(g.grand_total):,.2f}).",
            "timestamp": str(g.creation or g.posting_date),
            "doc_name": g.name,
            "link": f"/app/purchase-receipt/{g.name}",
        })

    # 3. From recent Production Orders
    pos = frappe.get_all("Production Order",
        fields=["name", "order_number", "recipe_name", "quantity", "status", "creation", "owner", "created_by_name", "started_by_name", "completed_by_name", "total_cost"],
        order_by="creation desc",
        limit=limit
    )
    for p in pos:
        user_display = p.created_by_name or frappe.utils.get_fullname(p.owner) or p.owner
        handler = p.completed_by_name or p.started_by_name or user_display
        activities.append({
            "type": "Production Order",
            "title": f"Run {p.order_number or p.name}",
            "status": p.status,
            "details": f"Run for {p.quantity} unit(s) of '{p.recipe_name}' [{p.status}]. Handled by: {handler}.",
            "timestamp": str(p.creation),
            "doc_name": p.name,
            "link": f"/app/production-order/{p.name}",
        })

    # Sort combined activities by timestamp descending
    activities.sort(key=lambda x: str(x.get("timestamp") or ""), reverse=True)
    return activities[:int(limit)]




