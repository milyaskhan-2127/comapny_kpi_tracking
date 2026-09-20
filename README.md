# Productix ERP

**Recipe & Production Management System built on ERPNext/Frappe**

> Demo Version — Productix ERP v1.0.0

---

## Overview

Productix is a complete ERPNext-based ERP for recipe-driven production businesses (bakeries, commissary kitchens, food manufacturers). It is built as a proper Frappe custom app installed on top of ERPNext v15, following all ERPNext/Frappe conventions.

---

## Features

| Module | Features |
|---|---|
| **Recipe Management** | Recipe BOM, Recipe Extras, Cost calculation |
| **Production Orders** | Create, Start (FEFO stock deduction), Complete, Cancel |
| **Inventory** | Batch tracking, FEFO consumption, expiry per batch |
| **GRN / Purchasing** | Purchase Receipts with batch + expiry date per line |
| **Supplier Management** | Full supplier CRUD with traceability to batches |
| **Reports** | Recipe Costing, Inventory Status, Batch Expiry, Production, Purchasing, Waste, Consumption |
| **Alerts** | Daily low-stock email + 7-day expiry email via SMTP |
| **Subscription** | License key system, auto-renewal via payment webhook |
| **Instruction Room** | Team messaging with @mention notifications |
| **User Management** | ERPNext roles: Admin, Asst. Admin, Production Mgr, Store Keeper, Purchase Mgr, General |

---

## Quick Start (Docker)

### Prerequisites
- Docker Desktop installed and running
- Docker Compose v2+

### 1. Clone / Copy

```bash
cd D:/TechoHub/project/productix_erp
```

### 2. Configure environment

```bash
cp .env .env.local
# Edit .env with your SMTP credentials and passwords
```

### 3. Start containers

```bash
docker compose up -d
```

### 4. Initialize the site (run ONCE)

```bash
bash setup_site.sh
```

This will:
- Create the ERPNext site `productix.local`
- Install ERPNext
- Install the `productix` custom app
- Run migrations
- Build assets

### 5. Open the app

Navigate to: **http://localhost:8080**

Login:
- **Username:** `Administrator`
- **Password:** `Admin@123` (or as set in `.env`)

---

## Post-Setup Configuration

### Configure SMTP Email
1. Go to **Settings → Email Account**
2. Add your SMTP server (same as in `.env`)
3. Enable "Use for Outgoing"

### Create First License Key
1. Go to **Subscription Management → Productix License**
2. Click **New**
3. Set `valid_until` (e.g., 1 year from today)
4. Set `max_users` (default: 5)
5. Save — the `license_key` is auto-generated

### Set Up Roles for Users
1. Go to **Settings → User** → select user
2. Assign one of the Productix roles:
   - `Productix Admin`
   - `Productix Assistant Admin`
   - `Productix Production Manager`
   - `Productix Store Keeper`
   - `Productix Purchase Manager`
   - `Productix General User`

### Configure Low-Stock Alert Emails
1. Go to **Stock Settings**
2. Set **Email Footer Address** to the alert recipient email(s) (comma-separated)

### Enable Batch Tracking on Items
1. Go to **Item** → open each ingredient
2. Enable **Has Batch No**
3. Set **Minimum Stock Qty** (custom field) for low-stock alerts

---

## Architecture

