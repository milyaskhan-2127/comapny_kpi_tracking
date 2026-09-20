#!/usr/bin/env python3
"""
Productix ERP — Chemical Formulation & Manufacturing Data Seeder & Reset.
Wipes old database records and generates a massive, comprehensive Chemical Formulation dataset.

Usage:
    docker compose exec backend bash -c "
        cd /home/frappe/frappe-bench &&
        bench --site productix.local execute productix.setup_data.run
    "
"""
import frappe
from frappe.utils import today, add_days, now_datetime, nowdate, flt
from productix.setup_workspace import run as setup_workspace_run
from productix.utils.email_utils import setup_smtp_email_account


def run():
    frappe.set_user("Administrator")
    print("=" * 65)
    print("  PRODUCTIX ERP — COMPLETE CHEMICAL RE-SEED & SYSTEM RESET")
    print("=" * 65)

    print("\n[1/11] Wiping existing database transactions & demo data...")
    _clear_all_data()

    print("\n[2/11] Setting up Factory User Roles...")
    _create_roles()

    print("\n[3/11] Configuring Productix License...")
    _create_license()

    print("\n[4/11] Configuring SMTP Email Account (mail.techohub.net)...")
    setup_smtp_email_account()

    print("\n[5/11] Creating Chemical Item Groups & Categories...")
    _create_item_groups()

    print("\n[6/11] Configuring Units of Measure (UOMs)...")
    _create_uoms()

    print("\n[7/11] Creating Chemical Suppliers & Vendors...")
    _create_suppliers()

    print("\n[8/11] Creating Chemical Raw Materials...")
    _create_chemical_items()

    print("\n[9/11] Processing Goods Received Notes (GRNs) & Inventory Batches...")
    _create_grns_and_stock()

    print("\n[10/11] Creating Industrial Chemical Formulation Recipes & BOMs...")
    _create_chemical_recipes()

    print("\n[11/11] Creating Chemical Production Runs & Consumption Audit Logs...")
    _create_production_runs()

    print("\n[12/12] Building Workspace Dashboard Layout & Team Messages...")
    setup_workspace_run()
    _create_team_messages()

    frappe.db.commit()
    frappe.clear_cache()

    print("\n" + "=" * 65)
    print("  ✅ CHEMICAL RE-SEED COMPLETE — 100% DYNAMIC DATABASE READY")
    print("=" * 65)


def _clear_all_data():
    """Wipe all transactional tables, old recipes, orders, batches, items, and suppliers."""
    tables_to_clear = [
        "tabConsumption Log",
        "tabProduction Order Extra",
        "tabProduction Order",
        "tabRecipe Extra",
        "tabRecipe Item",
        "tabRecipe",
        "tabMessage Notification",
        "tabInstruction Message",
        "tabAI Agent Log",
        "tabStock Ledger Entry",
        "tabBatch",
        "tabPurchase Receipt Item",
        "tabPurchase Receipt",
        "tabStock Entry Detail",
        "tabStock Entry",
        "tabBin",
    ]

    for tbl in tables_to_clear:
        try:
            frappe.db.sql(f"DELETE FROM `{tbl}`")
        except Exception as e:
            print(f"  Notice clearing {tbl}: {e}")

    try:
        frappe.db.sql("DELETE FROM `tabItem` WHERE name LIKE 'CHEM-%' OR name LIKE 'ALL-PURPOSE%' OR name LIKE 'WHITE-SUGAR%' OR name LIKE 'FLOUR%' OR name LIKE 'SUGAR%' OR name LIKE 'BUTTER%' OR name LIKE 'EGGS%' OR name LIKE 'COCOA%' OR name LIKE 'VANILLA%' OR name LIKE 'BAKE%' OR name LIKE 'MILK%'")
        frappe.db.sql("DELETE FROM `tabSupplier` WHERE name IN ('Fresh Farms Ltd', 'Dairy Gold Supplies', 'Apex Petrochemicals & Solvents Corp', 'Sigma Reagents & Specialty Chemicals Ltd', 'BioPolymer Global Synthetics', 'Catalyst Dynamics & Noble Elements Inc', 'SurfaceActive Surfactants & Chem Group', 'Vibrant Pigments & Minerals International')")
    except Exception as e:
        print(f"  Notice deleting items/suppliers: {e}")

    frappe.db.commit()
    print("  ✓ Database cleared of all legacy records.")


def _create_roles():
    roles = [
        {"role_name": "Factory Admin", "desk_access": 1},
        {"role_name": "Assistant System Administrator", "desk_access": 1},
        {"role_name": "Production Manager", "desk_access": 1},
        {"role_name": "Store Keeper", "desk_access": 1},
        {"role_name": "Purchase Manager", "desk_access": 1},
        {"role_name": "General Staff", "desk_access": 1},
    ]
    for r in roles:
        if not frappe.db.exists("Role", r["role_name"]):
            frappe.get_doc({
                "doctype": "Role",
                "role_name": r["role_name"],
                "desk_access": r.get("desk_access", 1),
            }).insert(ignore_permissions=True)
    print("  ✓ 6 Factory Roles configured.")


