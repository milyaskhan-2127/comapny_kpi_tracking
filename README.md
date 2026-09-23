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

```
productix_erp/
├── docker-compose.yml                  # Complete multi-container production stack
├── nginx.conf                          # Reverse proxy & static assets configuration
├── mariadb.cnf                         # Optimized MariaDB InnoDB configuration
├── setup_site.sh / setup_site.ps1      # Automated site initialization (Linux & Windows)
├── deploy.sh / deploy.ps1              # Deployment & migration runner (Linux & Windows)
├── backup.sh                           # Standalone database backup script
├── common_site_config.json.template    # Site configuration template
├── README.md                           # Project documentation
│
└── apps/
    └── productix/                      # Productix Frappe Application
        ├── requirements.txt            # Python dependencies (Groq, etc.)
        ├── setup.py                    # Package setup definition
        └── productix/
            ├── hooks.py                # Frappe app hooks & event listeners
            ├── modules.txt             # Installed modules declaration
            ├── patches.txt             # Database migration patches
            ├── setup_data.py           # Default system fixtures & bootstrap data
            ├── setup_workspace.py      # Desk workspace configuration
            │
            ├── recipe_management/      # [MODULE] Recipe & Batch Production
            │   ├── doctype/
            │   │   ├── recipe/         # BOM, recipe items, yield & cost
            │   │   ├── recipe_item/    # Raw material child table
            │   │   ├── recipe_extra/   # Packaging & overhead child table
            │   │   ├── production_order/ # Production execution lifecycle
            │   │   ├── production_order_extra/
            │   │   └── consumption_log/# FEFO stock consumption audit
            │   ├── report/             # Production & Costing reports
            │   └── utils/              # FEFO stock deduction & GRN hooks
            │
            ├── kpi_tracking/           # [MODULE] Company KPI Tracking & Analytics
            │   ├── doctype/
            │   │   ├── kpi_definition/ # Master KPI configuration & targets
            │   │   ├── kpi_department/ # Departmental structures
            │   │   ├── kpi_business_unit/
            │   │   ├── kpi_formula/    # Dynamic math formula definition
            │   │   ├── kpi_formula_variable/
            │   │   ├── kpi_data_entry/ # Periodic actuals submission
            │   │   ├── kpi_data_entry_value/
            │   │   ├── kpi_alert/      # Automated alert records
            │   │   ├── kpi_operational_table/ # Dynamic operational tables
            │   │   ├── kpi_operational_data/
            │   │   ├── kpi_template/   # Department starter templates
            │   │   ├── kpi_user_assignment/
            │   │   ├── kpi_ceo_access/ # Granular CEO permissions
            │   │   ├── kpi_ceo_department_access/
            │   │   ├── kpi_ceo_kpi_access/
            │   │   ├── machine/        # Machinery registry
            │   │   ├── machine_type/   # Equipment categories
            │   │   ├── machine_type_parameter/
            │   │   ├── machine_reading/# Sensor readings & telemetry
            │   │   ├── machine_reading_value/
            │   │   ├── machine_health_log/
            │   │   └── machine_kpi_link/ # Direct Machine-to-KPI links
            │   ├── page/               # Custom SPA Dashboards
            │   │   ├── kpi_company_overview/     # Executive Company Scorecard
            │   │   ├── kpi_department_dashboard/ # Department Analytics
            │   │   ├── kpi_setup_wizard/         # Guided KPI Setup Flow
            │   │   ├── kpi_action_center/        # Alert & Incident Triage
            │   │   ├── kpi_data_entry_page/      # Rapid bulk data entry
            │   │   ├── machine_health/           # Live Machine Telemetry UI
            │   │   └── backups/                  # Integrated Database Backup Page
            │   ├── report/             # KPI Performance & Audit Reports
            │   ├── services/           # Analytics, Period, Machine & AI Engines
            │   └── security/           # Dynamic role permission enforcement
            │
            ├── subscription_management/# [MODULE] Licensing & Tenants
            │   ├── doctype/
            │   │   ├── productix_license/ # License keys & seat limits
            │   │   └── productix_tenant/
            │   └── utils/              # License validation utilities
            │
            ├── instruction_room/       # [MODULE] Internal Team Messaging
            │   └── doctype/
            │       ├── instruction_message/
            │       └── message_notification/
            │
            ├── alerts/                 # [MODULE] Background Tasks & Notifications
            │   ├── doctype/ai_agent_log/
            │   └── tasks.py            # Daily cron jobs for low stock & expiry
            │
            ├── api/                    # Custom REST & RPC API Endpoints
            │   ├── backup.py           # Backup manager backend
            │   ├── subscription.py     # Payment webhook receiver
            │   └── inventory.py        # Stock & batch queries
            │
            ├── migrations/             # Custom schema & data migrations
            ├── fixtures/               # Seed roles and custom fields
            └── public/                 # Client assets (CSS, JS overrides)
```

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
2. Create the Frappe site `productix.local`
3. Install the standard ERPNext app
4. Install the custom `productix` app
5. Apply database fixtures, roles, and migration patches
6. Build and compile frontend assets

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

To manually run database migrations:
```bash
docker compose exec backend bench --site productix.local migrate
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

## 📄 License & Attribution

Copyright © 2026 **TechoHub**. All rights reserved.  
Built and developed for **Productix ERP & Company KPI Tracking System**.