```
productix_erp/
├── docker-compose.yml          # All services
├── mariadb.cnf                 # MariaDB tuning
├── setup_site.sh               # First-run site setup
├── deploy.sh                   # Update deployment
├── backup.sh                   # Backup script
└── apps/
    └── productix/              # Custom Frappe app
        └── productix/
            ├── hooks.py                    # App hooks
            ├── modules.txt                 # Module list
            ├── recipe_management/          # Core module
            │   ├── doctype/
            │   │   ├── recipe/
            │   │   ├── recipe_item/
            │   │   ├── recipe_extra/
            │   │   ├── production_order/
            │   │   ├── production_order_extra/
            │   │   └── consumption_log/
            │   ├── report/
            │   │   ├── recipe_costing/
            │   │   ├── inventory_status_report/
            │   │   ├── batch_expiry_report/
            │   │   ├── production_performance_report/
            │   │   ├── purchasing_report/
            │   │   ├── waste_and_expiry_report/
            │   │   ├── consumption_report/
            │   │   └── production_ingredient_sheet/
            │   └── utils/
            │       ├── fefo_utils.py       # FEFO stock consumption
            │       ├── grn_utils.py        # GRN hooks
            │       └── production_utils.py # Production hooks
            ├── subscription_management/    # License system
            │   ├── doctype/
            │   │   ├── productix_license/
            │   │   └── productix_tenant/
            │   └── utils/tenant_utils.py
            ├── communication/              # Instruction Room
            │   └── doctype/
            │       ├── instruction_message/
            │       └── message_notification/
            ├── alerts/                     # Scheduled alerts
            │   ├── doctype/ai_agent_log/
            │   └── tasks.py               # Daily email jobs
            ├── api/
            │   ├── subscription.py        # Webhook endpoint
            │   └── inventory.py           # Stock APIs
            ├── utils/
            │   ├── boot.py               # Session boot data
            │   └── helpers.py            # Jinja helpers
            ├── fixtures/
            │   ├── roles.json            # Role definitions
            │   └── custom_fields.json    # Custom fields
            └── public/
                ├── css/productix.css     # Global styles
                └── js/productix.js       # Global JS
```

---

## ERPNext Native → Productix Mapping

| Original System | ERPNext Native | Productix Custom |
|---|---|---|
| Ingredient | Item (with Has Batch No) | min_stock_qty custom field |
| Supplier | Supplier | products_supplied, supplier_status custom fields |
| GRN | Purchase Receipt | expiry_date, certificate per item line |
| Inventory Batch | Batch | supplier, certificate_url custom fields |
| Inventory Transaction | Stock Ledger Entry | Native |
| Recipe (BOM) | — | Recipe DocType |
| Production Order | — | Production Order DocType |
| FEFO Logic | — | fefo_utils.py |
| User/Auth | ERPNext User | Native |
| Roles/Permissions | ERPNext Role | 6 Productix roles |
| Email Alerts | ERPNext Email | alerts/tasks.py scheduled jobs |
| Subscription | — | Productix License DocType |
| Instruction Room | — | Instruction Message DocType |

---

## Deployment Workflow

### Development → Production

```bash
# 1. Start fresh
docker compose up -d
bash setup_site.sh

# 2. Make code changes in apps/productix/
# 3. Deploy changes
bash deploy.sh

# 4. Backup
bash backup.sh
```

### Database Migrations
All schema changes are handled by Frappe's migration system:
```bash
bench --site productix.local migrate
```

---

## Payment Webhook Integration

Endpoint: `POST /api/method/productix.api.subscription.process_renewal_webhook`

The webhook endpoint:
1. Validates HMAC-SHA256 signature
2. Checks payment status == succeeded/paid
3. Finds the license by `metadata.license_key`
4. Checks idempotency (webhook_id deduplication)
5. Renews the license by +12 months
6. Logs the event

Configure `payment_webhook_secret` in `common_site_config.json`.

---

## Scheduled Jobs

| Job | Schedule | Purpose |
|---|---|---|
| `run_daily_inventory_scan` | Daily | Low-stock + expiry email alerts |
| `mark_expired_batches` | Daily | Auto-disable expired Batch records |

---

## Role Permissions Summary

| Action | Admin | Asst.Admin | Prod.Mgr | Store Keeper | Purch.Mgr | General |
|---|---|---|---|---|---|---|
| Recipes | R/W/D | R/W/D | R/W | — | — | R |
| Production Orders | R/W/D | R/W/D | R/W | R | — | R |
| Purchase Receipt (GRN) | R/W/D | R/W/D | — | R/W | R/W | R |
| Items (Ingredients) | R/W/D | R/W/D | R | R | R/W | R |
| Suppliers | R/W/D | R/W/D | R | R | R/W | R |
| Batches | R/W/D | R/W/D | — | R/W | — | R |
| Reports | All | All | Prod | Inv | Purch | — |
| User Mgmt | Y | Y | — | — | — | — |
| Subscription/License | Y | Y | — | — | — | — |
| Instruction Room | Y | Y | Y | Y | Y | Y |

---

## License

MIT © TechoHub
