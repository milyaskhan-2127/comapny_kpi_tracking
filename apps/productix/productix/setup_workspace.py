#!/usr/bin/env python3
"""
Productix ERP — Setup Recipe Management Workspace & Dashboard.
Creates Number Cards, Dashboard Charts, and full Workspace layout with Role & Staff management.
"""
import json
import frappe


def run():
    frappe.set_user("Administrator")
    print("Setting up Recipe Management Workspace & Dashboard...")

    _setup_custom_docperms()
    _create_number_cards()
    _create_dashboard_charts()
    _create_workspace()
    _hide_builtin_workspaces()
    _setup_page_roles()

    frappe.db.commit()
    frappe.clear_cache()
    print("✅ Recipe Management Workspace & Dashboard configured successfully!")


def _hide_builtin_workspaces():
    """
    Ensure all built-in ERPNext and custom workspaces are public and visible (public=1, is_hidden=0),
    and attach all standard roles to tabHas Role so every workspace displays cleanly in the sidebar.
    """
    workspaces = frappe.get_all("Workspace", fields=["name", "module", "public", "is_hidden"])

    for ws in workspaces:
        if ws.name == "Recipe Management":
            frappe.db.set_value("Workspace", ws.name, {
                "is_hidden": 0,
                "public": 1,
                "sequence_id": 0.1,
            }, update_modified=False)
        else:
            frappe.db.set_value("Workspace", ws.name, {
                "is_hidden": 0,
                "public": 1,
            }, update_modified=False)

    # Attach core roles to all Workspaces in tabHas Role
    try:
        frappe.db.sql("""
            INSERT IGNORE INTO `tabHas Role` (name, creation, modified, modified_by, owner, docstatus, idx, role, parent, parentfield, parenttype)
            SELECT
                SUBSTRING(MD5(CONCAT(w.name, r.name)), 1, 10),
                NOW(), NOW(), 'Administrator', 'Administrator', 0, 1,
                r.name, w.name, 'roles', 'Workspace'
            FROM `tabWorkspace` w
            CROSS JOIN (
                SELECT 'Administrator' AS name UNION SELECT 'System Manager' UNION SELECT 'All' UNION SELECT 'Desk User' UNION SELECT 'Factory Admin' UNION SELECT 'Production Manager' UNION SELECT 'Store Keeper' UNION SELECT 'Purchase Manager'
            ) r
            WHERE NOT EXISTS (
                SELECT 1 FROM `tabHas Role` hr WHERE hr.parent = w.name AND hr.role = r.name
            )
        """)
    except Exception as e:
        print(f"  Notice attaching workspace roles: {e}")

    print("  ✓ Workspaces configured: All ERPNext built-in & custom workspaces enabled with roles.")


def _create_number_cards():
    cards = [
        {
            "name": "Total Recipes",
            "label": "Total Recipes",
            "document_type": "Recipe",
            "function": "Count",
            "filters_json": "[]",
            "color": "#e74c3c",
            "module": "Recipe Management",
        },
        {
            "name": "Production Orders Today",
            "label": "Orders Today",
            "document_type": "Production Order",
            "function": "Count",
            "filters_json": '[["Production Order","production_date","Timespan","today"]]',
            "color": "#27ae60",
            "module": "Recipe Management",
        },
        {
            "name": "Total Production Orders",
            "label": "Total Production Orders",
            "document_type": "Production Order",
            "function": "Count",
            "filters_json": "[]",
            "color": "#2980b9",
            "module": "Recipe Management",
        },
        {
            "name": "Total Active Items",
            "label": "Active Ingredients / Items",
            "document_type": "Item",
            "function": "Count",
            "filters_json": '[["Item","disabled","=",0]]',
            "color": "#f39c12",
            "module": "Recipe Management",
        },
        {
            "name": "Active Suppliers",
            "label": "Active Suppliers",
            "document_type": "Supplier",
            "function": "Count",
            "filters_json": '[["Supplier","disabled","=",0]]',
            "color": "#8e44ad",
            "module": "Recipe Management",
        },
        {
            "name": "Total Batches",
            "label": "Total Batches",
            "document_type": "Batch",
            "function": "Count",
            "filters_json": '[["Batch","disabled","=",0]]',
            "color": "#16a085",
            "module": "Recipe Management",
        },
    ]

    for c in cards:
        if frappe.db.exists("Number Card", c["name"]):
            doc = frappe.get_doc("Number Card", c["name"])
            doc.update(c)
            doc.save(ignore_permissions=True)
        else:
            doc = frappe.get_doc({"doctype": "Number Card", **c})
            doc.insert(ignore_permissions=True)
    print("  ✓ Number Cards created/updated.")