def _create_license():
    if frappe.db.exists("Productix License", {"tenant_name": "Apex Chemical Industries"}):
        return
    from frappe.utils import add_months
    frappe.get_doc({
        "doctype": "Productix License",
        "tenant_name": "Apex Chemical Industries",
        "is_active": 1,
        "valid_until": add_months(today(), 12),
        "max_users": 100,
        "notes": "Enterprise Chemical Factory License — Apex Chemical Industries.",
    }).insert(ignore_permissions=True)
    print("  ✓ Factory License configured.")


def _create_item_groups():
    if not frappe.db.exists("Item Group", "All Item Groups"):
        frappe.get_doc({
            "doctype": "Item Group",
            "item_group_name": "All Item Groups",
            "is_group": 1,
            "parent_item_group": "",
        }).insert(ignore_permissions=True)

    chemical_groups = [
        "Acids & Bases",
        "Organic Solvents",
        "Polymers & Resins",
        "Catalysts & Initiators",
        "Surfactants & Emulsifiers",
        "Pigments & Dyes",
        "Specialty Additives",
        "Inorganic Salts",
    ]
    for g in chemical_groups:
        if not frappe.db.exists("Item Group", g):
            frappe.get_doc({
                "doctype": "Item Group",
                "item_group_name": g,
                "is_group": 0,
                "parent_item_group": "All Item Groups",
            }).insert(ignore_permissions=True)
    print("  ✓ Chemical Item Groups created.")


def _create_uoms():
    uoms = ["kg", "g", "litre", "ml", "drum", "ton", "pcs", "Unit", "Batch", "Portion"]
    for u in uoms:
        if not frappe.db.exists("UOM", u):
            frappe.get_doc({"doctype": "UOM", "uom_name": u}).insert(ignore_permissions=True)
    print("  ✓ Units of Measure ready.")


def _create_suppliers():
    if not frappe.db.exists("Supplier Group", "All Supplier Groups"):
        frappe.get_doc({
            "doctype": "Supplier Group",
            "supplier_group_name": "All Supplier Groups",
            "is_group": 1,
            "parent_supplier_group": "",
        }).insert(ignore_permissions=True)

    suppliers = [
        {"name": "Apex Petrochemicals & Solvents Corp", "products": "IPA, Ethanol, Acetone, Toluene, MEK", "status": "Active"},
        {"name": "Sigma Reagents & Specialty Chemicals Ltd", "products": "Sulfuric Acid, Hydrochloric Acid, Sodium Hydroxide, Citric Acid, DI Water", "status": "Active"},
        {"name": "BioPolymer Global Synthetics", "products": "Epoxy Resin EP-828, Polyurethane PU-100, PEG-400, Xanthan Gum", "status": "Active"},
        {"name": "Catalyst Dynamics & Noble Elements Inc", "products": "Platinum on Carbon 5%, Benzoyl Peroxide (BPO-75)", "status": "Active"},
        {"name": "SurfaceActive Surfactants & Chem Group", "products": "SLES-70, CAPB-30, Benzalkonium Chloride, Silicone Antifoam", "status": "Active"},
        {"name": "Vibrant Pigments & Minerals International", "products": "Titanium Dioxide Rutile R-902, Carbon Black Nano, Zinc Oxide", "status": "Active"},
    ]

    for s in suppliers:
        if not frappe.db.exists("Supplier", s["name"]):
            frappe.get_doc({
                "doctype": "Supplier",
                "supplier_name": s["name"],
                "supplier_type": "Company",
                "supplier_group": "All Supplier Groups",
                "products_supplied": s["products"],
                "supplier_status": s["status"],
            }).insert(ignore_permissions=True)
    print("  ✓ 6 Chemical Suppliers created.")


