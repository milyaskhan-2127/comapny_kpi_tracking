# Productix ERP

**Enterprise Manufacturing, Recipe Management & Company KPI Tracking System built on ERPNext / Frappe v15**

> **Version:** Productix ERP v2.0.0 (Enterprise Edition)  
> **Platform:** Frappe Framework v15 / ERPNext v15  
> **Architecture:** Docker-orchestrated multi-container stack (Frappe, ERPNext, MariaDB, Redis, Nginx)

---

## 📖 Executive Overview

**Productix ERP** is a comprehensive, production-grade enterprise resource planning platform engineered for manufacturing, food processing, commercial bakeries, commissary kitchens, and multi-department enterprises. 

Built natively as a Frappe application on top of **ERPNext v15**, Productix combines precision **Recipe & Batch Production Management** with an **Enterprise Company KPI Tracking & Machine Health Analytics Engine**, powered by customizable mathematical formula builders, real-time executive dashboards, CEO granular access control, and Groq AI-driven insights.

---

## 🚀 Key Modules & System Capabilities

### 1. 🍳 Recipe & Production Management
- **Recipe BOM & Extras**: Multi-layer recipe formulation with dynamic yield calculation, packaging materials, overheads, and real-time batch costing.
- **Production Orders**: End-to-end lifecycle management (Draft → Submitted → In Production → Completed / Cancelled).
- **Automated Stock Consumption**: Real-time inventory deduction using **FEFO** (First Expired, First Out) rules.
- **Batch & Expiry Traceability**: Strict batch number enforcement across all raw materials, WIP, and finished goods with expiration dates.
- **GRN & Purchasing**: Purchase Receipts with automated certificate attachments, supplier linkage, and batch creation per item line.
- **Production Reports**: Recipe Costing, Production Performance, Waste & Expiry Analysis, Inventory Status, and Daily Ingredient Sheets.

### 2. 📊 Company KPI Tracking & Analytics Suite
- **Department & Business Unit Hierarchy**: Organize KPIs across departments (Production, Quality, Sales, HR, Finance, Maintenance) and business units.
- **KPI Definitions & Metrics**: Support for Target Values, Tolerances, Polarity (Higher is Better / Lower is Better), and Measurement Units.
- **Visual Formula Builder & Mathematical Engine**: Calculate complex derived KPIs using dynamic formula variables, cross-period averages, and multi-metric aggregation.
- **Operational Data Tables**: Flexible tabular data entry for operational metrics, customer feedback, and department logs.
- **Multi-Frequency Data Entry**: Data entry workflows supporting Daily, Weekly, Monthly, Quarterly, and Yearly reporting periods.
- **Action Center & Automated Alerts**: Threshold breach detection triggering automated alerts, priority notifications, and corrective action workflows.
- **Intelligent Period Engine**: Automatic period boundary resolution, historical comparisons, quarter-over-quarter and year-over-year trending.

### 3. ⚙️ Machine Management & IoT Health Tracking
- **Machine Fleet Registry**: Catalog machinery, equipment models, serial numbers, locations, and operating capacities.
- **Machine Types & Parameters**: Define sensor parameters (Temperature, Pressure, RPM, Vibration, Voltage, Downtime, etc.) with safe operating ranges.
- **Machine Readings & Telemetry**: Record real-time manual and automated sensor readings against machines.
- **Machine-KPI Linkage**: Directly feed machine telemetry into production KPIs (OEE, Availability, Performance, Quality, Downtime Rate).
- **Machine Health Monitoring Dashboard**: Live visual dashboard displaying machine status (Operational, Warning, Critical, Offline), parameter gauges, and health logs.

### 4. 🔒 Granular CEO & Executive Access Control
- **Executive Security Layer**: Specialized access control for C-level executives, department heads, and managers.
- **Targeted Department Permissions**: Explicitly grant or restrict access to specific departments (`KPI CEO Department Access`).
- **Targeted KPI Permissions**: Granular white-listing and black-listing of sensitive KPIs (`KPI CEO KPI Access`).
- **Audit-Ready Security**: Role permission engines enforcing multi-tier data segregation and confidentiality.

### 5. 🤖 Groq AI Insights & Analytics Assistant
- **Automated Performance Insights**: Natural-language analysis of department and company KPIs using high-speed Groq AI LLM inference.
- **Root-Cause & Anomaly Detection**: Automatic detection of variance spikes, underperforming metrics, and production bottlenecks.
- **Smart Recommendations**: Context-aware recommendations for operational optimization, yield improvement, and waste reduction.