def _create_dashboard_charts():
    charts = [
        {
            "name": "Production Orders by Status",
            "chart_name": "Production Orders by Status",
            "chart_type": "Group By",
            "document_type": "Production Order",
            "group_by_based_on": "status",
            "group_by_type": "Count",
            "filters_json": "[]",
            "type": "Donut",
            "color": "#27ae60",
            "module": "Recipe Management",
        },
        {
            "name": "Recipes by Category",
            "chart_name": "Recipes by Category",
            "chart_type": "Group By",
            "document_type": "Recipe",
            "group_by_based_on": "category",
            "group_by_type": "Count",
            "filters_json": "[]",
            "type": "Bar",
            "color": "#e74c3c",
            "module": "Recipe Management",
        },
    ]

    for ch in charts:
        if frappe.db.exists("Dashboard Chart", ch["name"]):
            doc = frappe.get_doc("Dashboard Chart", ch["name"])
            doc.update(ch)
            doc.save(ignore_permissions=True)
        else:
            doc = frappe.get_doc({"doctype": "Dashboard Chart", **ch})
            doc.insert(ignore_permissions=True)
    print("  ✓ Dashboard Charts created/updated.")


def _create_workspace():
    if frappe.db.exists("Workspace", "Productix"):
        frappe.delete_doc("Workspace", "Productix", force=True, ignore_permissions=True)

    workspace_name = "Recipe Management"

    content = [
        # Shortcuts Section Header
        {
            "id": "hdr_shortcuts",
            "type": "header",
            "data": {"text": '<span class="h4"><b>Quick Actions &amp; Operations</b></span>', "col": 12},
        },
        # Shortcuts Grid
        {"id": "sc_dash", "type": "shortcut", "data": {"shortcut_name": "Visual Dashboard", "col": 3}},
        {"id": "sc_new_rec", "type": "shortcut", "data": {"shortcut_name": "New Recipe", "col": 3}},
        {"id": "sc_all_rec", "type": "shortcut", "data": {"shortcut_name": "Recipes", "col": 3}},
        {"id": "sc_new_po", "type": "shortcut", "data": {"shortcut_name": "New Production Order", "col": 3}},
        {"id": "sc_all_po", "type": "shortcut", "data": {"shortcut_name": "Production Orders", "col": 3}},
        {"id": "sc_items", "type": "shortcut", "data": {"shortcut_name": "Ingredients / Items", "col": 3}},
        {"id": "sc_stock_in", "type": "shortcut", "data": {"shortcut_name": "Stock In", "col": 3}},
        {"id": "sc_grn_hist", "type": "shortcut", "data": {"shortcut_name": "GRN History", "col": 3}},
        {"id": "sc_batches", "type": "shortcut", "data": {"shortcut_name": "Inventory Batches", "col": 3}},
        {"id": "sc_suppliers", "type": "shortcut", "data": {"shortcut_name": "Suppliers", "col": 3}},
        {"id": "sc_roles", "type": "shortcut", "data": {"shortcut_name": "Manage Roles", "col": 3}},
        {"id": "sc_users", "type": "shortcut", "data": {"shortcut_name": "Manage Users", "col": 3}},
        {"id": "sc_room", "type": "shortcut", "data": {"shortcut_name": "Instruction Room", "col": 3}},
        # Spacer
        {"id": "sp_cards", "type": "spacer", "data": {"col": 12}},
        # Masters & Reports Section Header
        {
            "id": "hdr_cards",
            "type": "header",
            "data": {"text": '<span class="h4"><b>Masters &amp; Reports</b></span>', "col": 12},
        },
        # Categorized Link Cards
        {"id": "cd_recipe_prod", "type": "card", "data": {"card_name": "Recipe & Production", "col": 4}},
        {"id": "cd_inventory", "type": "card", "data": {"card_name": "Inventory & Batches", "col": 4}},
        {"id": "cd_purchasing", "type": "card", "data": {"card_name": "Purchasing & Suppliers", "col": 4}},
        {"id": "cd_reports", "type": "card", "data": {"card_name": "Reports & Analytics", "col": 4}},
        {"id": "cd_roles_staff", "type": "card", "data": {"card_name": "Roles & Staff Management", "col": 4}},
        {"id": "cd_subscription", "type": "card", "data": {"card_name": "License & System Logs", "col": 4}},
    ]

    shortcuts = [
        {"label": "Visual Dashboard", "link_to": "recipe-dashboard", "type": "Page", "color": "#3b82f6"},
        {"label": "New Recipe", "link_to": "Recipe", "type": "DocType", "color": "#e74c3c", "doc_view": "New"},
        {"label": "Recipes", "link_to": "Recipe", "type": "DocType", "color": "#e74c3c", "doc_view": "List"},
        {"label": "New Production Order", "link_to": "Production Order", "type": "DocType", "color": "#27ae60", "doc_view": "New"},
        {"label": "Production Orders", "link_to": "Production Order", "type": "DocType", "color": "#27ae60", "doc_view": "List"},
        {"label": "Ingredients / Items", "link_to": "Item", "type": "DocType", "color": "#3498db", "doc_view": "List"},
        {"label": "Stock In", "link_to": "Purchase Receipt", "type": "DocType", "color": "#2980b9", "doc_view": "New"},
        {"label": "GRN History", "link_to": "Purchasing Report", "type": "Report", "color": "#2563eb"},
        {"label": "Inventory Batches", "link_to": "Batch", "type": "DocType", "color": "#f39c12", "doc_view": "List"},
        {"label": "Suppliers", "link_to": "Supplier", "type": "DocType", "color": "#8e44ad", "doc_view": "List"},
        {"label": "Staff Directory", "link_to": "User", "type": "DocType", "color": "#0ea5e9", "doc_view": "List"},
        {"label": "Instruction Room", "link_to": "Instruction Message", "type": "DocType", "color": "#16a085", "doc_view": "List"},
    ]

    links = [
        # Card: Recipe & Production
        {"label": "Recipe & Production", "type": "Card Break"},
        {"label": "Visual Dashboard", "link_to": "recipe-dashboard", "link_type": "Page", "type": "Link", "onboard": 1},
        {"label": "Recipe", "link_to": "Recipe", "link_type": "DocType", "type": "Link", "onboard": 1},
        {"label": "Production Order", "link_to": "Production Order", "link_type": "DocType", "type": "Link", "onboard": 1},
        {"label": "Recipe Extras", "link_to": "Recipe Extra", "link_type": "DocType", "type": "Link"},
        {"label": "Consumption Log", "link_to": "Consumption Log", "link_type": "DocType", "type": "Link"},

        # Card: Inventory & Batches
        {"label": "Inventory & Batches", "type": "Card Break"},
        {"label": "Ingredients (Item)", "link_to": "Item", "link_type": "DocType", "type": "Link", "onboard": 1},
        {"label": "Batches", "link_to": "Batch", "link_type": "DocType", "type": "Link", "onboard": 1},
        {"label": "Item Group", "link_to": "Item Group", "link_type": "DocType", "type": "Link"},
        {"label": "Unit of Measure (UOM)", "link_to": "UOM", "link_type": "DocType", "type": "Link"},

        # Card: Purchasing & Suppliers
        {"label": "Purchasing & Suppliers", "type": "Card Break"},
        {"label": "Stock In", "link_to": "Purchase Receipt", "link_type": "DocType", "type": "Link", "onboard": 1},
        {"label": "GRN History", "link_to": "Purchasing Report", "link_type": "Report", "is_query_report": 1, "type": "Link", "onboard": 1},
        {"label": "Suppliers", "link_to": "Supplier", "link_type": "DocType", "type": "Link", "onboard": 1},
        {"label": "Supplier Group", "link_to": "Supplier Group", "link_type": "DocType", "type": "Link"},

        # Card: Reports & Analytics
        {"label": "Reports & Analytics", "type": "Card Break"},
        {"label": "Recipe Costing", "link_to": "Recipe Costing", "link_type": "Report", "is_query_report": 1, "type": "Link"},
        {"label": "Inventory Status Report", "link_to": "Inventory Status Report", "link_type": "Report", "is_query_report": 1, "type": "Link"},
        {"label": "Batch Expiry Report", "link_to": "Batch Expiry Report", "link_type": "Report", "is_query_report": 1, "type": "Link"},
        {"label": "Production Performance", "link_to": "Production Performance Report", "link_type": "Report", "is_query_report": 1, "type": "Link"},
        {"label": "Production Ingredient Sheet", "link_to": "Production Ingredient Sheet", "link_type": "Report", "is_query_report": 1, "type": "Link"},
        {"label": "Purchasing Report", "link_to": "Purchasing Report", "link_type": "Report", "is_query_report": 1, "type": "Link"},
        {"label": "Consumption Report", "link_to": "Consumption Report", "link_type": "Report", "is_query_report": 1, "type": "Link"},
        {"label": "Waste and Expiry Report", "link_to": "Waste and Expiry Report", "link_type": "Report", "is_query_report": 1, "type": "Link"},
        {"label": "Financial Report", "link_to": "Financial Report", "link_type": "Report", "is_query_report": 1, "type": "Link"},
        {"label": "Stock Movement Report", "link_to": "Stock Movement Report", "link_type": "Report", "is_query_report": 1, "type": "Link"},

        # Card: Roles & Staff Management
        {"label": "Roles & Staff Management", "type": "Card Break"},
        {"label": "Manage Roles", "link_to": "Role", "link_type": "DocType", "type": "Link", "onboard": 1},
        {"label": "Staff Directory (Users)", "link_to": "User", "link_type": "DocType", "type": "Link", "onboard": 1},
        {"label": "Role Permission Manager", "link_to": "permission-manager", "link_type": "Page", "type": "Link"},
        {"label": "Instruction Room", "link_to": "Instruction Message", "link_type": "DocType", "type": "Link"},

        # Card: License & System Logs
        {"label": "License & System Logs", "type": "Card Break"},
        {"label": "Productix License", "link_to": "Productix License", "link_type": "DocType", "type": "Link"},
        {"label": "AI Agent & Scan Logs", "link_to": "AI Agent Log", "link_type": "DocType", "type": "Link"},
    ]

    roles = [
        {"role": "Factory Admin"},
        {"role": "Assistant System Administrator"},
        {"role": "Production Manager"},
        {"role": "Store Keeper"},
        {"role": "Purchase Manager"},
        {"role": "General Staff"},
        {"role": "System Manager"},
        {"role": "Administrator"},
        {"role": "All"},
        {"role": "Desk User"},
        {"role": "Stock User"},
        {"role": "Stock Manager"},
        {"role": "Item Manager"},
        {"role": "Manufacturing User"},
        {"role": "Manufacturing Manager"},
        {"role": "Purchase User"},
    ]

    charts_child = [
        {"chart_name": "Production Orders by Status"},
        {"chart_name": "Recipes by Category"},
    ]

    num_cards_child = []

    ws_data = {
        "doctype": "Workspace",
        "name": workspace_name,
        "title": "Recipe Management",
        "label": "Recipe Management",
        "icon": "box",
        "module": "Recipe Management",
        "public": 1,
        "is_hidden": 0,
        "sequence_id": 0.1,
        "content": json.dumps(content),
        "roles": roles,
        "shortcuts": shortcuts,
        "links": links,
        "charts": charts_child,
        "number_cards": num_cards_child,
    }

    if frappe.db.exists("Workspace", workspace_name):
        doc = frappe.get_doc("Workspace", workspace_name)
        doc.update(ws_data)
        doc.save(ignore_permissions=True)
    else:
        doc = frappe.get_doc(ws_data)
        doc.insert(ignore_permissions=True)

    print("  ✓ Workspace 'Recipe Management' created/updated.")