def _create_chemical_items():
    materials = [
        {"code": "CHEM-IPA-99", "name": "Isopropyl Alcohol (IPA) 99.8% Tech", "group": "Organic Solvents", "uom": "litre", "min_stock": 200, "rate": 3.20},
        {"code": "CHEM-ETHANOL-ABS", "name": "Ethanol Absolute 99.9% Denatured", "group": "Organic Solvents", "uom": "litre", "min_stock": 150, "rate": 2.85},
        {"code": "CHEM-ACETONE-PURE", "name": "Acetone Pure Grade 99.5%", "group": "Organic Solvents", "uom": "litre", "min_stock": 100, "rate": 4.10},
        {"code": "CHEM-TOLUENE-AR", "name": "Toluene Analytical Reagent 99.5%", "group": "Organic Solvents", "uom": "litre", "min_stock": 80, "rate": 5.40},
        {"code": "CHEM-MEK-SOLV", "name": "Methyl Ethyl Ketone (MEK)", "group": "Organic Solvents", "uom": "litre", "min_stock": 50, "rate": 6.20},

        {"code": "CHEM-SULFURIC-98", "name": "Sulfuric Acid 98% Industrial Grade", "group": "Acids & Bases", "uom": "kg", "min_stock": 100, "rate": 1.95},
        {"code": "CHEM-HYDROCHLOR-37", "name": "Hydrochloric Acid 37% Technical", "group": "Acids & Bases", "uom": "litre", "min_stock": 80, "rate": 2.40},
        {"code": "CHEM-NAOH-PELLETS", "name": "Sodium Hydroxide Pellets 99%", "group": "Acids & Bases", "uom": "kg", "min_stock": 120, "rate": 3.80},
        {"code": "CHEM-CITRIC-MONO", "name": "Citric Acid Monohydrate Fine", "group": "Acids & Bases", "uom": "kg", "min_stock": 50, "rate": 4.50},

        {"code": "CHEM-EPOXY-EP828", "name": "Epoxy Resin Prepolymer EP-828", "group": "Polymers & Resins", "uom": "kg", "min_stock": 250, "rate": 14.50},
        {"code": "CHEM-POLYURETH-PU100", "name": "Polyurethane Prepolymer PU-100", "group": "Polymers & Resins", "uom": "kg", "min_stock": 150, "rate": 18.20},
        {"code": "CHEM-PEG-400", "name": "Polyethylene Glycol 400 (PEG-400)", "group": "Polymers & Resins", "uom": "kg", "min_stock": 80, "rate": 8.90},

        {"code": "CHEM-PT-CARBON-5PCT", "name": "Platinum on Carbon 5% Catalyst", "group": "Catalysts & Initiators", "uom": "g", "min_stock": 100, "rate": 85.00},
        {"code": "CHEM-BPO-75", "name": "Benzoyl Peroxide 75% Initiator", "group": "Catalysts & Initiators", "uom": "kg", "min_stock": 25, "rate": 32.00},

        {"code": "CHEM-SLES-70", "name": "Sodium Lauryl Ether Sulfate 70%", "group": "Surfactants & Emulsifiers", "uom": "kg", "min_stock": 300, "rate": 5.10},
        {"code": "CHEM-CAPB-30", "name": "Cocamidopropyl Betaine 30% (CAPB)", "group": "Surfactants & Emulsifiers", "uom": "kg", "min_stock": 150, "rate": 6.40},
        {"code": "CHEM-BKC-50", "name": "Benzalkonium Chloride 50% (BKC)", "group": "Surfactants & Emulsifiers", "uom": "litre", "min_stock": 80, "rate": 11.50},
        {"code": "CHEM-SILICONE-AF", "name": "Silicone Antifoam Emulsion 30%", "group": "Specialty Additives", "uom": "litre", "min_stock": 30, "rate": 22.00},

        {"code": "CHEM-TIO2-R902", "name": "Titanium Dioxide Rutile R-902+", "group": "Pigments & Dyes", "uom": "kg", "min_stock": 500, "rate": 7.80},
        {"code": "CHEM-CARBON-BLK", "name": "Carbon Black Nano Pigment Paste", "group": "Pigments & Dyes", "uom": "kg", "min_stock": 100, "rate": 16.50},
        {"code": "CHEM-ZINC-OXIDE", "name": "Zinc Oxide Active Micro Powder", "group": "Specialty Additives", "uom": "kg", "min_stock": 80, "rate": 9.20},

        {"code": "CHEM-DI-WATER", "name": "Demineralized DI Water Purified", "group": "Specialty Additives", "uom": "litre", "min_stock": 1000, "rate": 0.25},
        {"code": "CHEM-NACL-ACS", "name": "Sodium Chloride Pure Chemical ACS", "group": "Inorganic Salts", "uom": "kg", "min_stock": 200, "rate": 0.85},
        {"code": "CHEM-XANTHAN-GUM", "name": "Xanthan Gum Polymer Thickener", "group": "Specialty Additives", "uom": "kg", "min_stock": 40, "rate": 28.00},
    ]

    for m in materials:
        if not frappe.db.exists("Item", m["code"]):
            doc = frappe.get_doc({
                "doctype": "Item",
                "item_code": m["code"],
                "item_name": m["name"],
                "item_group": m.get("group", "All Item Groups"),
                "stock_uom": m.get("uom", "kg"),
                "valuation_rate": m.get("rate", 1.0),
                "has_batch_no": 1,
                "has_expiry_date": 1,
                "min_stock_qty": m.get("min_stock", 0),
                "is_stock_item": 1,
            })
            doc.insert(ignore_permissions=True)
    print(f"  ✓ {len(materials)} Chemical Raw Materials created.")


def _get_company_and_warehouse():
    warehouse_types = ["Transit", "Stores", "Manufacturing"]
    for wt in warehouse_types:
        if not frappe.db.exists("Warehouse Type", wt):
            frappe.get_doc({"doctype": "Warehouse Type", "name": wt}).insert(ignore_permissions=True)

    company_name = frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company", {}, "name") or "Apex Chemical Industries"
    if not frappe.db.exists("Company", company_name):
        c = frappe.get_doc({
            "doctype": "Company",
            "company_name": company_name,
            "default_currency": "USD",
            "country": "United States",
        })
        c.insert(ignore_permissions=True)
        company_name = c.name

    if not frappe.db.exists("Fiscal Year", "2026"):
        fy = frappe.get_doc({
            "doctype": "Fiscal Year",
            "year": "2026",
            "year_start_date": "2026-01-01",
            "year_end_date": "2026-12-31",
            "companies": [{"company": company_name}],
        })
        fy.insert(ignore_permissions=True)
    elif not frappe.db.exists("Fiscal Year Company", {"parent": "2026", "company": company_name}):
        fy = frappe.get_doc("Fiscal Year", "2026")
        fy.append("companies", {"company": company_name})
        fy.save(ignore_permissions=True)

    abbr = frappe.db.get_value("Company", company_name, "abbr") or "ACI"
    stores = frappe.get_all("Warehouse", filters={"disabled": 0, "is_group": 0, "company": company_name}, limit=1, pluck="name")
    if stores:
        return company_name, stores[0]

    wh_doc = frappe.get_doc({
        "doctype": "Warehouse",
        "warehouse_name": "Stores",
        "company": company_name,
        "is_group": 0,
    })
    wh_doc.insert(ignore_permissions=True)
    return company_name, wh_doc.name