### 6. 📈 Executive Dashboards & Interactive Pages
- **Company Overview Dashboard**: High-level corporate health scorecard with target vs. actual dials, departmental health indexes, and trend charts.
- **Department Dashboard**: Deep-dive analytics per department with filtered KPI cards, variance bars, and historical tables.
- **KPI Action Center**: Centralized alert monitoring, escalation management, and task resolution board.
- **KPI Setup Wizard**: Step-by-step interactive onboarding wizard to configure departments, metrics, targets, and formulas without writing code.
- **Custom Native Doctype Integrations**: Script injections enhancing standard ERPNext forms with Productix KPI widgets.

### 7. 📑 Advanced Reporting Engine
- **Department Performance Report**: Multi-period comparative performance matrices by department.
- **KPI Performance & Variance Report**: Target vs. Actual variance analysis with percentage deviations and rag status.
- **KPI Trend & Forecast Report**: Historical trend analysis with predictive trajectory modeling.
- **KPI Data Quality & Completeness Report**: Audit logging of data entry timeliness, missing entries, and validation warnings.
- **KPI Alert & Action Report**: Historical log of all system alerts, response times, and resolution notes.

### 8. 💾 Automated Backup & Recovery System
- **Integrated Backup Manager**: Web-based database and site backup management built directly into the KPI Tracking workspace.
- **Instant On-Demand Backups**: One-click database and files backup generation.
- **Automated Retention & Cleanup**: Scheduled backups with configurable retention policies.
- **Download & Restore Support**: Secure access to download SQL database dumps and restore instances.

### 9. 💬 Instruction Room & Internal Communication
- **Team Instruction Messaging**: Real-time communication room for shift supervisors, operators, and managers.
- **Mention Notifications**: Direct `@user` tagging triggering in-app and email notifications.
- **Audit Trail**: Persistent history tied to shift handovers and operational instructions.

### 10. 🔑 Subscription & Multi-Tenant Management
- **Cryptographic License Management**: Software licensing mechanism with max-user caps, feature flags, and expiration dates.
- **Webhook Payment Integration**: Automated license renewal handler with HMAC-SHA256 signature verification for Stripe/payment gateways.
- **Tenant Isolation**: Multi-tenant support with data segregation controls.

---

## 🏗️ Repository Architecture

Productix was **modularized** from a monolithic app into four independently
installable Frappe apps (see `docs/architecture.md`):

```
productix_erp/
├── docker-compose.yml                  # Multi-container stack (mounts all 4 apps)
├── nginx.conf.template                 # Reverse-proxy template (site name injected)
├── mariadb.cnf                         # MariaDB InnoDB configuration
├── .env.example                        # Environment reference (secrets are env-only)
├── apps.json                           # bench app manifest (erpnext + 4 productix apps)
├── setup_site.sh / setup_site.ps1      # Site init (PRODUCTIX_APPS selects modules)
├── deploy.sh / deploy.ps1              # Deployment & migration runner
├── backup.sh                           # Standalone database backup script
├── scripts/                            # Static validators + migration health checks
│   ├── validate_dependencies.py        #   cross-app import/API hygiene (CI gate)
│   ├── validate_modules.py             #   registry & module-ownership invariants
│   └── migration_check.py              #   pre/post migration health report
├── tests/                              # Acceptance plan + pytest smoke tests
├── docs/                               # architecture / module-dev / deployment /
│                                       # on-premise / migration / versioning /
│                                       # rollback / lifecycle / future-module /
│                                       # ci-matrix
│
└── apps/
    ├── productix_core/                 # [PLATFORM] Productix Settings, module
    │   │                               #   registry + entitlement gate, licensing/
    │   │                               #   tenants, shared audit log + email utils,
    │   │                               #   boot session (license + unread + modules)
    │   └── productix_core/
    │       ├── productix_core/doctype/                     # module folder ("Productix Core")
    │       │   ├── productix_settings/                     #   entitlement UI
    │       │   ├── productix_module_entitlement/           #   entitlement child table
    │       │   └── ai_agent_log/                           #   shared audit log
    │       ├── modules/registry.py + entitlement.py         # module contract
    │       ├── subscription_management/                     # licensing & tenants
    │       ├── migrations/productix/repoint_module_defs     # ownership patch
    │       └── public/js/productix_core.js                  # is_module_enabled()
    │
    ├── productix_recipe/               # [MODULE Recipe Management]
    │   └── productix_recipe/
    │       ├── recipe_management/      # recipes, production orders, FEFO, GRN
    │       ├── api/inventory.py        # stock/batch APIs + trigger_manual_scan
    │       ├── tasks.py                # scheduled scans (require_module-guarded)
    │       ├── setup_data.py           # guarded demo seeding
    │       ├── fixtures/               # custom fields, roles, reports, ...
    │       └── public/js/              # list-view enhancements + doctype scripts
    │
    ├── productix_kpi/                  # [MODULE KPI Tracking]
    │   └── productix_kpi/
    │       ├── kpi_tracking/           # KPI definitions, formulas, data entry,
    │       │                           #   dashboards, machine health, CEO access
    │       ├── api/backup.py           # backup/restore manager backend
    │       ├── kpi_tracking/page/backups/  # backup manager page
    │       ├── fixtures/               # KPI roles, workspace, reports
    │       └── public/js/              # route guards + KPI user scripts
    │
    ├── productix_instruction/          # [MODULE Instruction Room]
    │   └── productix_instruction/
    │       └── instruction_room/       # Instruction Message + Message Notification
    │
    └── productix/                      # LEGACY monolithic app (migration baseline
                                        #   only — retired after migration)
```