def _setup_page_roles():
    if not frappe.db.exists("Page", "recipe-dashboard"):
        return

    all_roles = [
        "Factory Admin",
        "Assistant System Administrator",
        "Production Manager",
        "Store Keeper",
        "Purchase Manager",
        "General Staff",
        "System Manager",
        "Administrator",
        "All",
        "Desk User",
        "Stock User",
        "Stock Manager",
        "Item Manager",
        "Manufacturing User",
        "Manufacturing Manager",
        "Purchase User",
    ]

    page_doc = frappe.get_doc("Page", "recipe-dashboard")
    existing_roles = {r.role for r in page_doc.roles}

    for r in all_roles:
        if r not in existing_roles and frappe.db.exists("Role", r):
            page_doc.append("roles", {"role": r})

    page_doc.save(ignore_permissions=True)
    print("  ✓ Page 'recipe-dashboard' roles configured.")


def _setup_custom_docperms():
    """
    Ensure all factory roles have dynamic Custom DocPerm records on standard & custom DocTypes
    so permissions and allowed modules work seamlessly for all users.
    """
    perms = [
        # (parent_doctype, role, read, write, create, submit, delete)
        ("Item", "Store Keeper", 1, 1, 1, 0, 0),
        ("Item", "Purchase Manager", 1, 0, 0, 0, 0),
        ("Item", "Production Manager", 1, 0, 0, 0, 0),
        ("Item", "General Staff", 1, 0, 0, 0, 0),
        ("Item", "Factory Admin", 1, 1, 1, 0, 1),
        ("Item", "Desk User", 1, 0, 0, 0, 0),
        ("Item", "All", 1, 0, 0, 0, 0),

        ("Batch", "Store Keeper", 1, 1, 1, 0, 0),
        ("Batch", "Purchase Manager", 1, 0, 0, 0, 0),
        ("Batch", "Production Manager", 1, 0, 0, 0, 0),
        ("Batch", "General Staff", 1, 0, 0, 0, 0),
        ("Batch", "Factory Admin", 1, 1, 1, 0, 1),
        ("Batch", "Desk User", 1, 0, 0, 0, 0),
        ("Batch", "All", 1, 0, 0, 0, 0),

        ("Purchase Receipt", "Store Keeper", 1, 1, 1, 1, 0),
        ("Purchase Receipt", "Purchase Manager", 1, 1, 1, 1, 0),
        ("Purchase Receipt", "Factory Admin", 1, 1, 1, 1, 1),

        ("Stock Entry", "Store Keeper", 1, 1, 1, 1, 0),
        ("Stock Entry", "Production Manager", 1, 1, 1, 1, 0),
        ("Stock Entry", "Factory Admin", 1, 1, 1, 1, 1),

        ("Supplier", "Purchase Manager", 1, 1, 1, 0, 0),
        ("Supplier", "Store Keeper", 1, 0, 0, 0, 0),
        ("Supplier", "Factory Admin", 1, 1, 1, 0, 1),

        # Recipe permissions for all factory & desk roles
        ("Recipe", "Factory Admin", 1, 1, 1, 0, 1),
        ("Recipe", "Assistant System Administrator", 1, 1, 1, 0, 1),
        ("Recipe", "Production Manager", 1, 1, 1, 0, 0),
        ("Recipe", "System Manager", 1, 1, 1, 0, 1),
        ("Recipe", "Productix Admin", 1, 1, 1, 0, 1),
        ("Recipe", "Productix Assistant Admin", 1, 1, 1, 0, 1),
        ("Recipe", "Productix Production Manager", 1, 1, 1, 0, 0),
        ("Recipe", "Store Keeper", 1, 0, 0, 0, 0),
        ("Recipe", "Purchase Manager", 1, 0, 0, 0, 0),
        ("Recipe", "General Staff", 1, 0, 0, 0, 0),
        ("Recipe", "Productix Store Keeper", 1, 0, 0, 0, 0),
        ("Recipe", "Productix Purchase Manager", 1, 0, 0, 0, 0),
        ("Recipe", "Productix General User", 1, 0, 0, 0, 0),
        ("Recipe", "Desk User", 1, 0, 0, 0, 0),
        ("Recipe", "All", 1, 0, 0, 0, 0),
        ("Recipe", "Stock User", 1, 0, 0, 0, 0),
        ("Recipe", "Stock Manager", 1, 0, 0, 0, 0),
        ("Recipe", "Item Manager", 1, 0, 0, 0, 0),
        ("Recipe", "Manufacturing User", 1, 0, 0, 0, 0),

        # Production Order permissions for all factory & desk roles
        ("Production Order", "Factory Admin", 1, 1, 1, 0, 1),
        ("Production Order", "Assistant System Administrator", 1, 1, 1, 0, 1),
        ("Production Order", "Production Manager", 1, 1, 1, 0, 0),
        ("Production Order", "System Manager", 1, 1, 1, 0, 1),
        ("Production Order", "Productix Admin", 1, 1, 1, 0, 1),
        ("Production Order", "Productix Assistant Admin", 1, 1, 1, 0, 1),
        ("Production Order", "Productix Production Manager", 1, 1, 1, 0, 0),
        ("Production Order", "Store Keeper", 1, 0, 0, 0, 0),
        ("Production Order", "Purchase Manager", 1, 0, 0, 0, 0),
        ("Production Order", "General Staff", 1, 0, 0, 0, 0),
        ("Production Order", "Productix Store Keeper", 1, 0, 0, 0, 0),
        ("Production Order", "Productix Purchase Manager", 1, 0, 0, 0, 0),
        ("Production Order", "Productix General User", 1, 0, 0, 0, 0),
        ("Production Order", "Desk User", 1, 0, 0, 0, 0),
        ("Production Order", "All", 1, 0, 0, 0, 0),
        ("Production Order", "Stock User", 1, 0, 0, 0, 0),
        ("Production Order", "Stock Manager", 1, 0, 0, 0, 0),
        ("Production Order", "Item Manager", 1, 0, 0, 0, 0),
        ("Production Order", "Manufacturing User", 1, 0, 0, 0, 0),

        # Instruction Message for all desk users
        ("Instruction Message", "Desk User", 1, 1, 1, 0, 0),
        ("Instruction Message", "All", 1, 1, 1, 0, 0),
    ]

    for dt, role, r, w, c, s, d in perms:
        if not frappe.db.exists("Role", role):
            continue
        if not frappe.db.exists("Custom DocPerm", {"parent": dt, "role": role}):
            doc = frappe.get_doc({
                "doctype": "Custom DocPerm",
                "parent": dt,
                "parenttype": "DocType",
                "parentfield": "permissions",
                "role": role,
                "read": r,
                "write": w,
                "create": c,
                "submit": s,
                "delete": d,
                "permlevel": 0,
            })
            doc.insert(ignore_permissions=True)

    print("  ✓ Custom DocPerms configured.")