def _create_grns_and_stock():
    """Create real Purchase Receipts (GRN) and Stock Entries so that live inventory is populated."""
    company, warehouse = _get_company_and_warehouse()

    receipts_data = [
        {
            "supplier": "Apex Petrochemicals & Solvents Corp",
            "items": [
                {"item_code": "CHEM-IPA-99", "qty": 1200, "rate": 3.20, "batch": "BAT-IPA-2026-001", "exp_days": 180},
                {"item_code": "CHEM-ETHANOL-ABS", "qty": 800, "rate": 2.85, "batch": "BAT-ETH-2026-001", "exp_days": 240},
                {"item_code": "CHEM-ACETONE-PURE", "qty": 500, "rate": 4.10, "batch": "BAT-ACT-2026-001", "exp_days": 150},
                {"item_code": "CHEM-TOLUENE-AR", "qty": 350, "rate": 5.40, "batch": "BAT-TOL-2026-001", "exp_days": 200},
                {"item_code": "CHEM-MEK-SOLV", "qty": 250, "rate": 6.20, "batch": "BAT-MEK-2026-001", "exp_days": 120},
            ]
        },
        {
            "supplier": "Sigma Reagents & Specialty Chemicals Ltd",
            "items": [
                {"item_code": "CHEM-SULFURIC-98", "qty": 650, "rate": 1.95, "batch": "BAT-SULF-2026-001", "exp_days": 365},
                {"item_code": "CHEM-HYDROCHLOR-37", "qty": 400, "rate": 2.40, "batch": "BAT-HCL-2026-001", "exp_days": 300},
                {"item_code": "CHEM-NAOH-PELLETS", "qty": 900, "rate": 3.80, "batch": "BAT-NAOH-2026-001", "exp_days": 365},
                {"item_code": "CHEM-CITRIC-MONO", "qty": 300, "rate": 4.50, "batch": "BAT-CIT-2026-001", "exp_days": 180},
                {"item_code": "CHEM-DI-WATER", "qty": 8000, "rate": 0.25, "batch": "BAT-H2O-2026-001", "exp_days": 365},
                {"item_code": "CHEM-NACL-ACS", "qty": 1200, "rate": 0.85, "batch": "BAT-NACL-2026-001", "exp_days": 365},
            ]
        },
        {
            "supplier": "BioPolymer Global Synthetics",
            "items": [
                {"item_code": "CHEM-EPOXY-EP828", "qty": 1400, "rate": 14.50, "batch": "BAT-EPX-2026-001", "exp_days": 90},
                {"item_code": "CHEM-POLYURETH-PU100", "qty": 750, "rate": 18.20, "batch": "BAT-PU-2026-001", "exp_days": 60},
                {"item_code": "CHEM-PEG-400", "qty": 450, "rate": 8.90, "batch": "BAT-PEG-2026-001", "exp_days": 210},
                {"item_code": "CHEM-XANTHAN-GUM", "qty": 120, "rate": 28.00, "batch": "BAT-XAN-2026-001", "exp_days": 5},
            ]
        },
        {
            "supplier": "Catalyst Dynamics & Noble Elements Inc",
            "items": [
                {"item_code": "CHEM-PT-CARBON-5PCT", "qty": 500, "rate": 85.00, "batch": "BAT-PT-2026-001", "exp_days": 180},
                {"item_code": "CHEM-BPO-75", "qty": 120, "rate": 32.00, "batch": "BAT-BPO-2026-001", "exp_days": 4},
            ]
        },
        {
            "supplier": "SurfaceActive Surfactants & Chem Group",
            "items": [
                {"item_code": "CHEM-SLES-70", "qty": 1800, "rate": 5.10, "batch": "BAT-SLES-2026-001", "exp_days": 120},
                {"item_code": "CHEM-CAPB-30", "qty": 650, "rate": 6.40, "batch": "BAT-CAPB-2026-001", "exp_days": 90},
                {"item_code": "CHEM-BKC-50", "qty": 400, "rate": 11.50, "batch": "BAT-BKC-2026-001", "exp_days": 150},
                {"item_code": "CHEM-SILICONE-AF", "qty": 20, "rate": 22.00, "batch": "BAT-AF-2026-001", "exp_days": 45},
            ]
        },
        {
            "supplier": "Vibrant Pigments & Minerals International",
            "items": [
                {"item_code": "CHEM-TIO2-R902", "qty": 2500, "rate": 7.80, "batch": "BAT-TIO2-2026-001", "exp_days": 365},
                {"item_code": "CHEM-CARBON-BLK", "qty": 350, "rate": 16.50, "batch": "BAT-CB-2026-001", "exp_days": 60},
                {"item_code": "CHEM-ZINC-OXIDE", "qty": 400, "rate": 9.20, "batch": "BAT-ZNO-2026-001", "exp_days": 180},
            ]
        }
    ]

    for grn_data in receipts_data:
        supplier = grn_data["supplier"]

        # 1. Create Batches first
        for itm in grn_data["items"]:
            b_id = itm["batch"]
            exp_date = add_days(today(), itm["exp_days"])
            uom = frappe.db.get_value("Item", itm["item_code"], "stock_uom") or "kg"

            if not frappe.db.exists("Batch", b_id):
                b_doc = frappe.get_doc({
                    "doctype": "Batch",
                    "batch_id": b_id,
                    "item": itm["item_code"],
                    "item_name": frappe.db.get_value("Item", itm["item_code"], "item_name"),
                    "stock_uom": uom,
                    "batch_qty": itm["qty"],
                    "expiry_date": exp_date,
                    "supplier": supplier,
                    "disabled": 1 if itm["exp_days"] < 0 else 0,
                })
                b_doc.insert(ignore_permissions=True)

        # 2. Record Purchase Receipt (GRN) document
        pr_doc = frappe.new_doc("Purchase Receipt")
        pr_doc.supplier = supplier
        pr_doc.company = company
        pr_doc.posting_date = today()
        pr_doc.docstatus = 1  # Submitted
        pr_doc.received_by_user = "Administrator"
        pr_doc.received_by_name = "Alex Vance (Procurement)"
        for itm in grn_data["items"]:
            uom = frappe.db.get_value("Item", itm["item_code"], "stock_uom") or "kg"
            pr_doc.append("items", {
                "item_code": itm["item_code"],
                "item_name": frappe.db.get_value("Item", itm["item_code"], "item_name"),
                "qty": itm["qty"],
                "uom": uom,
                "stock_uom": uom,
                "rate": itm["rate"],
                "amount": itm["qty"] * itm["rate"],
                "warehouse": warehouse,
                "batch_no": itm["batch"],
                "expiry_date": add_days(today(), itm["exp_days"]),
                "conversion_factor": 1,
            })
        pr_doc.insert(ignore_permissions=True)

        # Log audit trail
        try:
            from productix.alerts.doctype.ai_agent_log.ai_agent_log import log_event
            items_str = ", ".join([f"{i['item_code']} ({i['qty']} {i.get('uom', 'kg')})" for i in grn_data["items"]])
            log_event(
                action_type="Purchase Receipt",
                status="Success",
                details=f"GRN #{pr_doc.name} received from '{supplier}' by Alex Vance (Procurement). Total Items: {len(grn_data['items'])}.",
                items_affected=items_str,
            )
        except Exception:
            pass

        # 3. Create Stock Ledger Entries linked to pr_doc.name
        for itm in grn_data["items"]:
            uom = frappe.db.get_value("Item", itm["item_code"], "stock_uom") or "kg"
            frappe.get_doc({
                "doctype": "Stock Ledger Entry",
                "item_code": itm["item_code"],
                "warehouse": warehouse,
                "posting_date": today(),
                "posting_time": "08:00:00",
                "voucher_type": "Purchase Receipt",
                "voucher_no": pr_doc.name,
                "actual_qty": itm["qty"],
                "qty_after_transaction": itm["qty"],
                "incoming_rate": itm["rate"],
                "valuation_rate": itm["rate"],
                "stock_value": itm["qty"] * itm["rate"],
                "stock_value_difference": itm["qty"] * itm["rate"],
                "batch_no": itm["batch"],
                "stock_uom": uom,
                "company": company,
                "is_cancelled": 0,
            }).insert(ignore_permissions=True)

    # Mark one batch as expired for waste & expiry report testing
    if frappe.db.exists("Batch", "BAT-CB-2026-001"):
        frappe.db.set_value("Batch", "BAT-CB-2026-001", {
            "expiry_date": add_days(today(), -10),
            "disabled": 1,
            "description": f"[AUTO-EXPIRED {today()}] Chemical lot past shelf life"
        })

    print("  ✓ 6 Purchase Receipts (GRN) submitted & Stock Ledger Entries created.")