---

## 📚 Documentation

| Document | Purpose |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | Modular app boundary design, module registry & entitlement flow |
| [`docs/ownership-matrix.md`](docs/ownership-matrix.md) | Complete legacy→app DocType/API/hook/scheduled-job ownership matrix |
| [`docs/module-development.md`](docs/module-development.md) | How to build a new Productix module app |
| [`docs/deployment.md`](docs/deployment.md) | Infrastructure, environment variables, secrets handling |
| [`docs/on-premise.md`](docs/on-premise.md) | Air-gapped / on-premise rollout guidance |
| [`docs/migration.md`](docs/migration.md) | Migrating an existing monolithic `productix` DB to the modular apps |
| [`docs/versioning.md`](docs/versioning.md) | Versioning scheme & compatibility matrix |
| [`docs/rollback.md`](docs/rollback.md) | Rollback strategy & disaster recovery |
| [`docs/lifecycle.md`](docs/lifecycle.md) | App/module lifecycle & retirement policy |
| [`docs/future-module-template.md`](docs/future-module-template.md) | Copy-paste template for a new module app |
| [`docs/ci-matrix.md`](docs/ci-matrix.md) | CI install matrix (A/B/C combinations) |
| [`tests/README.md`](tests/README.md) | Acceptance test plan & evidence checklist |

---

## 🛠️ Technology Stack

| Layer | Technologies |
|---|---|
| **Backend Framework** | Frappe Framework v15, Python 3.11 |
| **ERP Base** | ERPNext v15 (Manufacturing, Stock, Buying, Accounts) |
| **Database** | MariaDB 10.6 (InnoDB, Barracuda, utf8mb4) |
| **Caching & Queues** | Redis (Cache, Queue, Socket.io) |
| **Frontend** | Vanilla JS (ES6+), jQuery, Frappe Desk, ApexCharts, FontAwesome |
| **AI / Machine Learning** | Groq AI API (Llama 3 / Mixtral for instant KPI insights) |
| **Infrastructure** | Docker, Docker Compose, Nginx Reverse Proxy |

---

## 🚀 Quick Start Guide

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows or macOS) or Docker Engine + Docker Compose v2 (Linux)
- Git

### 1. Clone the Repository
```bash
git clone https://github.com/milyaskhan-2127/comapny_kpi_tracking.git productix_erp
cd productix_erp
```

### 2. Configure Environment Variables
Copy the sample environment file:
```bash
cp .env.example .env
```
Edit `.env` to configure your database passwords, admin credentials, and SMTP settings.

> **Modular installation:** set `PRODUCTIX_APPS` to select which Productix apps
> to install. By default every app discovered via its
> `apps/<app>/<app>/productix_module.json` manifest is installed, with the
> platform app (manifest flagged `always_enabled`, today `productix_core`)
> first — a future app added under `apps/` needs no script change:
> ```bash
> # Examples (override the discovered set):
> PRODUCTIX_APPS="productix_core,productix_recipe"              # Recipe only
> PRODUCTIX_APPS="productix_core,productix_kpi"                 # KPI only
> PRODUCTIX_APPS="productix_core,productix_recipe,productix_kpi,productix_instruction"
> ```
> `setup_site.sh` / `setup_site.ps1` read `PRODUCTIX_APPS` from the environment
> or `.env` and install exactly that set (the platform app is auto-added if
> missing). The legacy `apps/productix` directory ships no manifest and is
> never picked up.

### 3. Start Multi-Container Stack
```bash
docker compose up -d
```

### 4. Initialize Site & Install Apps (Run Once)