def _create_chemical_recipes():
    recipes = [
        {
            "recipe_name": "Heavy-Duty Industrial Solvent Degreaser",
            "category": "Main Course",
            "serving_size": 100,
            "unit": "Litre",
            "description": "High-efficiency degreasing formulation for industrial machinery, engine blocks, and tooling.",
            "items": [
                {"ingredient": "CHEM-IPA-99", "quantity": 45.0, "unit": "litre", "unit_cost": 3.20, "amount": 144.00},
                {"ingredient": "CHEM-ACETONE-PURE", "quantity": 25.0, "unit": "litre", "unit_cost": 4.10, "amount": 102.50},
                {"ingredient": "CHEM-MEK-SOLV", "quantity": 15.0, "unit": "litre", "unit_cost": 6.20, "amount": 93.00},
                {"ingredient": "CHEM-SLES-70", "quantity": 10.0, "unit": "kg", "unit_cost": 5.10, "amount": 51.00},
                {"ingredient": "CHEM-SILICONE-AF", "quantity": 5.0, "unit": "litre", "unit_cost": 22.00, "amount": 110.00},
            ],
            "extras": [
                {"extra_name": "Corrosion Inhibitor Booster", "ingredient": "CHEM-ZINC-OXIDE", "quantity": 2.0, "unit": "kg", "extra_cost": 18.40},
            ],
            "bom_cost": 500.50,
            "cost_per_serving": 5.01,
        },
        {
            "recipe_name": "High-Performance Structural Epoxy Primer",
            "category": "Main Course",
            "serving_size": 50,
            "unit": "Kg",
            "description": "Two-component epoxy resin primer with exceptional corrosion resistance and substrate bonding.",
            "items": [
                {"ingredient": "CHEM-EPOXY-EP828", "quantity": 30.0, "unit": "kg", "unit_cost": 14.50, "amount": 435.00},
                {"ingredient": "CHEM-TIO2-R902", "quantity": 10.0, "unit": "kg", "unit_cost": 7.80, "amount": 78.00},
                {"ingredient": "CHEM-TOLUENE-AR", "quantity": 8.0, "unit": "litre", "unit_cost": 5.40, "amount": 43.20},
                {"ingredient": "CHEM-BPO-75", "quantity": 2.0, "unit": "kg", "unit_cost": 32.00, "amount": 64.00},
            ],
            "extras": [
                {"extra_name": "UV Stabilizer Package", "ingredient": "CHEM-ZINC-OXIDE", "quantity": 1.5, "unit": "kg", "extra_cost": 13.80},
            ],
            "bom_cost": 620.20,
            "cost_per_serving": 12.40,
        },
        {
            "recipe_name": "Broad-Spectrum Healthcare Disinfectant Solution",
            "category": "Beverages",
            "serving_size": 200,
            "unit": "Litre",
            "description": "Hospital-grade surface sanitizer formulated with quaternary ammonium compound and refined ethanol.",
            "items": [
                {"ingredient": "CHEM-ETHANOL-ABS", "quantity": 140.0, "unit": "litre", "unit_cost": 2.85, "amount": 399.00},
                {"ingredient": "CHEM-DI-WATER", "quantity": 50.0, "unit": "litre", "unit_cost": 0.25, "amount": 12.50},
                {"ingredient": "CHEM-BKC-50", "quantity": 8.0, "unit": "litre", "unit_cost": 11.50, "amount": 92.00},
                {"ingredient": "CHEM-PEG-400", "quantity": 2.0, "unit": "kg", "unit_cost": 8.90, "amount": 17.80},
            ],
            "extras": [
                {"extra_name": "Viscosity Modifier", "ingredient": "CHEM-XANTHAN-GUM", "quantity": 0.5, "unit": "kg", "extra_cost": 14.00},
            ],
            "bom_cost": 521.30,
            "cost_per_serving": 2.61,
        },
        {
            "recipe_name": "Polyurethane Gloss Industrial Enamel Topcoat",
            "category": "Main Course",
            "serving_size": 100,
            "unit": "Kg",
            "description": "Premium protective polyurethane coating for chemical tanks and marine equipment.",
            "items": [
                {"ingredient": "CHEM-POLYURETH-PU100", "quantity": 55.0, "unit": "kg", "unit_cost": 18.20, "amount": 1001.00},
                {"ingredient": "CHEM-TIO2-R902", "quantity": 25.0, "unit": "kg", "unit_cost": 7.80, "amount": 195.00},
                {"ingredient": "CHEM-ACETONE-PURE", "quantity": 15.0, "unit": "litre", "unit_cost": 4.10, "amount": 61.50},
                {"ingredient": "CHEM-SILICONE-AF", "quantity": 5.0, "unit": "litre", "unit_cost": 22.00, "amount": 110.00},
            ],
            "extras": [],
            "bom_cost": 1367.50,
            "cost_per_serving": 13.68,
        },
        {
            "recipe_name": "Acidic Descaler & Rust Neutralizer Conc.",
            "category": "Sides",
            "serving_size": 50,
            "unit": "Litre",
            "description": "Rapid scale and oxidation removal formulation for boiler pipelines and heat exchangers.",
            "items": [
                {"ingredient": "CHEM-HYDROCHLOR-37", "quantity": 25.0, "unit": "litre", "unit_cost": 2.40, "amount": 60.00},
                {"ingredient": "CHEM-CITRIC-MONO", "quantity": 10.0, "unit": "kg", "unit_cost": 4.50, "amount": 45.00},
                {"ingredient": "CHEM-DI-WATER", "quantity": 13.0, "unit": "litre", "unit_cost": 0.25, "amount": 3.25},
                {"ingredient": "CHEM-CAPB-30", "quantity": 2.0, "unit": "kg", "unit_cost": 6.40, "amount": 12.80},
            ],
            "extras": [],
            "bom_cost": 121.05,
            "cost_per_serving": 2.42,
        },
        {
            "recipe_name": "Premium Liquid Hand Soap Formulation",
            "category": "Desserts",
            "serving_size": 500,
            "unit": "Litre",
            "description": "Mild surfactant formulation with deep cleansing and skin-conditioning polymers.",
            "items": [
                {"ingredient": "CHEM-DI-WATER", "quantity": 380.0, "unit": "litre", "unit_cost": 0.25, "amount": 95.00},
                {"ingredient": "CHEM-SLES-70", "quantity": 70.0, "unit": "kg", "unit_cost": 5.10, "amount": 357.00},
                {"ingredient": "CHEM-CAPB-30", "quantity": 35.0, "unit": "kg", "unit_cost": 6.40, "amount": 224.00},
                {"ingredient": "CHEM-NACL-ACS", "quantity": 12.0, "unit": "kg", "unit_cost": 0.85, "amount": 10.20},
                {"ingredient": "CHEM-BKC-50", "quantity": 3.0, "unit": "litre", "unit_cost": 11.50, "amount": 34.50},
            ],
            "extras": [],
            "bom_cost": 720.70,
            "cost_per_serving": 1.44,
        },
        {
            "recipe_name": "Caustic CIP Alkaline Cleaner Solution",
            "category": "Sides",
            "serving_size": 250,
            "unit": "Litre",
            "description": "Heavy alkaline clean-in-place (CIP) solution for brewery and food processing tanks.",
            "items": [
                {"ingredient": "CHEM-DI-WATER", "quantity": 200.0, "unit": "litre", "unit_cost": 0.25, "amount": 50.00},
                {"ingredient": "CHEM-NAOH-PELLETS", "quantity": 40.0, "unit": "kg", "unit_cost": 3.80, "amount": 152.00},
                {"ingredient": "CHEM-SLES-70", "quantity": 10.0, "unit": "kg", "unit_cost": 5.10, "amount": 51.00},
            ],
            "extras": [],
            "bom_cost": 253.00,
            "cost_per_serving": 1.01,
        },
        {
            "recipe_name": "Laboratory pH 7.0 Calibration Buffer Standard",
            "category": "Snacks",
            "serving_size": 20,
            "unit": "Litre",
            "description": "Traceable analytical reagent calibration standard for high-precision laboratory pH meters.",
            "items": [
                {"ingredient": "CHEM-DI-WATER", "quantity": 18.0, "unit": "litre", "unit_cost": 0.25, "amount": 4.50},
                {"ingredient": "CHEM-NACL-ACS", "quantity": 1.5, "unit": "kg", "unit_cost": 0.85, "amount": 1.28},
                {"ingredient": "CHEM-CITRIC-MONO", "quantity": 0.5, "unit": "kg", "unit_cost": 4.50, "amount": 2.25},
            ],
            "extras": [],
            "bom_cost": 8.03,
            "cost_per_serving": 0.40,
        },
    ]

    for r in recipes:
        if not frappe.db.exists("Recipe", r["recipe_name"]):
            doc = frappe.get_doc({
                "doctype": "Recipe",
                "recipe_name": r["recipe_name"],
                "category": r["category"],
                "serving_size": r["serving_size"],
                "unit": r["unit"],
                "description": r["description"],
                "items": r["items"],
                "extras": r.get("extras", []),
                "bom_cost": r["bom_cost"],
                "cost_per_serving": r["cost_per_serving"],
            })
            doc.insert(ignore_permissions=True)
    print("  ✓ 8 Industrial Formulation Recipes & BOMs created.")


def _create_production_runs():
    orders = [
        {
            "order_number": "PO-2026-CH01",
            "recipe": "Heavy-Duty Industrial Solvent Degreaser",
            "quantity": 5,
            "status": "Completed",
            "production_date": now_datetime(),
            "created_by_user": "Administrator",
            "created_by_name": "Sarah Chen (Production Mgr)",
            "started_by_name": "Sarah Chen (Production Mgr)",
            "completed_by_name": "Elena Rostova (Floor Operator)",
            "base_cost": 2502.50,
            "total_cost": 2502.50,
            "notes": "500L Batch fulfilled for Heavy Machinery Plant #4.",
        },
        {
            "order_number": "PO-2026-CH02",
            "recipe": "High-Performance Structural Epoxy Primer",
            "quantity": 8,
            "status": "Completed",
            "production_date": now_datetime(),
            "created_by_user": "Administrator",
            "created_by_name": "David Miller (Lead Chemist)",
            "started_by_name": "David Miller (Lead Chemist)",
            "completed_by_name": "David Miller (Lead Chemist)",
            "base_cost": 4961.60,
            "total_cost": 4961.60,
            "notes": "400kg Structural primer batch for Marine Shipbuilding customer.",
        },
        {
            "order_number": "PO-2026-CH03",
            "recipe": "Broad-Spectrum Healthcare Disinfectant Solution",
            "quantity": 10,
            "status": "In Progress",
            "production_date": now_datetime(),
            "created_by_user": "Administrator",
            "created_by_name": "Sarah Chen (Production Mgr)",
            "started_by_name": "Elena Rostova (Floor Operator)",
            "base_cost": 5213.00,
            "total_cost": 5213.00,
            "notes": "2,000L Sanitizer run currently undergoing homogenization in Tank 2.",
        },
        {
            "order_number": "PO-2026-CH04",
            "recipe": "Polyurethane Gloss Industrial Enamel Topcoat",
            "quantity": 4,
            "status": "In Progress",
            "production_date": now_datetime(),
            "created_by_user": "Administrator",
            "created_by_name": "David Miller (Lead Chemist)",
            "started_by_name": "David Miller (Lead Chemist)",
            "base_cost": 5470.00,
            "total_cost": 5470.00,
            "notes": "400kg High-gloss PU topcoat in polymerization reactor.",
        },
        {
            "order_number": "PO-2026-CH05",
            "recipe": "Premium Liquid Hand Soap Formulation",
            "quantity": 6,
            "status": "Pending",
            "production_date": now_datetime(),
            "created_by_user": "Administrator",
            "created_by_name": "Sarah Chen (Production Mgr)",
            "base_cost": 4324.20,
            "total_cost": 4324.20,
            "notes": "3,000L Liquid soap production scheduled for night shift.",
        },
        {
            "order_number": "PO-2026-CH06",
            "recipe": "Acidic Descaler & Rust Neutralizer Conc.",
            "quantity": 12,
            "status": "Pending",
            "production_date": now_datetime(),
            "created_by_user": "Administrator",
            "created_by_name": "Sarah Chen (Production Mgr)",
            "base_cost": 1452.60,
            "total_cost": 1452.60,
            "notes": "600L Boiler pipeline cleaning acid batch.",
        },
        {
            "order_number": "PO-2026-CH07",
            "recipe": "Caustic CIP Alkaline Cleaner Solution",
            "quantity": 8,
            "status": "Pending",
            "production_date": now_datetime(),
            "created_by_user": "Administrator",
            "created_by_name": "David Miller (Lead Chemist)",
            "base_cost": 2024.00,
            "total_cost": 2024.00,
            "notes": "2,000L Brewery cleaning formulation queued.",
        },
        {
            "order_number": "PO-2026-CH08",
            "recipe": "Laboratory pH 7.0 Calibration Buffer Standard",
            "quantity": 25,
            "status": "Completed",
            "production_date": now_datetime(),
            "created_by_user": "Administrator",
            "created_by_name": "David Miller (Lead Chemist)",
            "started_by_name": "David Miller (Lead Chemist)",
            "completed_by_name": "David Miller (Lead Chemist)",
            "base_cost": 200.75,
            "total_cost": 200.75,
            "notes": "500L Analytical standard solution bottled in 1L flasks.",
        },
        {
            "order_number": "PO-2026-CH09",
            "recipe": "Heavy-Duty Industrial Solvent Degreaser",
            "quantity": 3,
            "status": "Cancelled",
            "production_date": now_datetime(),
            "created_by_user": "Administrator",
            "created_by_name": "Sarah Chen (Production Mgr)",
            "completed_by_name": "Cancelled by Factory Admin",
            "base_cost": 1501.50,
            "total_cost": 1501.50,
            "notes": "Cancelled by client before blending start.",
        },
        {
            "order_number": "PO-2026-CH10",
            "recipe": "High-Performance Structural Epoxy Primer",
            "quantity": 2,
            "status": "Pending",
            "production_date": now_datetime(),
            "created_by_user": "Administrator",
            "created_by_name": "David Miller (Lead Chemist)",
            "base_cost": 1240.40,
            "total_cost": 1240.40,
            "notes": "Sample test batch for aerospace qualification.",
        },
    ]

    for o in orders:
        if not frappe.db.exists("Production Order", o["order_number"]):
            doc = frappe.get_doc({
                "doctype": "Production Order",
                **o
            })
            doc.insert(ignore_permissions=True)

            if o["status"] in ("Completed", "In Progress"):
                _generate_consumption_logs(doc.name, o["order_number"], o["recipe"], o["quantity"])

            # Log audit trail
            try:
                from productix.alerts.doctype.ai_agent_log.ai_agent_log import log_event
                log_event(
                    action_type="Production Order",
                    status="Success" if o["status"] == "Completed" else ("Info" if o["status"] == "In Progress" else "Warning"),
                    details=f"Production Run {o['order_number']} for {o['quantity']}x '{o['recipe']}' [{o['status']}]. Handler: {o.get('completed_by_name') or o.get('started_by_name') or o.get('created_by_name')}.",
                    items_affected=o["recipe"],
                )
            except Exception:
                pass

    print("  ✓ 10 Chemical Production Runs across all operational stages created.")