**On Linux / macOS:**
```bash
bash setup_site.sh
```

**On Windows (PowerShell):**
```powershell
.\setup_site.ps1
```

This automated script will:
1. Wait for MariaDB to become healthy
2. Create the Frappe site `${SITE_NAME:-productix.local}`
3. Install the standard ERPNext app
4. Install each Productix app (manifest-discovered via `PRODUCTIX_APPS`,
   platform app first), which registers that app's module(s) in the module
   registry
5. Apply database fixtures, roles, and migration patches
6. Build and compile frontend assets

> **App names:** install via `bench install-app productix_core` and then any of
> `productix_recipe`, `productix_kpi`, `productix_instruction` — never the
> legacy `productix` app on a fresh install. The monolith is kept in this
> repository only as a **migration baseline** for existing databases (see
> `docs/migration.md`).

### 5. Access the Application
Open your browser and navigate to:
👉 **`http://localhost:8080`**

- **Default Administrator**: `Administrator`
- **Default Password**: `Admin@123` (or password specified in `.env`)

---

## ⚙️ Post-Installation Setup

### 1. Execute Setup Wizard
1. Log in as `Administrator`.
2. Open the **Company KPI Tracking** workspace from the Desk sidebar.
3. Launch the **KPI Setup Wizard** to automatically configure:
   - Default business units & departments (Production, Quality, Sales, HR, Finance, Maintenance).
   - Core starter KPIs and target definitions.
   - Recommended daily/monthly tracking templates.

### 2. Configure Groq AI Insights
1. Navigate to **KPI Settings** in Frappe Desk.
2. Enter your **Groq API Key**.
3. Select your preferred LLM model (e.g., `llama-3.3-70b-versatile`).
4. Instant AI commentary and variance root-cause analysis will now appear across all KPI dashboards.

### 3. Machine Telemetry Configuration
1. Open **Machine Management** → **Machine Type**.
2. Define parameters for your equipment (e.g., Temperature, Speed, Operating Hours).
3. Register your machines under **Machine** and link them to corresponding production KPIs.
4. Access the **Machine Health Dashboard** for live status monitoring.

---

## 👥 Roles & Security Permissions

Productix defines a role hierarchy ensuring strict segregation of duties:

| Role | Scope & Permissions |
|---|---|
| **Productix Admin** | Full administrative access across all ERP, KPI, Recipe, and System settings |
| **Productix Assistant Admin** | Operational management across recipes, KPIs, production, and reporting |
| **Productix CEO / Executive** | Read-only executive visibility across authorized departments and strategic KPIs |
| **Productix Production Manager** | Create & manage Recipes, Production Orders, and Production KPI entries |
| **Productix Store Keeper** | Manage Batches, Material Requests, Stock Entries, and Inventory KPIs |
| **Productix Purchase Manager** | Supplier management, Purchase Orders, GRNs, and Purchasing KPIs |
| **Productix General User** | Read access to assigned dashboards and designated KPI data entry forms |

---

## 🔄 Deployment & Database Migrations

When pulling updates or applying changes:

**On Linux / macOS:**
```bash
bash deploy.sh
```

**On Windows (PowerShell):**
```powershell
.\deploy.ps1
```

Both runners execute `bench migrate` on the site (running the `repoint_module_defs`
and other migration patches) and rebuild assets. `deploy.{sh,ps1}` also honour
`PRODUCTIX_APPS` when bootstrapping a new environment.

To manually run database migrations:
```bash
docker compose exec backend bench --site "$SITE_NAME" migrate
```

---

## 📦 Backup & Disaster Recovery

### Automated Backups
Productix includes an in-app **Backup Manager** located at `KPI Tracking → System → Backups`.

### Command-Line Backup
Generate a full timestamped database dump at any time:
```bash
bash backup.sh
```
Backups are archived in the `/backups/` directory with automatic compression.

---

## 🔐 Security & Secrets

- All SMTP credentials are supplied via environment variables (`.env`) only —
  they are **never committed** to the repository. See `.env.example`.
- Sensitive artifacts (SQL dumps, `.env`, `sites/`, logs) are git-ignored.
- **⚠️ Existing git history:** the pre-modularization history still contains an
  old SMTP password string. Rotate/revoke that credential, and rewrite or scrub
  history (`git filter-repo` / `BFG`) **before** this repository is ever pushed
  to a shared remote. Never commit customer database dumps.

## 📄 License & Attribution

Copyright © 2026 **TechoHub**. All rights reserved.  
Built and developed for **Productix ERP & Company KPI Tracking System**.