def _generate_consumption_logs(po_name, order_number, recipe_name, qty):
    try:
        recipe = frappe.get_doc("Recipe", recipe_name)
        multiplier = flt(qty) or 1
        for item in recipe.items:
            consumed_qty = flt(item.quantity) * multiplier
            batch_name = frappe.db.get_value("Batch", {"item": item.ingredient}, "name")
            frappe.get_doc({
                "doctype": "Consumption Log",
                "production_order": po_name,
                "order_number": order_number,
                "ingredient": item.ingredient,
                "batch": batch_name,
                "planned_quantity": consumed_qty,
                "actual_quantity": consumed_qty,
                "difference": 0.0,
                "unit": item.unit,
            }).insert(ignore_permissions=True)
    except Exception as e:
        frappe.logger().warning(f"Could not generate logs for {po_name}: {e}")


def _create_team_messages():
    messages = [
        {
            "sender": "Administrator",
            "message": "⚠️ <b>Batch Expiry Alert:</b> Batch <code>BAT-BPO-2026-001</code> (Benzoyl Peroxide) expires in 4 days. Prioritizing for today's structural epoxy production runs.",
        },
        {
            "sender": "Administrator",
            "message": "📋 <b>Quality Assurance Notice:</b> Certificate of Analysis (COA) for <code>CHEM-EPOXY-EP828</code> is verified by QA laboratory. Released for production.",
        },
        {
            "sender": "Administrator",
            "message": "🚚 <b>Receiving Notice:</b> Incoming bulk shipment of Isopropyl Alcohol 99.8% (10,000L) scheduled for receiving at Gate 3 at 14:00.",
        },
    ]
    for m in messages:
        try:
            frappe.get_doc({
                "doctype": "Instruction Message",
                "sender": m["sender"],
                "message": m["message"],
            }).insert(ignore_permissions=True)
        except Exception:
            pass
    print("  ✓ Team Instruction Room announcements created.")


if __name__ == "__main__":
    run()
