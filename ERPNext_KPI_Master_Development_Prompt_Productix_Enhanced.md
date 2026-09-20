# MASTER DEVELOPMENT PROMPT

# ERPNext KPI & Company Performance Tracking System

## IMPORTANT: READ THIS ENTIRE PROMPT BEFORE IMPLEMENTING ANYTHING

You are acting as a:

* Senior ERPNext/Frappe Architect
* Senior Backend Engineer
* Senior Frontend Engineer
* Database Architect
* UX/UI Designer
* Security Engineer
* Analytics Engineer
* Prediction/Forecasting Engineer
* QA Engineer
* Product Architect

Your task is to **design, implement, test, debug, optimize, document, and deliver a production-ready KPI & Company Performance Tracking System inside the existing ERPNext/Frappe installation.**

This is NOT merely a dashboard customization.

This is a complete KPI/performance-management application that should provide a significantly more user-friendly experience than a raw ERPNext configuration.

The final product should feel like a dedicated modern:

> **Company Performance / KPI Analytics Platform**

while using ERPNext/Frappe as the underlying platform.

---

# 1. ABSOLUTE NON-NEGOTIABLE RULE

## KPI TRACKING AND RECIPE MANAGEMENT MUST BE TWO SEPARATE APPLICATIONS

There is an existing Recipe Management System in the ERPNext installation.

The new KPI Tracking System is a completely separate application.

These two systems must NEVER be treated as one product.

Conceptually, the installation must look like:

```text
ERPNext Installation
│
├── Recipe Management Application
│   ├── Recipe Workspace
│   ├── Recipe Dashboard
│   ├── Recipe DocTypes
│   ├── Recipe APIs
│   ├── Recipe Routes
│   ├── Recipe Frontend
│   └── Recipe Permissions
│
└── KPI Tracking Application
    ├── KPI Workspace
    ├── Company Overview
    ├── Department Dashboards
    ├── KPI Management
    ├── KPI Templates
    ├── KPI Data Entry
    ├── Analytics
    ├── Trends
    ├── Growth
    ├── Predictions
    ├── Prediction Accuracy
    ├── Alerts
    ├── Notifications
    ├── Reports
    ├── KPI DocTypes
    ├── KPI APIs
    ├── KPI Routes
    ├── KPI Frontend
    └── KPI Permissions
```

## Strict separation requirements

Do NOT:

* Merge Recipe and KPI dashboards.
* Merge Recipe and KPI workspaces.
* Merge Recipe and KPI navigation.
* Reuse Recipe business logic unnecessarily.
* Make KPI functionality depend on Recipe DocTypes.
* Make Recipe functionality depend on KPI DocTypes.
* Add KPI buttons to Recipe pages.
* Add Recipe buttons to KPI pages.
* Mix their permissions.
* Mix their routes.
* Mix their API namespaces.
* Mix their CSS.
* Mix their JavaScript.
* Create hidden dependencies.
* Modify Recipe business logic merely to implement KPI functionality.
* Copy the Recipe application unnecessarily.
* Make KPI functionality fail if Recipe Management is removed.
* Make Recipe functionality fail if KPI Tracking is removed.

Future integration may be possible, but **no Recipe integration is required for the current version.**

If future integration is eventually required, it must occur through a clearly defined API/integration layer.

---

# 2. PRODUCT VISION

The purpose of this application is to allow a company to track:

```text
Company
    ↓
Departments
    ↓
KPIs
    ↓
KPI Data
    ↓
Historical Data
    ↓
Trend
    ↓
Growth
    ↓
Prediction
    ↓
Prediction vs Actual
    ↓
Intelligent Analysis
    ↓
Alerts
    ↓
Notifications
    ↓
Company Performance
```

The application must answer three questions immediately:

### 1. How are we performing?

### 2. What is changing?

### 3. What is likely to happen next?

The system must make this understandable to:

* CEO
* Company Admin
* Department Manager
* Department User

without requiring them to understand ERPNext technical concepts.

---

# 3. MOST IMPORTANT UX PRINCIPLE

## ERPNext is the backend platform.

## The KPI Tracking application is the product experience.

Do not force users to interact with complicated ERPNext configuration screens when a simpler custom interface can be provided.

The user should feel like they are using:

> A dedicated KPI analytics application

and NOT:

> A complicated ERPNext customization.

Use ERPNext/Frappe capabilities underneath where appropriate, but create a friendly layer over them.

---

# 4. ADMIN EXPERIENCE — ZERO-CONFIGURATION MINDSET

The biggest UX goal is:

> **An administrator should be able to set up a company without needing to understand ERPNext.**

Do NOT expect the administrator to manually create dozens of DocTypes, dashboards, charts, permissions, and configurations.

Instead, provide a guided setup experience.

---

# 5. ADMIN SETUP WIZARD

When the KPI application is installed for a new company, provide a:

# Performance Setup Wizard

The wizard should guide the administrator through setup.

Conceptually:

```text
Welcome
   ↓
Company Setup
   ↓
Departments
   ↓
Users
   ↓
KPI Templates
   ↓
KPIs
   ↓
Targets
   ↓
KPI Owners
   ↓
Review
   ↓
Finish
```

The admin should always understand:

* What has been completed.
* What remains.
* What the next step is.

---

# 6. SETUP PROGRESS

Display something similar to:

```text
Performance Setup

████████████████░░░░ 80%

✓ Company
✓ Departments
✓ Users
✓ KPI Templates
✓ KPIs
⚠ Targets
⚠ KPI Owners

[Continue Setup]
```

Never leave the administrator wondering:

> "What am I supposed to configure next?"

---

# 7. STEP 1 — COMPANY SETUP

Collect only essential information.

Example:

```text
Company Name
[ __________________ ]

Industry
[ Manufacturing ▼ ]

Currency
[ USD ▼ ]

Fiscal Year
[ 2026 ▼ ]

[Continue]
```

Use existing ERPNext company information where appropriate instead of duplicating it unnecessarily.

---

# 8. STEP 2 — DEPARTMENT SETUP

Initially support these departments:

1. Sales
2. Production
3. QC
4. Safety
5. Procurement
6. R&D
7. Supply Chain

However:

## DO NOT HARD-CODE THESE DEPARTMENTS INTO BUSINESS LOGIC.

Departments must be database records.

The administrator must be able to:

* Create departments.
* Edit departments.
* Activate departments.
* Deactivate departments.
* Assign users.
* Assign KPIs.
* View department performance.

Future departments must be addable without changing source code.

---

# 9. DEPARTMENT TEMPLATE EXPERIENCE

When setting up departments, provide convenient defaults.

Example:

```text
Choose Departments

☑ Sales
☑ Production
☑ QC
☑ Safety
☑ Procurement
☑ R&D
☑ Supply Chain

+ Add Custom Department
```

The admin can select the departments they actually use.

Do not force a company to use every predefined department.

---

# 10. STEP 3 — USER SETUP

Allow administrators to assign users to departments.

Example:

```text
User                  Department       Role

Ahmed                 Sales            KPI Contributor
Ali                   Production       KPI Contributor
Sara                  Finance          Manager
Usman                 Sales            Manager
CEO                   Company          CEO
```

Department assignment must drive access control.

Users must never be able to assign themselves to another department.

---

# 11. SIMPLE ROLE MODEL

At minimum support:

## CEO / Super Admin

Can:

* View company performance.
* View every department.
* View all KPIs.
* Create KPIs.
* Edit KPIs.
* Activate/deactivate KPIs.
* Configure targets.
* Configure frequency.
* Configure KPI inputs.
* Configure prediction.
* Configure alerts.
* Manage departments.
* Manage users.
* View historical data.
* View trends.
* View growth.
* View predictions.
* View prediction accuracy.
* View reports.
* View audit information.

---

## Department Manager

Can:

* View their department.
* View department KPIs.
* View department historical data.
* Enter data where authorized.
* Review submissions.
* View trends.
* View growth.
* View predictions.
* View alerts.

They cannot configure company-level settings unless explicitly granted.

---

## KPI Contributor / Department User

Can:

* View their department dashboard.
* View their assigned KPIs.
* Enter KPI data.
* View historical department KPI data where permitted.
* View KPI trends.
* View KPI growth.
* View KPI predictions.
* View relevant alerts.

Cannot:

* Create KPIs.
* Delete KPIs.
* Modify KPI configuration.
* Change targets.
* Change frequency.
* Manage departments.
* Manage users.
* Access company administration.
* Access another department.

---

# 12. SECURITY — FRONTEND HIDING IS NOT SECURITY

Hiding buttons is NOT sufficient.

All backend operations must verify:

1. Current user.
2. Current role.
3. Assigned department.
4. Requested KPI.
5. KPI department.
6. Requested data record.
7. Permission to perform the requested action.

Example:

```text
Sales User
    ↓
Requests Production KPI API
    ↓
Backend Authorization
    ↓
ACCESS DENIED
```

Even if the Sales user manually changes a KPI ID in the browser, they must not be able to retrieve Production data.

All department isolation must be enforced server-side.

---

# 13. KPI TEMPLATE SYSTEM

One of the most important UX features is:

# KPI Templates

Do not make the administrator create every KPI from zero.

Provide predefined templates.

Example:

## Sales KPI Template

```text
✓ Revenue
✓ Sales Growth
✓ New Customers
✓ Conversion Rate
✓ Average Deal Size
✓ Customer Retention
```

## Production KPI Template

```text
✓ Production Quantity
✓ Production Efficiency
✓ Downtime
✓ Rejection Rate
✓ Capacity Utilization
```

## QC KPI Template

```text
✓ Defect Rate
✓ First Pass Yield
✓ Inspection Completion
✓ Rejection Rate
```

## Safety KPI Template

```text
✓ Incidents
✓ Near Misses
✓ Lost Time Injury
✓ Safety Compliance
```

## Procurement KPI Template

```text
✓ Purchase Cost
✓ Supplier Performance
✓ On-Time Delivery
✓ Purchase Cycle Time
```

## R&D KPI Template

```text
✓ Projects Completed
✓ Development Progress
✓ Research Milestones
✓ Time to Completion
```

## Supply Chain KPI Template

```text
✓ On-Time Delivery
✓ Inventory Turnover
✓ Stock Accuracy
✓ Lead Time
```

These are defaults only.

Administrators must be able to:

* Add KPIs.
* Remove KPIs.
* Modify KPIs.
* Create custom KPI templates.
* Create completely custom KPIs.

---

# 14. APPLY KPI TEMPLATE

The experience should be:

```text
Sales Department

Recommended KPI Template

☑ Revenue
☑ New Customers
☑ Conversion Rate
☑ Sales Growth
☐ Average Deal Size

[Add Selected KPIs]
```

After clicking:

```text
KPIs Created Successfully

✓ Revenue
✓ New Customers
✓ Conversion Rate
✓ Sales Growth

[Configure Targets]
```

Do not force the administrator to create four separate records manually.

---

# 15. CREATE KPI WIZARD

Do not expose a complicated raw ERPNext form as the primary KPI creation experience.

Instead provide:

# Create KPI

## Step 1 — Basic Information

```text
KPI Name
[ Monthly Revenue ]

Department
[ Sales ▼ ]

Description
[ __________________ ]

KPI Code
[ SALES-REV-MONTHLY ]
```

---

## Step 2 — Measurement

```text
How is this KPI measured?

○ Number
○ Integer
○ Decimal
○ Percentage
○ Currency
○ Duration
○ Rating
```

---

## Step 3 — Target

```text
Target Type

○ Fixed Target
○ Growth Target
○ Range
○ No Target

Target
[ 10,000 ]

Minimum Acceptable
[ 8,000 ]
```

---

## Step 4 — Frequency

Initially support:

* Daily
* Weekly
* Monthly

Architect the system for future:

* Hourly
* Quarterly
* Yearly

---

## Step 5 — Data Requirements

Allow the administrator to define what users need to enter.

Example:

```text
Production Efficiency

Inputs:

Planned Production     Number     Required
Actual Production      Number     Required
Downtime               Decimal    Required
Rejected Units         Integer    Optional

Efficiency %
Automatically calculated
```

---

## Step 6 — Prediction

```text
Enable Prediction
[ ✓ ]

Prediction Method
[ Automatic ▼ ]

Minimum Historical Data
[ configurable ]
```

---

## Step 7 — Alerts

```text
Enable Alerts
[ ✓ ]

Target Miss
[ ✓ ]

Negative Trend
[ ✓ ]

Growth Decline
[ ✓ ]

Prediction Miss
[ ✓ ]

Repeated Decline
[ ✓ ]
```

---

## Step 8 — Ownership

```text
KPI Owner
[ Sales Manager ▼ ]

Data Entry Role
[ KPI Contributor ▼ ]
```

---

## Step 9 — Review

Display a summary:

```text
KPI Summary

Name: Monthly Revenue
Department: Sales
Measurement: Currency
Frequency: Monthly
Target: 10,000
Prediction: Enabled
Alerts: Enabled

[Back] [Create KPI]
```

---

# 16. KPI DEFINITION DATA MODEL

Create a dedicated KPI Definition DocType.

Recommended fields:

* KPI Name
* KPI Code
* Department
* Description
* Measurement Unit
* Target Value
* Minimum Acceptable Value
* Frequency
* Start Date
* Active
* Data Entry Requirements
* Prediction Enabled
* Alert Enabled
* Alert Threshold
* Growth Calculation Method
* Trend Calculation Method
* Prediction Method/Configuration
* Alert Severity Configuration
* Allow Negative Values
* Decimal Precision
* Weight / Importance

KPI Code must be unique.

---

# 17. DYNAMIC KPI INPUT SYSTEM

Different KPIs require different inputs.

The architecture must support configurable KPI input parameters.

Supported types should include:

* Number
* Integer
* Decimal
* Percentage
* Currency
* Text
* Date
* Boolean
* Duration where appropriate

Each input should support:

* Field name
* Label
* Data type
* Required
* Minimum
* Maximum
* Decimal precision
* Unit
* Allow negative
* Calculation participation

All validation must also occur server-side.

---

# 18. KPI DATA ENTRY — EXTREMELY SIMPLE

Normal employees should NOT navigate through complicated ERPNext forms.

The main employee action is:

> **Enter KPI Data**

Example:

# September KPI Submission

```text
Sales Department

Revenue
Target: 100,000

Actual
[ __________ ]

New Customers
Target: 50

Actual
[ __________ ]

Conversion Rate
Target: 20%

Actual
[ __________ ]

Customer Retention
Target: 90%

Actual
[ __________ ]
```

Display:

```text
3 / 4 KPIs completed

██████████████░░ 75%
```

Buttons:

```text
[Save Draft]       [Submit KPIs]
```

The system should automatically know:

* User
* Department
* KPI
* Period
* Frequency

The employee should not manually select another department.

---

# 19. DYNAMIC DATA ENTRY

The data-entry UI must be generated from KPI configuration.

For example:

KPI:

```text
Production Efficiency
```

Inputs:

```text
Planned Production
Actual Production
Downtime
Rejection
```

The system automatically builds the appropriate form.

If another KPI requires:

```text
Supplier Delivery Performance
```

it may contain:

```text
Orders
On-Time Orders
Late Orders
```

The UI should adapt automatically.

---

# 20. SERVER-SIDE CALCULATIONS

Where a KPI value can be calculated automatically:

Calculate it on the server.

Example:

```text
Efficiency %

=
Actual Production / Planned Production × 100
```

Do not trust client-side calculations.

The server is authoritative.

---

# 21. KPI DATA VALIDATION

Reject:

* Missing required values.
* Invalid data types.
* Invalid dates.
* Invalid numbers.
* Invalid negative values.
* Values outside configured boundaries.
* Invalid KPI IDs.
* Inactive KPIs.
* Missing departments.
* Unauthorized department submissions.
* Duplicate submissions.

Prevent duplicates using appropriate business rules such as:

```text
KPI + Department + Period/Date
```

depending on frequency.

---

# 22. KPI DATA RECORD

Every submission should record:

* KPI
* Department
* User
* Date
* Period
* Input Values
* Calculated Value
* Target
* Status
* Created At
* Modified At

Never allow the frontend to spoof the user or department.

Derive authenticated user from the server session.

---

# 23. EMPLOYEE EXPERIENCE

The employee dashboard should be much simpler than the administrator dashboard.

Example:

```text
Good Morning, Ahmed

Sales Performance

My KPI Submission

████████████░░░ 80%

4 / 5 Complete

[Complete Submission]

My KPIs

Revenue             92%  ↑
New Customers      105%  ↑
Conversion Rate     84%  ↓
Retention           98%  ↑
```

The employee should immediately understand:

* What they need to enter.
* What is completed.
* What is performing well.
* What needs attention.

---

# 24. ADMIN DASHBOARD

The administrator should have:

# Company Overview

This is the executive-level dashboard.

Display:

* Overall company performance.
* Company KPI health.
* Company growth.
* Company trend.
* Company prediction.
* Department performance.
* Critical alerts.
* Department comparison.
* Performance distribution.

Example:

```text
COMPANY PERFORMANCE

Revenue              $4.8M       +12.4%
Profit               $920K       +8.2%
Overall KPI Health    86%        ↑
Company Growth        14.7%      ↑

Department Performance

Sales                 92%   ↑
Production            89%   ↑
QC                    78%   ↓
Safety                95%   ↑
Procurement            82%   →
R&D                    88%   ↑
Supply Chain           76%   ↓
```

---

# 25. DEPARTMENT DASHBOARD

Every department uses the same dashboard architecture but receives its own data.

Example:

# Sales Dashboard

Display:

* Sales KPIs.
* KPI cards.
* Current values.
* Targets.
* Target achievement.
* Growth.
* Trend.
* Prediction.
* Prediction vs actual.
* Historical performance.
* Alerts.

The same architecture automatically supports:

* Production.
* QC.
* Safety.
* Procurement.
* R&D.
* Supply Chain.
* Future departments.

Do NOT create seven separate codebases.

Build reusable dashboard components and filter them by department.

---

# 26. KPI CARD DESIGN

Each KPI card should communicate:

```text
KPI NAME

Current Value
50,000

Target
70,000

Achievement
71.4%

Growth
+12.4%

Trend
Improving

Prediction
65,000

Status
Below Target
```

The card should make the KPI understandable without opening another page.

---

# 27. DASHBOARD INFORMATION HIERARCHY

When a dashboard opens, prioritize:

1. Current Performance
2. KPI Health
3. Target vs Actual
4. Growth
5. Trend
6. Prediction
7. Alerts
8. Historical Analysis

The user should not need to open multiple forms to understand performance.

---

# 28. CEO DEPARTMENT SELECTOR

CEO/Admin should have a simple department selector:

```text
COMPANY OVERVIEW

[ Sales ]
[ Production ]
[ QC ]
[ Safety ]
[ Procurement ]
[ R&D ]
[ Supply Chain ]
```

Clicking Sales:

```text
Sales Dashboard
```

Clicking Production:

```text
Production Dashboard
```

Only authorized company-level users may use this selector.

---

# 29. LOGIN ROUTING

After login:

## CEO/Admin

Automatically open:

```text
Company Overview
```

They can then navigate:

```text
Company Overview
   ↓
Sales
Production
QC
Safety
Procurement
R&D
Supply Chain
```

---

## Department User

Determine assigned department.

Example:

```text
User Department = Sales
```

Automatically open:

```text
Sales Dashboard
```

Do NOT allow the Sales user to switch to Production.

---

# 30. THREE CORE ANALYTICS

Every KPI must support:

1. Trend
2. Growth
3. Prediction

These should be visible throughout the application.

---

# 31. TREND ANALYSIS

Trend determines the direction of KPI performance.

Support:

* Improving
* Declining
* Stable
* Insufficient Data

Use historical actual KPI values.

Do not fabricate missing values.

Do not generate random classifications.

Trend logic should be modular and configurable.

---

# 32. GROWTH CALCULATION

Growth compares the current relevant period to the previous relevant period.

Daily:

```text
Current Day vs Previous Day
```

Weekly:

```text
Current Week vs Previous Week
```

Monthly:

```text
Current Month vs Previous Month
```

Default:

```text
Growth %
=
((Current Value - Previous Value) / Previous Value) × 100
```

Safely handle zero previous values.

Never return infinity.

Use states such as:

* Not Available
* Undefined
* New Baseline

where appropriate.

---

# 33. PREDICTION ENGINE

Create a modular prediction service.

Prediction must use historical KPI data.

Never create fake predictions.

The system should:

1. Retrieve historical KPI values.
2. Validate data sufficiency.
3. Analyze historical behavior.
4. Identify trend.
5. Generate prediction.
6. Store prediction.
7. Compare future actual against prediction.
8. Calculate variance.
9. Track prediction performance.

If insufficient historical data exists:

```text
Insufficient data for prediction.
```

Do not generate a random number.

The prediction algorithm should be modular so it can evolve later.

---

# 34. PREDICTION RECORD

Create KPI Prediction records containing:

* KPI
* Department
* Prediction Date
* Target Period
* Predicted Value
* Actual Value
* Variance
* Variance Percentage
* Accuracy / Difference
* Status
* Prediction Method
* Created At

Prediction history must remain auditable.

---

# 35. PREDICTION VS ACTUAL

When the actual value becomes available:

Compare:

```text
Predicted Value
vs
Actual Value
```

Calculate:

```text
Variance
Variance %
Status
```

Example:

```text
Prediction = 100
Actual = 50

Variance = -50
Variance % = -50%

Status = Prediction Miss
```

Handle zero prediction safely.

---

# 36. INTELLIGENT ANALYTICS / AGENT LAYER

Create an independent analytics/agent service.

The initial purpose is:

> Automatically analyze KPI performance and identify meaningful issues.

Analyze:

* Growth.
* Trend.
* Target.
* Prediction.
* Prediction vs actual.
* Repeated decline.
* Threshold breaches.

The agent should be deterministic and explainable wherever possible.

Do NOT generate meaningless AI text for every KPI.

Only produce intelligent commentary when a meaningful condition exists.

---

# 37. ALERT CONDITIONS

Support at least:

## Growth Decline

If configured growth conditions indicate a meaningful decline:

```text
Sales growth has declined compared with the previous period.
```

---

## Negative Trend

If a KPI persistently moves downward:

```text
Sales KPI is showing a declining trend.
```

---

## Prediction Miss

If actual performance is significantly below prediction:

```text
Actual Sales were significantly below the predicted value.
```

---

## Target Miss

If actual performance falls below target:

```text
Production target was not achieved.
```

---

## Repeated Decline

If a KPI declines across multiple consecutive periods:

Generate a higher-priority alert.

The number of consecutive periods must be configurable.

---

# 38. ALERT SEVERITY

At minimum:

* Informational
* Warning
* Critical

Example:

```text
Warning
KPI slightly below target.
```

```text
Critical
KPI has experienced repeated decline.
```

Do not spam users.

---

# 39. ALERT DEDUPLICATION

Do not create the same alert repeatedly during every background job.

Consider:

* KPI
* Alert Type
* Department
* Time Period
* Existing unresolved alert
* Cooldown

If an unresolved alert already exists for the same condition, do not create another duplicate.

---

# 40. NOTIFICATIONS

Initial notification channel:

> ERPNext in-app notifications.

Do NOT implement initially:

* Email
* WhatsApp
* SMS

unless explicitly requested later.

Architect notification handling so additional channels can be added in the future.

---

# 41. NOTIFICATION RECIPIENTS

Department-specific alerts should go only to relevant users.

Example:

```text
Sales Alert
↓
Sales Manager
Sales KPI Users
CEO/Admin if Critical
```

Production alerts must not be sent to unrelated departments.

---

# 42. COMPANY-LEVEL KPI CALCULATION

Do NOT simply average all KPIs.

KPIs can have:

* Different units.
* Different scales.
* Different frequencies.
* Different importance.
* Different targets.

Therefore company-level aggregation must support:

* Normalization.
* KPI weights.
* Transparent aggregation logic.

For example:

```text
Sales          92%
Production     89%
QC             78%
Safety         95%
Procurement    82%
R&D            88%
Supply Chain   76%
```

The CEO should immediately understand which departments are strong and which require attention.

---

# 43. ADMIN "PERFORMANCE SETUP CENTER"

Create a central setup page.

Example:

```text
PERFORMANCE SETUP

Company
✓ Complete

Departments
✓ 7 departments

Users
✓ 24 users

KPI Templates
✓ Configured

KPIs
⚠ 18 KPIs configured
   4 need targets

Data Entry
✓ Ready

Dashboard
✓ Ready

Predictions
⚠ Waiting for historical data

Alerts
✓ Configured
```

This becomes the admin's control center.

---

# 44. EXCEL IMPORT

Provide an optional KPI import capability.

Example spreadsheet structure:

```text
Department | KPI | Type | Frequency | Target | Owner

Sales | Revenue | Currency | Monthly | 1000000 | Sales Manager
Sales | Leads | Number | Monthly | 500 | Sales Manager
HR | Turnover | Percentage | Monthly | 5 | HR Manager
```

The administrator can upload the completed spreadsheet.

The system validates it and creates the appropriate KPI configuration.

Do not bypass permission or validation through import.

---

# 45. NAVIGATION

Create an independent:

# KPI Tracking

workspace.

Admin:

```text
KPI Tracking

├── Company Overview
├── Setup
├── Departments
├── Users
├── KPI Templates
├── KPIs
├── KPI Data
├── Predictions
├── Alerts
└── Reports
```

Department User:

```text
KPI Tracking

├── My Dashboard
├── My KPIs
├── Data Entry
└── My Alerts
```

Only display authorized navigation items.

---

# 46. DATA MODEL

Recommended core DocTypes:

```text
Department
KPI Definition
KPI Input Definition
KPI Data Entry
KPI Prediction
KPI Alert
KPI Template
KPI Template Item
```

Add supporting configuration DocTypes only where required.

Keep the model normalized and scalable.

---

# 47. DEPARTMENT DOCTYPE

Fields:

* Department Name
* Department Code
* Description
* Active

Department Code must be unique.

---

# 48. KPI DEFINITION DOCTYPE

Fields:

* KPI Name
* KPI Code
* Department
* Description
* Measurement Unit
* Target Value
* Minimum Acceptable Value
* Frequency
* Start Date
* Active
* Prediction Enabled
* Alert Enabled
* Alert Threshold
* Growth Method
* Trend Method
* Prediction Configuration
* Alert Severity Configuration
* Allow Negative Values
* Decimal Precision
* Weight

KPI Code must be unique.

---

# 49. KPI INPUT DEFINITION

Allow each KPI to define its own inputs.

Fields may include:

* Field Name
* Label
* Type
* Required
* Minimum
* Maximum
* Unit
* Decimal Precision
* Allow Negative
* Used in Calculation
* Calculation Order

---

# 50. KPI DATA ENTRY DOCTYPE

Store:

* KPI
* Department
* User
* Date
* Period
* Input Values
* Calculated Value
* Target
* Status
* Created At
* Modified At

---

# 51. KPI PREDICTION DOCTYPE

Store:

* KPI
* Department
* Prediction Date
* Target Period
* Predicted Value
* Actual Value
* Variance
* Variance Percentage
* Accuracy
* Status
* Prediction Method

---

# 52. KPI ALERT DOCTYPE

Store:

* KPI
* Department
* Alert Type
* Severity
* Message
* Trigger Period
* Status
* Created At
* Resolved At
* Cooldown Information

---

# 53. BACKEND API ARCHITECTURE

Use a dedicated KPI namespace.

Conceptually:

```text
kpi_tracking.api.dashboard
kpi_tracking.api.kpi
kpi_tracking.api.data_entry
kpi_tracking.api.prediction
kpi_tracking.api.alerts
kpi_tracking.api.departments
```

Never expose unrestricted APIs.

Every API must perform authorization.

---

# 54. DATA ACCESS FLOW

Every request should follow:

```text
Current User
      ↓
Role Check
      ↓
Department Check
      ↓
Allowed KPI Query
      ↓
Allowed KPI Data
      ↓
Analytics
      ↓
Dashboard
```

For CEO:

```text
CEO
 ↓
Company Access
 ↓
All Departments
 ↓
All KPIs
 ↓
Company Analytics
```

For Department User:

```text
Department User
 ↓
Assigned Department
 ↓
Department KPIs
 ↓
Department Data
 ↓
Department Analytics
```

---

# 55. BACKGROUND PROCESSING

Do not make users wait for heavy analytics.

After KPI submission:

```text
KPI Data Submitted
        ↓
Validate
        ↓
Save
        ↓
Queue Background Job
        ↓
Trend Analysis
        ↓
Growth Calculation
        ↓
Prediction
        ↓
Prediction vs Actual
        ↓
Alert Evaluation
        ↓
Notification
```

Use Frappe background processing/scheduler mechanisms appropriate to the installed version.

---

# 56. PERFORMANCE

Do not load the entire KPI database every time a dashboard opens.

Use:

* Efficient queries.
* Aggregations.
* Indexed fields.
* Pagination.
* Limited historical ranges.
* Background jobs.
* Caching where appropriate.
* Lazy loading where appropriate.
* Small API responses.

Index frequently queried fields such as:

* Department
* KPI
* Date
* Period
* User
* Status
* Active

---

# 57. UI DESIGN REQUIREMENTS

The UI should look like a modern analytics product.

Use:

* KPI cards.
* Charts.
* Trend indicators.
* Growth indicators.
* Prediction cards.
* Target-vs-actual visualizations.
* Alert badges.
* Status indicators.
* Department cards.
* Clean spacing.
* Clear typography.
* Responsive layouts.
* Strong visual hierarchy.

Avoid making every screen look like a generic ERPNext form.

---

# 58. RESPONSIVE DESIGN

The KPI dashboard should work properly on:

* Desktop.
* Laptop.
* Tablet.
* Mobile where practical.

Data-entry screens should be particularly mobile-friendly because users may enter KPI values away from their desks.

---

# 59. EMPTY STATES

Design proper empty states.

No KPIs:

```text
No KPIs have been configured for this department yet.

[Configure KPIs]
```

No historical data:

```text
No historical data available.
```

Insufficient prediction data:

```text
Insufficient data for prediction.
```

No alerts:

```text
No active alerts.
```

Do not display broken charts or misleading zeros.

---

# 60. AUDITABILITY

Maintain complete auditability.

Track:

* Who entered data.
* When it was entered.
* KPI.
* Original value.
* Modified value.
* Who modified it.
* Modification timestamp.
* Period.

Use Frappe's native audit/versioning facilities where appropriate.

---

# 61. DEVELOPMENT MUST FOLLOW THIS EXACT FLOW

Do NOT blindly create the whole application in one uncontrolled operation.

Follow this project flow.

---

# PHASE 0 — READ AND UNDERSTAND

Before touching code:

1. Read this entire prompt.
2. Understand the existing Recipe application.
3. Understand that Recipe and KPI are separate products.
4. Understand the existing ERPNext environment.
5. Understand the required department isolation.
6. Understand the required admin UX.
7. Understand the analytics flow.

Do not start coding before completing discovery.

---

# PHASE 1 — ENVIRONMENT DISCOVERY

Inspect:

* Frappe version.
* ERPNext version.
* Installed apps.
* Bench structure.
* Existing app structure.
* Existing Recipe application.
* Recipe app name.
* Recipe module.
* Existing DocTypes.
* Existing routes.
* Existing workspaces.
* Existing dashboards.
* Existing roles.
* Existing permissions.
* Existing hooks.
* Existing JS.
* Existing CSS.
* Existing APIs.
* Existing custom scripts.
* Existing fixtures.
* Existing website/page routes.

Determine exactly how the current system is structured.

Do NOT guess versions or APIs.

---

# PHASE 2 — RECIPE SAFETY ASSESSMENT

Before implementing KPI:

Document:

```text
Recipe Application
├── App
├── Module
├── Workspaces
├── Routes
├── DocTypes
├── APIs
├── JS
├── CSS
├── Permissions
└── Hooks
```

Identify what must NOT be modified.

If modification is unavoidable, explain why before doing it.

Prefer new KPI files instead.

---

# PHASE 3 — KPI ARCHITECTURE DESIGN

Define:

* KPI application/module.
* Namespace.
* Folder structure.
* DocTypes.
* Roles.
* Permissions.
* API architecture.
* Dashboard architecture.
* Setup Wizard.
* KPI Template system.
* KPI Input system.
* Analytics services.
* Prediction services.
* Alert engine.
* Notification service.
* Background jobs.

Produce an architecture assessment before implementation.

---

# PHASE 4 — CORE DATA MODEL

Implement first:

```text
Department
KPI Template
KPI Template Item
KPI Definition
KPI Input Definition
KPI Data Entry
KPI Prediction
KPI Alert
```

Ensure relationships are correct.

Do not build advanced UI before the underlying data model is sound.

---

# PHASE 5 — SECURITY

Implement:

* Roles.
* Role permissions.
* Department restrictions.
* Document permissions.
* Server-side authorization.
* API authorization.
* Department isolation.

Then test:

```text
Sales → Sales = Allowed
Sales → Production = Denied
Production → Sales = Denied
CEO → Everything = Allowed
```

Security must be proven before continuing.

---

# PHASE 6 — ADMIN SETUP EXPERIENCE

Build:

1. Setup Center.
2. Setup Wizard.
3. Department setup.
4. User assignment.
5. KPI templates.
6. Apply template.
7. KPI creation wizard.
8. Target configuration.
9. KPI owner configuration.

The admin should be able to establish a functioning KPI system without touching raw DocType configuration.

---

# PHASE 7 — EMPLOYEE DATA ENTRY

Build:

* My Dashboard.
* KPI submission page.
* Dynamic KPI forms.
* Validation.
* Duplicate prevention.
* Draft support.
* Submission.
* Audit trail.

Optimize this flow for simplicity.

---

# PHASE 8 — ANALYTICS

Implement:

1. Current performance.
2. Target achievement.
3. Trend.
4. Growth.
5. Prediction.
6. Prediction-vs-actual.

Use real historical data only.

---

# PHASE 9 — AGENT / ALERT ENGINE

Implement:

* Target miss.
* Growth decline.
* Negative trend.
* Prediction miss.
* Repeated decline.
* Severity.
* Deduplication.
* Cooldown.

Make outputs explainable.

---

# PHASE 10 — NOTIFICATIONS

Implement ERPNext in-app notifications.

Ensure:

* Correct recipients.
* Department isolation.
* Critical alerts can reach CEO/Admin.
* No notification spam.

---

# PHASE 11 — DASHBOARDS

Build:

## Company Overview

and

## Reusable Department Dashboard

Then make department dashboards dynamically filter according to department.

Do NOT duplicate dashboard code for every department.

---

# PHASE 12 — LOGIN ROUTING

Implement:

CEO/Admin:

```text
Login
 ↓
Company Overview
```

Department User:

```text
Login
 ↓
Assigned Department Dashboard
```

Do not allow unauthorized department switching.

---

# PHASE 13 — REPORTING

Build:

* KPI Performance Report.
* Department Performance Report.
* Growth Report.
* Trend Report.
* Prediction Report.
* Prediction Accuracy Report.
* Alert Report.
* Historical KPI Report.

All reports must respect permissions.

---

# PHASE 14 — PERFORMANCE OPTIMIZATION

Review:

* Queries.
* Indexes.
* API response sizes.
* Dashboard load time.
* Background jobs.
* Historical data queries.
* Caching.

Do not optimize prematurely before correctness, but perform a dedicated optimization pass before delivery.

---

# PHASE 15 — TESTING

Test:

## Authentication

* CEO.
* Department Manager.
* Department User.
* Inactive user.

## Authorization

```text
Sales → Sales = Allowed
Sales → Production = Denied
Production → Sales = Denied
CEO → All = Allowed
```

## KPI

* Create.
* Edit.
* Deactivate.
* Invalid configuration.
* Duplicate code.

## Data

* Valid submission.
* Missing required field.
* Invalid data.
* Negative values.
* Duplicate period.
* Wrong department.
* Inactive KPI.
* Unauthorized KPI.

## Analytics

* Trend.
* Growth.
* Zero previous value.
* Prediction.
* Insufficient data.
* Prediction-vs-actual.

## Alerts

* Target miss.
* Negative trend.
* Growth decline.
* Prediction miss.
* Repeated decline.
* Duplicate prevention.

## Dashboards

* CEO.
* Sales.
* Production.
* QC.
* Safety.
* Procurement.
* R&D.
* Supply Chain.
* Empty states.
* Department isolation.

---

# PHASE 16 — RECIPE REGRESSION TEST

This is mandatory.

After KPI implementation verify:

1. Recipe dashboard works.
2. KPI dashboard works.
3. Recipe dashboard does not contain KPI UI.
4. KPI dashboard does not contain Recipe UI.
5. Recipe routes remain functional.
6. KPI routes remain functional.
7. Recipe menus remain functional.
8. KPI menus remain independent.
9. Recipe JS remains functional.
10. KPI JS remains functional.
11. Recipe CSS remains functional.
12. KPI CSS remains functional.
13. Recipe permissions remain unchanged.
14. KPI permissions remain independent.
15. Removing KPI functionality does not break Recipe.
16. Removing Recipe functionality does not break KPI core functionality.

---

# 62. NAMESPACE ISOLATION

Use unique names for:

* DocTypes.
* APIs.
* JS variables.
* CSS classes.
* DOM IDs.
* Routes.
* Workspaces.
* Pages.
* Components.

Avoid generic global identifiers.

Prefer:

```text
kpi-tracking-dashboard
kpi-tracking-chart-sales
kpi-tracking-kpi-card
kpi-tracking-data-entry
```

rather than generic identifiers such as:

```text
dashboard
container
data
main
chart
```

unless appropriately scoped.

---

# 63. FRONTEND ISOLATION

Never globally override ERPNext/Frappe styling.

Avoid global CSS such as:

```css
body {}
button {}
.card {}
```

unless absolutely necessary and proven safe.

Prefer scoped selectors such as:

```css
.kpi-tracking-app .kpi-card {}
```

All KPI JavaScript should also be appropriately namespaced.

---

# 64. ERROR HANDLING

Handle:

* Missing historical data.
* Insufficient prediction data.
* Zero previous value.
* Zero prediction value.
* Invalid KPI configuration.
* Inactive KPI.
* Inactive user.
* Missing department.
* Prediction failure.
* Invalid data.
* Unauthorized access.
* Duplicate submission.
* Background job failure.

Errors should be understandable.

Example:

```text
Insufficient data for prediction.
```

not:

```text
Prediction Error 500
```

where a user-friendly explanation is possible.

---

# 65. PREDICTION FAILURE SAFETY

If prediction fails:

* Log the failure.
* Preserve KPI data.
* Do not break dashboard.
* Mark prediction unavailable/failed.
* Show a useful status.
* Allow retry through background processing.

Prediction failure must never corrupt KPI data.

---

# 66. FUTURE RECIPE INTEGRATION

Do not implement Recipe integration now.

However, architect future integration conceptually as:

```text
Recipe Management
        ↓
Integration/API Layer
        ↓
KPI Tracking
        ↓
Analytics
```

Never make KPI business logic depend directly on Recipe implementation details.

---

# 67. CODE QUALITY

Code must be:

* Modular.
* Readable.
* Maintainable.
* Testable.
* Secure.
* Documented.
* Frappe-compatible.
* Version-aware.
* Scalable.

Separate major responsibilities:

```text
KPI Service
Analytics Service
Prediction Service
Alert Service
Notification Service
Permission Service
Dashboard Service
```

Do not create one giant Python or JavaScript file.

---

# 68. DOCUMENTATION

Create documentation covering:

1. Installation.
2. App structure.
3. DocTypes.
4. Roles.
5. Permissions.
6. APIs.
7. Dashboard architecture.
8. Setup Wizard.
9. KPI Template system.
10. KPI Input system.
11. Analytics logic.
12. Trend logic.
13. Growth logic.
14. Prediction logic.
15. Prediction accuracy.
16. Alert logic.
17. Notification system.
18. Background jobs.
19. Security model.
20. Recipe separation.
21. Future Recipe integration architecture.
22. Testing.
23. Troubleshooting.

---

# 69. FINAL ACCEPTANCE CRITERIA

The application is NOT complete until:

## Architecture

* KPI is standalone.
* Recipe remains separate.
* Independent namespace.
* Independent workspace.
* Independent routes.
* Independent frontend.
* Independent permissions.
* No unnecessary Recipe dependency.

## Admin Experience

* Setup Wizard works.
* Setup Center works.
* Departments can be created.
* Users can be assigned.
* KPI Templates work.
* KPI creation wizard works.
* Targets can be configured.
* KPI owners can be configured.

## Employee Experience

* Employee automatically reaches their department dashboard.
* Employee can easily enter KPI data.
* Dynamic KPI inputs work.
* Validation works.
* Duplicate submissions are prevented.
* Employees cannot access another department.

## Analytics

* Trend works.
* Growth works.
* Prediction works.
* Prediction-vs-actual works.
* Insufficient data is handled correctly.

## Agent

* Target miss works.
* Growth decline works.
* Negative trend works.
* Prediction miss works.
* Repeated decline works.
* Severity works.
* Deduplication works.

## Notifications

* In-app notifications work.
* Correct department receives alerts.
* Critical alerts can reach CEO/Admin.
* Duplicate notifications are prevented.

## Dashboard

* Company Overview works.
* Department Dashboard works.
* Department selector works.
* Login routing works.
* KPI cards work.
* Charts work.
* Target vs actual works.
* Trend works.
* Growth works.
* Prediction works.
* Alerts work.

## Security

* Backend authorization works.
* Department isolation works.
* Direct API manipulation cannot bypass permissions.
* Direct ID manipulation cannot expose another department.

## Recipe Regression

* Recipe continues to work.
* Recipe routes continue to work.
* Recipe permissions continue to work.
* Recipe frontend continues to work.
* Recipe dashboard remains independent.
* KPI dashboard remains independent.

---

# 70. FINAL ACCEPTANCE TEST — SALES USER

Create:

```text
User: Sales User
Department: Sales
Role: KPI Contributor
```

Login.

Expected:

```text
Sales Dashboard
```

Visible:

* Sales KPIs.
* Sales data.
* Sales trends.
* Sales growth.
* Sales predictions.
* Sales alerts.

Not visible:

* Production.
* QC.
* Safety.
* Procurement.
* R&D.
* Supply Chain.

Attempt direct API access to Production.

Expected:

```text
ACCESS DENIED
```

---

# 71. FINAL ACCEPTANCE TEST — CEO

Login as CEO.

Expected:

```text
Company Overview
```

CEO sees:

* Company trend.
* Company growth.
* Company prediction.
* Department summaries.
* Critical alerts.

CEO selects:

```text
Sales
```

Sales Dashboard opens.

CEO selects:

```text
Production
```

Production Dashboard opens.

Data must remain correctly isolated between views.

---

# 72. FINAL ACCEPTANCE TEST — ANALYTICS

Create:

```text
KPI: Daily Sales
Target: 100
```

Historical values:

```text
Day 1 = 80
Day 2 = 90
Day 3 = 95
Day 4 = 70
Day 5 = 60
```

Expected:

```text
Trend = Declining
```

Growth must be calculated correctly against the previous relevant period.

Prediction should only be generated when sufficient historical data exists.

The system should evaluate target miss and declining trend conditions.

---

# 73. FINAL ACCEPTANCE TEST — PREDICTION

Prediction:

```text
100
```

Actual:

```text
50
```

Expected:

```text
Variance = -50
Variance % = -50%
Status = Prediction Miss
```

If configured threshold is exceeded:

```text
Alert Generated
```

---

# 74. FINAL DELIVERY REPORT

At the end of implementation, provide:

## A. Architecture Summary

Explain what was created.

## B. Files Changed

Separate:

```text
NEW FILES
```

and

```text
MODIFIED FILES
```

Clearly identify any Recipe-related files.

## C. DocTypes

List every created DocType and important fields.

## D. Roles & Permissions

Explain:

* CEO/Admin.
* Department Manager.
* Department User.
* Backend restrictions.

## E. API

List important API methods.

## F. Admin UX

Explain:

* Setup Wizard.
* Setup Center.
* Department setup.
* KPI templates.
* KPI creation wizard.
* KPI configuration.

## G. Employee UX

Explain:

* Login routing.
* Department dashboard.
* KPI data entry.
* Submission flow.

## H. Analytics

Explain:

* Trend.
* Growth.
* Prediction.
* Prediction-vs-actual.

## I. Agent

Explain:

* Alert conditions.
* Severity.
* Deduplication.
* Cooldown.

## J. Dashboard

Explain:

* Company dashboard.
* Department dashboard.
* Department selector.
* KPI cards.
* Charts.

## K. Testing

Report:

* Tests performed.
* Results.
* Failed tests.
* Fixed issues.

## L. Recipe Isolation Verification

Explicitly confirm:

* Recipe dashboard is not embedded in KPI.
* KPI dashboard is not embedded in Recipe.
* Recipe routes preserved.
* KPI routes independent.
* Recipe permissions preserved.
* KPI permissions independent.
* Frontend assets isolated.
* API namespaces isolated.
* No unnecessary cross-app dependency exists.

---

# 75. FINAL PRIORITY ORDER

If features conflict, follow this exact priority:

### PRIORITY 1

Standalone architecture and complete Recipe separation.

### PRIORITY 2

Security and department-level data isolation.

### PRIORITY 3

Correct dashboard routing and isolation.

### PRIORITY 4

Simple administrator setup.

### PRIORITY 5

Simple employee data entry.

### PRIORITY 6

KPI configuration and KPI templates.

### PRIORITY 7

Trend and growth analytics.

### PRIORITY 8

Prediction and prediction-vs-actual.

### PRIORITY 9

Agentic alerts and notifications.

### PRIORITY 10

Performance and scalability.

### PRIORITY 11

Future integration readiness.

Never sacrifice security, usability, or application separation merely to implement a feature faster.

---

# 76. FINAL NON-NEGOTIABLE PRODUCT PRINCIPLE

The final ERPNext installation must behave as if two independent products exist:

```text
┌──────────────────────────────┐
│     RECIPE MANAGEMENT        │
│                              │
│ Recipe Workspace             │
│ Recipe Dashboard             │
│ Recipe Features              │
└──────────────────────────────┘


┌──────────────────────────────┐
│       KPI TRACKING           │
│                              │
│ Setup                        │
│ Departments                  │
│ KPI Templates                │
│ KPIs                         │
│ Data Entry                   │
│ Company Dashboard            │
│ Department Dashboards        │
│ Trend                        │
│ Growth                       │
│ Prediction                   │
│ Prediction Accuracy          │
│ Intelligent Analysis         │
│ Alerts                       │
│ Notifications                │
│ Reports                      │
└──────────────────────────────┘
```

They happen to exist inside the same ERPNext installation, but they are architecturally and experientially independent.

---

# 77. FINAL KPI PRODUCT FLOW

The complete intended flow is:

```text
                    COMPANY ADMIN
                         │
                         ▼
                 PERFORMANCE SETUP
                         │
             ┌───────────┼───────────┐
             ▼           ▼           ▼
        Departments    Users     KPI Templates
             │                       │
             │                       ▼
             │                  Select KPIs
             │                       │
             └──────────────┬────────┘
                            ▼
                      KPI Configuration
                            │
                  ┌─────────┼─────────┐
                  ▼         ▼         ▼
               Target    Frequency   Inputs
                  │         │         │
                  └─────────┼─────────┘
                            ▼
                       KPI Activated
                            │
                            ▼
                  ┌─────────────────┐
                  │ Department User │
                  └────────┬────────┘
                           ▼
                  Department Dashboard
                           │
                           ▼
                     Enter KPI Data
                           │
                           ▼
                      Server Validate
                           │
                           ▼
                         Save
                           │
                           ▼
                  Background Analytics
                           │
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
          Trend          Growth       Prediction
            │              │              │
            └──────────────┼──────────────┘
                           ▼
                  Prediction vs Actual
                           │
                           ▼
                   Intelligent Analysis
                           │
                           ▼
                         Alerts
                           │
                           ▼
                     Notifications
                           │
                           ▼
                 Company-Level Analytics
                           │
                           ▼
                    CEO Dashboard
                           │
                           ▼
                 Business Decisions
```

This flow should be the core product architecture.

---

# 78. FINAL PRODUCT GOAL

The final system must be:

> **A standalone, secure, scalable, role-based, department-aware KPI and company-performance analytics application for ERPNext/Frappe.**

It must provide:

```text
Easy Setup
      ↓
Departments
      ↓
Users
      ↓
KPI Templates
      ↓
KPI Configuration
      ↓
Simple Data Entry
      ↓
Historical Data
      ↓
Trend
      ↓
Growth
      ↓
Prediction
      ↓
Prediction Accuracy
      ↓
Intelligent Analysis
      ↓
Alerts
      ↓
Notifications
      ↓
Department Performance
      ↓
Company Performance
```

while maintaining:

```text
STRICT DEPARTMENT ISOLATION
+
STRICT BACKEND AUTHORIZATION
+
SIMPLE ADMIN EXPERIENCE
+
SIMPLE EMPLOYEE EXPERIENCE
+
COMPLETE RECIPE INDEPENDENCE
```

## ABSOLUTE FINAL RULE

**DO NOT MERGE THE RECIPE MANAGEMENT SYSTEM WITH THE KPI TRACKING SYSTEM.**

**DO NOT make the administrator manually configure complicated ERPNext internals when a friendly KPI interface can perform the configuration automatically.**

**DO NOT make ordinary employees navigate ERPNext complexity merely to enter KPI numbers.**

**BUILD THE KPI APPLICATION AS A REAL PRODUCT EXPERIENCE, WITH ERPNext/Frappe SERVING AS THE UNDERLYING PLATFORM.**

Before declaring the implementation complete, verify every acceptance criterion, test all security boundaries, test all KPI workflows, test dashboard routing, and perform complete regression testing against the existing Recipe Management System.


---

# PDF-BASED PRODUCTIX-STYLE KPI FLOW & FUNCTIONAL ENHANCEMENT ADDENDUM

## PURPOSE OF THIS ADDENDUM

This section is an **additional requirement layer** to the existing MASTER DEVELOPMENT PROMPT.

**IMPORTANT: DO NOT DELETE, REWRITE, WEAKEN, OR REPLACE ANYTHING ABOVE.**

All existing requirements, architecture rules, security rules, Recipe separation rules, analytics requirements, testing requirements, acceptance criteria, and implementation phases remain mandatory.

The purpose of this addendum is to make the KPI application behave like the KPI/performance product demonstrated in the supplied **Productix AI Co Pilot / Productix AI User Manual**, while providing a stronger ERPNext-native implementation and additional enhancements.

The reference product demonstrates a flow centered around:

```text
Admin
  ↓
Users / Departments / Units
  ↓
Variables & Indicators
  ↓
Operational Tables
  ↓
Formula Builder / Formula Library
  ↓
KPI Creation & Assignment
  ↓
Operational Data Entry
  ↓
KPI Dashboard
  ↓
Reports & Analytics
  ↓
AI Insights / Specialized AI Assistants
  ↓
Actionable Productivity Recommendations
```

The reference also shows that administrators can create multiple users, define organization-performance variables and indicators, create unit-level analysis tables, assign those tables to users/departments, define relationships between indicators such as:

```text
Sales - Expense = Profit
```

and create/assign KPIs to users or departments.

The implementation must reproduce that **functional flow and method**, but should improve it using ERPNext/Frappe-native data, stronger permissions, better UX, better validation, auditability, scalability, and more configurable analytics.

Reference source: the supplied Productix manual describes the admin capabilities on page 2, the Operational Tables model on pages 3-4, the Formula Builder and Formula Library on page 5, operational data entry and KPI creation on page 6, KPI dashboard behavior on page 7, user functionality on pages 8-9, reporting/AI analysis on page 10, and specialized AI assistants/context filtering on page 11. 

---

# 79. PRODUCTIX-STYLE FUNCTIONAL MODEL

The KPI application must not be designed as only:

```text
KPI Definition
      ↓
KPI Dashboard
```

It must support a configurable performance-data lifecycle:

```text
COMPANY
   ↓
ORGANIZATION STRUCTURE
   ↓
DEPARTMENTS
   ↓
USERS
   ↓
BUSINESS UNITS / OPERATIONAL UNITS
   ↓
CUSTOMERS / CLIENTS
   ↓
VARIABLES
   ↓
INDICATORS
   ↓
OPERATIONAL TABLES
   ↓
FORMULAS / RELATIONSHIPS
   ↓
KPI DEFINITIONS
   ↓
KPI ASSIGNMENTS
   ↓
TARGETS
   ↓
DATA ENTRY
   ↓
CALCULATED KPI VALUES
   ↓
KPI STATUS
   ↓
TREND
   ↓
GROWTH
   ↓
PREDICTION
   ↓
PREDICTION VS ACTUAL
   ↓
REPORTS
   ↓
INTELLIGENT ANALYSIS
   ↓
ALERTS
   ↓
AI RECOMMENDATIONS
   ↓
MANAGEMENT ACTION
```

This flow is additive to the existing architecture.

---

# 80. ADMIN CONTROL CENTER — PRODUCTIX-STYLE

The existing Performance Setup Center remains mandatory.

Enhance it with a more complete administrative control center:

```text
PERFORMANCE CONTROL CENTER

Company
Departments
Users
Business Units
Customers
Variables
Indicators
Operational Tables
Formula Builder
Formula Library
KPI Templates
KPI Definitions
KPI Assignments
Targets
Data Sources
Data Entry
KPI Dashboard
Reports
AI Insights
AI Assistants
Alerts
Notifications
Audit Log
Settings
```

The administrator should be able to understand the complete performance system from one central navigation experience.

Do not force the administrator to discover these capabilities through raw ERPNext DocTypes.

---

# 81. MULTIPLE USER ACCOUNT MANAGEMENT

The reference product explicitly provides an administrative capability to create multiple user accounts.

Implement a friendly:

## User Management

screen.

The administrator should be able to:

```text
Create User
Edit User
Activate User
Deactivate User
Assign Department
Assign Role
Assign Business Unit
Assign KPI Access
Assign Operational Table Access
Assign KPI Ownership
```

Example:

```text
+------------------------------------------------------+
| CREATE USER                                          |
+------------------------------------------------------+
| Full Name                                            |
| [ Ahmed Khan                                      ] |
|                                                      |
| Email                                                |
| [ ahmed@company.com                                ] |
|                                                      |
| Department                                           |
| [ Sales ▼                                          ] |
|                                                      |
| Role                                                 |
| [ KPI Contributor ▼                                ] |
|                                                      |
| Business Unit                                        |
| [ Lahore Unit ▼                                    ] |
|                                                      |
| [ Create User ]                                      |
+------------------------------------------------------+
```

The system must create/use ERPNext users where appropriate rather than creating a second unnecessary authentication system.

All existing security rules remain mandatory.

---

# 82. ORGANIZATIONAL VARIABLES AND INDICATORS

Add a configurable concept of:

## KPI Variables

and:

## KPI Indicators

The terms may be implemented as separate DocTypes or as a clean unified model if the architecture demonstrates that separation is unnecessary.

The important requirement is functional behavior.

Examples of variables:

```text
Sales
Revenue
Fuel Cost
Electricity Cost
Rent
HR Cost
Production
Capacity
Power Generated
Power Sold
Customer Count
Active Customers
Machine Hours
Downtime
```

Variables must be reusable.

A variable should not have to be recreated for every KPI.

---

# 83. VARIABLE REGISTRY

Create a:

## Variable Registry

that allows administrators to see available variables.

Example:

```text
VARIABLE REGISTRY

Variable                 Code              Type
------------------------------------------------
Revenue                  revenue           Currency
Fuel Cost                fuel_cost        Currency
Electricity Cost         electricity      Currency
Rent                     rent              Currency
Production               production       Number
Capacity                 capacity         Number
Customers                customers        Integer
Power Generated          power_generated  Number
Power Sold               power_sold       Number
```

Support:

```text
Create
Edit
Activate
Deactivate
Rename
Change Description
Configure Source
Configure Unit
Configure Aggregation
```

Do not permit renaming a variable in a way that silently breaks existing formulas.

Use stable internal codes/IDs and separate human-readable labels.

---

# 84. VARIABLE SOURCE MAPPING

A major enhancement for ERPNext is that variables should be capable of being sourced from ERPNext data.

A variable should support a source model such as:

```text
Source Type:

○ Manual Entry
○ ERPNext DocType
○ ERPNext Report
○ Formula
○ Imported Data
○ External Integration (future)
```

For ERPNext sources:

```text
Source DocType
Source Field
Company
Branch
Department
Customer
Date Field
Aggregation
Filter Conditions
```

Example:

```text
Variable:
Revenue

Source:
Sales Invoice

Field:
Grand Total

Aggregation:
SUM

Date Field:
Posting Date

Status:
Submitted
```

This lets the KPI platform use real ERPNext transactions instead of unnecessarily duplicating business data.

---

# 85. OPERATIONAL TABLES — REQUIRED PRODUCTIX-STYLE CONCEPT

Add a first-class:

# Operational Table

concept.

This is one of the key flows from the reference product.

An Operational Table represents a configurable operational analysis structure for a specific business unit, branch, site, location, customer group, or other organizational scope.

The system must support:

```text
Operational Table
    ↓
Unit / Branch
    ↓
Location
    ↓
Customers
    ↓
Selected Variables / Indicators
    ↓
Operational Data
```

The reference manual describes Operational Tables as a control center for configuring operational branches/business sites, including location type, customers, and selected data columns such as fuel, rent, electricity, capacity, and customer utilization.

---

# 86. OPERATIONAL TABLE REGISTRY

Create:

## Operational Table Registry

Example:

```text
OPERATIONAL TABLE REGISTRY

+----------------------------------------------------------+
| Lahore Unit                                              |
| Location: Lahore                                         |
| Type: Urban                                              |
| Customers: Jazz, Ufone                                  |
| Variables: Fuel, Electricity, Rent, Capacity, Customers |
| Status: Active                                           |
+----------------------------------------------------------+

+----------------------------------------------------------+
| Karachi Unit                                             |
| Location: Karachi                                        |
| Type: Urban                                              |
| Customers: Jazz                                          |
| Variables: Fuel, Electricity, Capacity                  |
| Status: Active                                           |
+----------------------------------------------------------+
```

Actions:

```text
Create Table
Edit
Duplicate
Deactivate
Assign
Configure Variables
Configure Customers
Open Data
View KPIs
View Reports
```

---

# 87. CREATE OPERATIONAL TABLE WIZARD

Create a friendly multi-step flow.

## Step 1 — Table Parameters

```text
Table Name
City / Location
Location Type
Date / Effective Date
Business Unit
Department
```

Location type should support configurable values such as:

```text
Urban
Rural
Industrial
Regional
Warehouse
Factory
Office
Other
```

Do not hard-code the final list into business logic.

---

# 88. OPERATIONAL TABLE CUSTOMER CONFIGURATION

The administrator must be able to attach one or more customers/clients to an Operational Table.

Example:

```text
CUSTOMERS

[ Jazz ▼ ] [ Add ]

[ Ufone ▼ ] [ Add ]

Selected Customers:

✓ Jazz
✓ Ufone
```

Customers should preferably come from ERPNext's Customer records.

Do not create duplicate Customer masters solely for the KPI application unless an explicit external-data use case requires it.

---

# 89. OPERATIONAL TABLE VARIABLE CONFIGURATION

The administrator must be able to select which variables/indicators apply to the unit.

Example:

```text
VARIABLES / INDICATORS

Linked to Unit

☑ Fuel Cost
☑ Electricity Cost
☑ HR Cost
☑ Rent
☑ Other Costs
☑ Total Capacity
☑ Power Produced
☑ Power Sold
```

A separate section may allow customer-specific variables:

```text
Linked to Customers

☑ Fuel Cost
☑ Electricity Cost
☑ HR Cost
☑ Rent
☑ Capacity
☑ Customer Utilization
```

This must be configurable per Operational Table.

---

# 90. VARIABLE LABEL / BUSINESS VOCABULARY CUSTOMIZATION

The reference product allows administrators to rename system variables to match organizational terminology.

Support:

```text
System Variable:
Fuel Cost

Display Label:
Diesel Expense
```

or:

```text
System Variable:
Customer Utilization

Display Label:
Client Utilization %
```

Important:

```text
Internal Code = stable
Display Label = configurable
```

Renaming must not break formulas, reports, historical records, or API references.

---

# 91. OPERATIONAL TABLE ASSIGNMENT

Operational Tables must be assignable to:

```text
Users
Departments
Managers
Business Units
Roles
```

Example:

```text
Operational Table:
Lahore Unit

Assigned Department:
Operations

Assigned Users:
Ahmed
Ali
Sara
```

The assignment must control:

```text
Who can see it
Who can enter data
Who can edit data
Who can approve/review data
Who can see analytics
```

All access must be enforced server-side.

---

# 92. OPERATIONAL DATA ENTRY

Add a dedicated:

# Operational Data Entry

experience.

This is different from KPI configuration.

Users should be able to enter operational records against the configured Operational Table.

Example:

```text
OPERATIONAL DATA ENTRY

Unit:
Lahore Unit

Date:
13/06/2026

Fuel Cost:
[ 5000 ]

Electricity Cost:
[ 3200 ]

HR Cost:
[ 4200 ]

Rent:
[ 2000 ]

Capacity:
[ 100 ]

Power Produced:
[ 80 ]

Power Sold:
[ 75 ]

Customers:
[ 20 ]

[ Save Record ]
```

The exact fields must be dynamically generated from the variables configured for that Operational Table.

---

# 93. IMMUTABLE COLUMN STRUCTURE FOR NORMAL USERS

Preserve the reference product's important UX behavior:

> Normal users may enter data but must not alter the configured column/variable structure.

Therefore:

```text
ADMIN
    ↓
Defines Variables / Columns
    ↓
Operational Table Configuration
    ↓
USER
    ↓
Can Enter Values
    ↓
Cannot Rename Columns
    ↓
Cannot Add Arbitrary Variables
    ↓
Cannot Change Data Model
```

If a user needs an additional variable, provide a controlled request/configuration flow or permission-controlled KPI configuration flow.

Do not allow arbitrary frontend schema mutation.

---

# 94. OPERATIONAL DATA RECORDS

Every operational record should preserve:

```text
Operational Table
Business Unit
Department
Customer (optional)
User
Date
Period
Variable Values
Calculated Values
Status
Created At
Modified At
```

Where applicable, support:

```text
Draft
Submitted
Reviewed
Approved
Rejected
```

This is an enhancement for enterprise use.

---

# 95. FORMULA BUILDER — REQUIRED

Add a first-class:

# Formula Builder

The Formula Builder must allow an administrator or authorized KPI manager to create formulas without writing code.

The reference flow is:

```text
Select Unit / Table
      ↓
Select Variables
      ↓
Select Formula Relationship / Template
      ↓
Select Result Variable
      ↓
Preview
      ↓
Save
```

---

# 96. FORMULA BUILDER — VARIABLE SELECTION

Example:

```text
SELECT VARIABLES

☑ Fuel Cost
☑ Electricity Cost
☑ Rent
☑ HR Cost
☐ Other Cost
```

Only variables available to the selected Operational Table should be offered by default.

---

# 97. FORMULA TEMPLATES

Support predefined templates such as:

```text
Addition
Subtraction
Multiplication
Division
Percentage
Ratio
Average
Minimum
Maximum
Growth
Variance
Target Achievement
Weighted Average
```

Examples:

```text
Fuel + Electricity + Rent
```

```text
Sales - Expense
```

```text
Actual / Target * 100
```

```text
Power Sold / Power Produced * 100
```

```text
Current - Previous
```

```text
(Current - Previous) / Previous * 100
```

---

# 98. FORMULA RELATIONSHIP ENGINE

Support formulas involving multiple variables.

Examples:

```text
Sales - Expense = Profit
```

```text
Profit / Sales * 100 = Profit Margin
```

```text
Power Sold / Power Generated * 100 = Energy Sales Efficiency
```

```text
Actual Production / Capacity * 100 = Capacity Utilization
```

```text
Total Operating Cost / Production = Cost Per Unit
```

The formula engine must be deterministic, validated, auditable, and safe.

Do not execute arbitrary unsafe Python or JavaScript supplied by a user.

---

# 99. FORMULA RESULT VARIABLE

The administrator must select where the calculated value belongs.

Example:

```text
Formula:

Sales - Expense

Result:
Profit
```

Or:

```text
Actual Production / Planned Production * 100

Result:
Production Efficiency %
```

The result may be:

```text
Existing Variable
Existing KPI Input
Calculated Variable
KPI Result
```

depending on the selected architecture.

---

# 100. LIVE FORMULA PREVIEW

Before saving, show:

```text
Formula Preview

Sales
  -
Expense
  =
Profit

Example:

1,000,000 - 700,000
=
300,000
```

For percentage:

```text
80 / 100 * 100
=
80%
```

The preview must clearly indicate whether the preview is based on:

```text
Sample Data
Actual Data
No Data
```

Never present sample output as actual business performance.

---

# 101. FORMULA VALIDATION

Reject:

```text
Invalid variable
Missing operand
Invalid operator
Division by zero
Circular dependency
Inactive variable
Missing result variable
Incompatible data types
Unauthorized variable
```

Detect circular formulas.

Example:

```text
A = B + C
B = A - C
```

must be rejected.

---

# 102. FORMULA LIBRARY

Add:

# Formula Library

This stores every saved formula.

Example:

```text
FORMULA LIBRARY

Name                    Formula
-----------------------------------------------------
Total Operating Cost    Fuel + Electricity + Rent
Gross Profit            Sales - COGS
Profit Margin           Profit / Sales * 100
Capacity Utilization    Production / Capacity * 100
Energy Efficiency       Power Sold / Power Produced * 100
```

Actions:

```text
View
Edit
Duplicate
Deactivate
Preview
Assign
Use in KPI
```

Formula versioning should be supported so changes do not silently rewrite historical results.

---

# 103. FORMULA VERSIONING

If a formula changes:

```text
Formula V1
Effective: Jan 2026

Formula V2
Effective: Jul 2026
```

Historical KPI results calculated under V1 must remain traceable.

Do not recalculate historical business results silently after formula changes.

---

# 104. KPI CREATION — PRODUCTIX-STYLE ENHANCEMENT

Keep the existing Create KPI Wizard.

Add support for creating a KPI directly from:

```text
Variable
Formula
Operational Table
KPI Template
Existing KPI
```

Flow:

```text
Choose Source
      ↓
Choose Variable / Formula
      ↓
Define KPI
      ↓
Choose Department / Unit
      ↓
Define Target
      ↓
Define Frequency
      ↓
Define Status Thresholds
      ↓
Define Owner
      ↓
Enable Analytics
      ↓
Enable Alerts
      ↓
Activate KPI
```

---

# 105. KPI CREATION FROM FORMULA

Example:

```text
CREATE KPI

Formula:
Capacity Utilization %

Formula:
Actual Production / Total Capacity * 100

KPI Name:
Capacity Utilization %

Department:
Production

Unit:
%

Frequency:
Monthly

Target:
85%

Warning:
75%

Critical:
65%
```

Then:

```text
[ Create KPI ]
```

The KPI must automatically reference the formula and its underlying variables.

---

# 106. KPI ASSIGNMENT — USER OR DEPARTMENT

The reference product supports assigning KPIs to users or departments.

The enhanced system must support:

```text
Assign KPI To:

○ Department
○ User
○ Role
○ Business Unit
○ Operational Table
```

Example:

```text
KPI:
Monthly Revenue

Department:
Sales

Owner:
Sales Manager

Data Entry:
Sales Contributors

Business Unit:
Lahore
```

A KPI may have a department-level owner and individual contributors.

---

# 107. USER-CREATED KPIs — PERMISSION CONTROL

The reference manual describes user-controlled KPI creation.

Preserve this capability, but implement it safely through permissions.

Support a configurable permission:

```text
Can Create KPI
```

Default:

```text
CEO/Admin = Yes
Department Manager = Configurable
KPI Manager = Yes
KPI Contributor = No
```

This preserves the existing security model while allowing organizations to grant authorized users the same flexibility demonstrated in the reference product.

Never allow ordinary users to create KPIs that expose another department's data.

---

# 108. KPI DASHBOARD — PRODUCTIX-STYLE STATUS MODEL

Enhance the existing KPI Dashboard with explicit KPI health states:

```text
ON TRACK
WARNING
CRITICAL
MISSING DATA
```

Top-level summary cards:

```text
Total KPIs
On Track
Warning
Critical
Missing Data
```

The dashboard should visually distinguish the states.

Do not rely only on colors; include text/status badges for accessibility.

---

# 109. KPI CARD — COMPLETE INFORMATION

Each KPI card should support:

```text
KPI Name
Current Value
Unit
Target
Achievement %
Growth %
Trend
Prediction
Prediction Accuracy
Status
Last Updated
Data Completeness
Owner
Department
Business Unit
```

Example:

```text
┌─────────────────────────────────────┐
│ Capacity Utilization       ON TRACK │
│                                     │
│ 82%                                 │
│ Target: 80%                         │
│ Achievement: 102.5%                 │
│ Growth: +4.2%                       │
│ Trend: Improving                    │
│ Prediction: 84%                     │
│                                     │
│ ████████████████░░                  │
│                                     │
│ Production / Lahore                 │
└─────────────────────────────────────┘
```

---

# 110. KPI DASHBOARD FILTERS

Provide filters similar to the reference product and enhance them.

Support:

```text
Department
Business Unit
Operational Table
Customer
KPI Category
KPI
User / Owner
Date Range
Period
Status
```

For CEO/Admin:

```text
All Departments
All Units
All KPIs
```

For department users:

```text
Only authorized scope
```

---

# 111. OPERATIONAL VS CUSTOMER-SPECIFIC DATA

The reference interface distinguishes overall unit operations from customer-specific operations.

Support both concepts.

Example:

```text
UNIT OPERATIONS

Date
Fuel Cost
Electricity Cost
HR Cost
Capacity
Production
Power Generated
Power Sold
```

and:

```text
CUSTOMER-SPECIFIC OPERATIONS

Date
Customer
Fuel Cost
Electricity Cost
HR Cost
Revenue
Capacity
Utilization
```

The user interface should clearly distinguish:

```text
Overall Unit Data
```

from:

```text
Customer-Specific Data
```

---

# 112. CUSTOMER-SPECIFIC KPI ANALYSIS

KPIs should optionally be scoped to a customer.

Examples:

```text
Revenue per Customer
Cost per Customer
Customer Profitability
Customer Utilization
Customer Retention
Customer SLA Achievement
```

A KPI can be:

```text
Company-level
Department-level
Unit-level
Customer-level
User-level
```

depending on configuration.

---

# 113. REPORTS & ANALYTICS — PRODUCTIX-STYLE

The existing Reporting phase remains mandatory.

Add a report flow where users can select:

```text
Operational Table / Business Unit
Date Record / Date Range
Customer
KPI
```

and receive a comprehensive performance summary.

Example:

```text
REPORT & ANALYTICS

Unit:
[ Lahore Unit ▼ ]

Date:
[ September 2026 ▼ ]

Customer:
[ All Customers ▼ ]

[ Generate Report ]
[ Export Excel ]
```

---

# 114. OPERATIONAL COST REPORT

Support automatic calculations for:

```text
Fuel Cost
Electricity Cost
HR Cost
Rent
Other Costs
Total Operating Cost
```

Example:

```text
TOTAL OPERATING COST

Fuel                  50,000
Electricity           30,000
HR                    40,000
Rent                  20,000
Other                 10,000
--------------------------------
Total                150,000
```

---

# 115. PRODUCTION / OPERATIONS TREND REPORT

Provide charts such as:

```text
Production by Date
Operating Cost by Date
Revenue by Date
Cost per Unit
Capacity Utilization
Power Generated vs Power Sold
```

Charts must use actual available records.

---

# 116. EXCEL EXPORT

Preserve the existing Excel reporting requirement and enhance it.

Allow users with permission to export:

```text
KPI Data
Operational Data
KPI Results
Trend Reports
Growth Reports
Prediction Reports
Alert Reports
Customer Analysis
Unit Performance
```

Exports must respect permissions and filters.

A Sales user must never export Production data simply by manipulating a frontend filter.

---

# 117. AI INSIGHTS — PRODUCTIX-STYLE

The existing AI/Agent layer remains mandatory.

Enhance it with a dedicated:

# AI Insights

experience.

For selected:

```text
Company
Department
Business Unit
Operational Table
Customer
Date Range
```

the AI should analyze the selected data and identify:

```text
Top inefficiencies
Cost abnormalities
Performance gaps
Trend changes
Target misses
Growth changes
Prediction deviations
Capacity problems
Customer issues
```

---

# 118. TOP THREE INEFFICIENCIES

The reference product describes automatically identifying the top sources of inefficiency with percentage impact.

Implement a structured result:

```text
TOP 3 INEFFICIENCIES

1. High Fuel Cost
   Estimated Impact: 18%

2. Low Capacity Utilization
   Estimated Impact: 14%

3. Electricity Cost Increase
   Estimated Impact: 9%
```

The AI must distinguish:

```text
Measured / calculated impact
```

from:

```text
AI interpretation
```

Do not fabricate percentages.

If impact cannot be calculated reliably, state:

```text
Impact could not be quantified from available data.
```

---

# 119. AI PREDICTIONS

The reference product includes high-level predictions such as expected production output for the next shift.

The existing Prediction Engine remains the authoritative numeric prediction engine.

AI may explain or contextualize the prediction, but it must not invent a conflicting number.

Example:

```text
Predicted Next Shift Production:
8,450 units

Confidence / Data Sufficiency:
Adequate

AI Interpretation:
Production is expected to remain below the target primarily due to recent capacity decline.
```

---

# 120. PRODUCTIVITY AI ASSISTANT

Add:

# Productivity AI Assistant

Purpose:

```text
Analyze overall branch/company performance
Compare costs and revenue
Identify lowest-performing units
Explain KPI deterioration
Recommend productivity improvements
```

Example questions:

```text
Which unit is performing worst?

Why did production decline?

Which department needs attention?

Which KPI has deteriorated the most?

What should management investigate first?
```

The assistant must respect the active context filters.

---

# 121. ENERGY AI SPECIALIST

Add:

# Energy AI Specialist

Purpose:

```text
Analyze fuel
Analyze electricity
Analyze power generated
Analyze power sold
Identify abnormal energy costs
Identify inefficient units
Recommend energy optimization
```

Example questions:

```text
Which unit has the highest energy cost?

Which units have abnormal fuel consumption?

What is the gap between power generated and power sold?

Where is energy efficiency declining?

What actions could reduce fuel consumption?
```

All numeric answers must be traceable to KPI/operational data.

---

# 122. HR AI SPECIALIST

Add:

# HR AI Specialist

Purpose:

```text
Analyze labor costs
Analyze payroll spending
Analyze personnel efficiency
Compare workforce costs across units/cities
Calculate personnel cost per customer/output
```

Example questions:

```text
Which location has the highest labor cost?

What is labor cost per unit of production?

Which department has rising overtime?

How is personnel cost changing?
```

Use authorized ERPNext HR data and/or KPI data.

---

# 123. PROCESS OPTIMIZATION AI SPECIALIST

Add:

# Process Optimization Assistant

Purpose:

```text
Audit operational workflow
Identify bottlenecks
Identify abnormal cost spikes
Identify idle capacity
Identify units approaching capacity limits
Recommend operational improvements
```

Example:

```text
Unit X is approaching maximum customer capacity.

Fuel cost has increased 21% over the previous period.

Idle capacity remains high.

Recommended actions:
1. Investigate fuel consumption.
2. Review scheduling.
3. Review customer allocation.
```

Recommendations must clearly distinguish observed facts from AI-generated suggestions.

---

# 124. AI CONTEXT FILTERS — REQUIRED

All AI assistants must provide a:

# Context Filters

panel.

Support:

```text
Region
Department
Business Unit
Operational Table
Customer
User
Start Date
End Date
Frequency
KPI
```

Example:

```text
CONTEXT FILTERS

Region:
[ Lahore ]

Unit:
[ Lahore Unit ]

Department:
[ Operations ]

Start Date:
[ 01/09/2026 ]

End Date:
[ 30/09/2026 ]

Customer:
[ All ]

[ Apply Filters ]
```

The AI must only use the authorized filtered data scope.

---

# 125. AI DATA BOUNDARY

Context filters are not merely UI filters.

The backend must construct the actual data scope before AI processing.

Required flow:

```text
Current User
    ↓
Permission Check
    ↓
Department Scope
    ↓
Business Unit Scope
    ↓
Context Filters
    ↓
Authorized KPI/Operational Dataset
    ↓
Analytics
    ↓
AI
```

Never send unauthorized data to the AI service and rely on the AI to "ignore it."

---

# 126. AI GUARDRAILS

Add configurable AI guardrails.

Administrators should be able to configure:

```text
Allowed Departments
Allowed KPIs
Allowed Data Sources
Maximum Date Range
Sensitive Fields
Allowed Actions
Response Detail
Financial Data Access
HR Data Access
Customer Data Access
```

Users may have narrower scopes.

The guardrail system must be enforced before AI context construction.

---

# 127. AI CHATBOT EXPERIENCE

Provide a chatbot interface within the KPI application.

Example:

```text
PRODUCTIVITY AI ASSISTANT

Context:
Lahore / Operations / Sep 2026

User:
Why is capacity utilization declining?

AI:
Capacity utilization declined from 91% to 82%.
The largest change occurred in Unit 04.
Production decreased while available capacity remained relatively stable.

Likely contributing factors:
1. Lower production volume.
2. Increased downtime.
3. Reduced customer utilization.

Would you like me to analyze Unit 04?
```

The AI must not claim certainty where the data only supports correlation.

---

# 128. QUICK AI QUESTIONS

Provide suggested questions based on the selected context.

Examples:

```text
Which unit has the highest capacity utilization?

Which KPI declined the most?

What is causing the largest cost increase?

Which customer is least profitable?

What should management investigate?

What is expected next period?
```

These should be dynamically generated where practical.

---

# 129. AI ACTIONS — CONTROLLED

The AI may suggest actions, but initially should not execute destructive or consequential ERP transactions automatically.

Support:

```text
Analyze
Explain
Recommend
Create Alert
Prepare Report
Prepare Task Recommendation
```

Actual ERP transaction changes should require explicit user confirmation and appropriate permissions.

---

# 130. KPI → AI PRODUCTIVITY LOOP

The complete enhanced flow should be:

```text
KPI Data
   ↓
KPI Calculation
   ↓
Target Comparison
   ↓
Trend
   ↓
Growth
   ↓
Prediction
   ↓
Prediction Accuracy
   ↓
Issue Detection
   ↓
AI Root-Cause Analysis
   ↓
Productivity Recommendation
   ↓
Manager Review
   ↓
Action
   ↓
Future KPI Measurement
```

This creates a closed-loop performance-management system.

---

# 131. ADMIN CONFIGURATION OF VARIABLES, FORMULAS, AND KPIs

The administrator must be able to build the system progressively:

```text
1. Create Department
        ↓
2. Create User
        ↓
3. Create Business Unit
        ↓
4. Configure Customers
        ↓
5. Configure Variables
        ↓
6. Create Operational Table
        ↓
7. Select Variables
        ↓
8. Build Formula
        ↓
9. Save Formula
        ↓
10. Create KPI
        ↓
11. Configure Target
        ↓
12. Configure Frequency
        ↓
13. Assign KPI
        ↓
14. Activate
```

This must be available through friendly UI.

---

# 132. PRODUCTIX-STYLE COMPLETE ADMIN FLOW

The preferred administrative workflow is:

```text
ADMIN LOGIN
    ↓
COMPANY OVERVIEW / PERFORMANCE CONTROL CENTER
    ↓
SETUP
    ↓
DEPARTMENTS
    ↓
USERS
    ↓
BUSINESS UNITS
    ↓
CUSTOMERS
    ↓
VARIABLES / INDICATORS
    ↓
OPERATIONAL TABLES
    ↓
FORMULA BUILDER
    ↓
FORMULA LIBRARY
    ↓
KPI TEMPLATES
    ↓
CREATE / SELECT KPIs
    ↓
TARGETS
    ↓
FREQUENCY
    ↓
INPUTS
    ↓
OWNERSHIP
    ↓
ALERTS
    ↓
PREDICTION
    ↓
ACTIVATE
    ↓
DASHBOARD
```

The administrator must be able to return to any stage and modify configuration through the appropriate controlled interface.

---

# 133. PRODUCTIX-STYLE COMPLETE USER FLOW

The preferred user workflow is:

```text
USER LOGIN
    ↓
DETERMINE DEPARTMENT
    ↓
DEPARTMENT DASHBOARD
    ↓
SEE ASSIGNED KPIs
    ↓
SEE CURRENT PERFORMANCE
    ↓
SEE TARGET
    ↓
SEE TREND
    ↓
SEE GROWTH
    ↓
SEE PREDICTION
    ↓
ENTER OPERATIONAL DATA
    ↓
SAVE / SUBMIT
    ↓
SERVER VALIDATION
    ↓
CALCULATION
    ↓
BACKGROUND ANALYTICS
    ↓
UPDATED KPI DASHBOARD
    ↓
ALERTS / INSIGHTS
```

Users should never have to understand the underlying formula engine unless they have permission to configure KPIs.

---

# 134. PRODUCTIX-STYLE DATA FLOW

The technical data flow should support:

```text
ERPNext Master Data
       +
ERPNext Transactions
       +
Manual Operational Data
       ↓
Variables
       ↓
Operational Tables
       ↓
Formula Engine
       ↓
KPI Engine
       ↓
KPI Results
       ↓
Analytics Engine
       ├── Trend
       ├── Growth
       ├── Prediction
       └── Prediction Accuracy
       ↓
Agent / Intelligence Layer
       ├── Inefficiency Detection
       ├── Alert Detection
       ├── AI Analysis
       └── Recommendations
       ↓
Dashboards / Reports / Notifications
```

---

# 135. PRODUCTIX-STYLE DEPARTMENT EXAMPLE

For Sales:

```text
Sales Department
    ↓
Operational Table
    ↓
Variables:
Revenue
Orders
Customers
Leads
Conversions
Expenses
    ↓
Formulas:
Revenue - Expense = Profit
Conversions / Leads * 100 = Conversion Rate
    ↓
KPIs:
Revenue
Sales Growth
Conversion Rate
Profit Margin
Customer Retention
    ↓
Dashboard
    ↓
AI Productivity Analysis
```

For Production:

```text
Production Department
    ↓
Variables:
Planned Production
Actual Production
Capacity
Downtime
Rejected Units
Fuel
Electricity
    ↓
Formulas:
Actual / Planned * 100
Production / Capacity * 100
Rejected / Production * 100
    ↓
KPIs:
Production Efficiency
Capacity Utilization
Downtime
Reject Rate
Energy Cost per Unit
```

For Energy:

```text
Variables:
Fuel Cost
Electricity Cost
Power Generated
Power Sold
    ↓
Formulas:
Power Sold / Power Generated * 100
Fuel Cost / Production
Electricity Cost / Production
    ↓
KPIs:
Energy Efficiency
Fuel Cost per Unit
Power Sales Efficiency
```

For HR:

```text
Variables:
Payroll
Employees
Overtime
Production / Revenue
Customers
    ↓
Formulas:
Payroll / Revenue
Payroll / Customer
Payroll / Production
    ↓
KPIs:
Labor Cost Ratio
Personnel Cost per Customer
Revenue per Employee
```

---

# 136. ERPNext-NATIVE DATA INTEGRATION RULE

The Productix-style flow must not cause unnecessary duplication of ERPNext master/transaction data.

Prefer:

```text
ERPNext Customer
ERPNext Employee
ERPNext Department
ERPNext Company
ERPNext Branch
ERPNext Sales Invoice
ERPNext Purchase Invoice
ERPNext GL Entry
ERPNext Attendance
ERPNext Payroll
ERPNext Work Order
ERPNext Job Card
ERPNext Stock Entry
```

as sources where appropriate.

The KPI layer should provide:

```text
Variable Mapping
Formula Mapping
KPI Mapping
```

on top of those sources.

Manual Operational Tables should be used where the required data is not already available in ERPNext.

---

# 137. KPI SOURCE TRANSPARENCY

Every KPI should make its data origin discoverable.

Example:

```text
KPI:
Gross Profit

Source:
ERPNext Sales Invoice
ERPNext General Ledger

Formula:
Revenue - COGS

Period:
September 2026

Last Calculated:
14 Sep 2026 06:00
```

Users with appropriate permissions should be able to drill down from KPI → formula → variables → source data.

---

# 138. KPI DRILL-DOWN

Add drill-down behavior.

Example:

```text
Gross Profit
PKR 920,000
```

Click:

```text
Revenue
PKR 4,800,000
```

Click:

```text
Sales Invoices
```

or:

```text
COGS
PKR 3,880,000
```

Click:

```text
Relevant ERPNext source records
```

Every drill-down must enforce permissions.

---

# 139. KPI DATA COMPLETENESS

The reference product has a "missing data" concept.

Enhance this with:

```text
Expected Records
Received Records
Completion %
Missing Periods
Last Submission
```

Example:

```text
September Data

Expected: 30 daily records
Received: 27
Completion: 90%

Missing:
Sep 08
Sep 17
Sep 23
```

This should contribute to:

```text
Missing Data
```

dashboard status.

---

# 140. KPI STATUS ENGINE

Status should be configurable per KPI.

Support:

```text
Higher is Better
Lower is Better
Target Range
Exact Target
Threshold Based
```

Examples:

Higher is better:

```text
Revenue
Production
Capacity Utilization
```

Lower is better:

```text
Defect Rate
Downtime
Cost per Unit
```

Range:

```text
Temperature
Safety Incidents
Quality Score
```

The status engine must understand the direction of the KPI.

---

# 141. KPI WEIGHTING

Preserve the existing weighted company aggregation requirement.

Allow:

```text
KPI Weight
Department Weight
Category Weight
```

Example:

```text
Sales              25%
Production         25%
Quality            15%
Safety             15%
Procurement        10%
Supply Chain       10%
```

Company performance must be calculated transparently.

---

# 142. COMPANY / UNIT / CUSTOMER HIERARCHY

Support the hierarchy:

```text
Company
  ↓
Region
  ↓
Department
  ↓
Business Unit / Branch
  ↓
Operational Table
  ↓
Customer
  ↓
KPI
```

Not every organization must use every level.

The system should support optional hierarchy levels.

---

# 143. REUSABLE COMPONENT ARCHITECTURE

Do not create separate implementations for:

```text
Sales Dashboard
Production Dashboard
QC Dashboard
Safety Dashboard
Procurement Dashboard
R&D Dashboard
Supply Chain Dashboard
```

Instead create reusable components:

```text
DepartmentDashboard
KPIGrid
KPICard
TrendChart
GrowthIndicator
PredictionCard
AlertList
OperationalTableView
CustomerPerformanceView
FormulaPreview
AIInsightPanel
```

Then configure them based on scope.

---

# 144. PRODUCTIX-STYLE PAGE STRUCTURE

The KPI application may use the following navigation:

```text
KPI TRACKING

CO-PILOT / AI
├── Home
├── Productivity Assistant
├── Energy Assistant
├── HR Assistant
├── Process Assistant

PERFORMANCE
├── Company Overview
├── Department Dashboards
├── KPI Dashboard
├── Operational Tables
├── Operational Data

CONFIGURATION
├── Departments
├── Users
├── Business Units
├── Customers
├── Variables
├── Formula Builder
├── Formula Library
├── KPI Templates
├── KPIs
├── KPI Assignments

ANALYTICS
├── Reports
├── Trends
├── Growth
├── Predictions
├── Prediction Accuracy
├── AI Insights

CONTROL
├── Alerts
├── Notifications
├── Setup Center
├── Audit Log
└── Settings
```

Only show authorized items.

---

# 145. ADMIN QUICK ACTIONS

The Performance Control Center should provide shortcuts:

```text
+ Create Department
+ Create User
+ Create Business Unit
+ Create Operational Table
+ Create Variable
+ Create Formula
+ Create KPI
+ Apply KPI Template
+ Enter Test Data
+ View Dashboard
+ Run Report
```

This reduces navigation friction.

---

# 146. PRODUCTIX-STYLE "NO-CODE" CONFIGURATION PRINCIPLE

The administrator should be able to configure most of the KPI system without programming.

No-code/admin UI should cover:

```text
Departments
Users
Business Units
Operational Tables
Variables
Indicators
Formula Relationships
KPIs
Targets
Frequency
Inputs
Owners
Alerts
AI Context Filters
```

Developer/code intervention should primarily be required for:

```text
New core data source adapters
New advanced calculation engines
New prediction algorithms
New external integrations
New security capabilities
```

---

# 147. FORMULA BUILDER SAFETY

Never let the "no-code" formula builder become an arbitrary code execution system.

Allowed operations must come from a safe expression grammar.

Support:

```text
+
-
*
/
%
()
MIN
MAX
AVG
SUM
COUNT
IF
ABS
ROUND
```

only where explicitly implemented and validated.

No:

```text
eval()
exec()
arbitrary Python
arbitrary JavaScript
SQL entered by normal KPI users
```

---

# 148. AI INSIGHT TRACEABILITY

Every AI insight should have an expandable:

```text
Why am I seeing this?
```

section.

Example:

```text
Insight:
Fuel cost increased significantly.

Evidence:
Fuel Cost:
Aug = 42,000
Sep = 55,000

Change:
+30.9%

Affected Units:
Lahore Unit 04
Lahore Unit 07
```

Then:

```text
AI Interpretation:
The increase appears concentrated in two units.
```

This makes AI more trustworthy.

---

# 149. AI FACT VS RECOMMENDATION

AI output should separate:

```text
OBSERVED DATA
```

from:

```text
ANALYSIS
```

from:

```text
RECOMMENDATION
```

Example:

```text
OBSERVED
Fuel cost increased 18%.

ANALYSIS
The increase is concentrated in Unit 04.

RECOMMENDATION
Review fuel consumption and production volume for Unit 04.
```

Do not present recommendations as verified facts.

---

# 150. PRODUCTIVITY ACTION CENTER

Add an optional:

# Action Center

to improve on the reference product.

It should aggregate:

```text
Critical KPI
Target Miss
Repeated Decline
Prediction Miss
High Cost
Low Capacity
Missing Data
AI Recommendation
```

Example:

```text
ACTION CENTER

3 items require attention

CRITICAL
Production Efficiency — Unit 04

WARNING
Fuel Cost — Unit 07

MISSING DATA
Sales — Lahore — Sep 12

[Open Issue]
```

This is an enhancement, not a replacement for the existing Alerts system.

---

# 151. MANAGEMENT DECISION FLOW

The complete management experience should become:

```text
Dashboard
   ↓
See problem
   ↓
Open KPI
   ↓
Drill down
   ↓
See variables
   ↓
See formula
   ↓
See source records
   ↓
See trend
   ↓
See growth
   ↓
See prediction
   ↓
Ask AI
   ↓
Receive evidence-backed analysis
   ↓
Review recommendation
   ↓
Take action
```

---

# 152. PRODUCTIX-STYLE ACCEPTANCE TEST — ADMIN

Create:

```text
Company: Test Company
Department: Operations
Business Unit: Lahore Unit
Customer: Test Customer
User: Test Operator
```

Create variables:

```text
Fuel Cost
Electricity Cost
HR Cost
Revenue
Expense
Production
Capacity
Power Generated
Power Sold
```

Create formula:

```text
Revenue - Expense = Profit
```

Create formula:

```text
Production / Capacity * 100 = Capacity Utilization
```

Create KPI:

```text
Profit
Capacity Utilization
Energy Efficiency
```

Assign KPIs to Operations.

Expected:

```text
KPI dashboard displays all assigned KPIs.
```

---

# 153. PRODUCTIX-STYLE ACCEPTANCE TEST — OPERATIONAL TABLE

Create:

```text
Operational Table:
Lahore Unit

Location Type:
Urban

Customers:
Test Customer A
Test Customer B
```

Select:

```text
Fuel
Electricity
HR Cost
Capacity
Production
```

Expected:

```text
Operational Data Entry
```

automatically displays those configured fields.

User must be unable to rename them.

---

# 154. PRODUCTIX-STYLE ACCEPTANCE TEST — FORMULA BUILDER

Create:

```text
Fuel Cost = 50,000
Electricity = 30,000
Rent = 20,000
```

Build:

```text
Fuel + Electricity + Rent
```

Result:

```text
Total Operating Cost = 100,000
```

Save formula.

Verify Formula Library contains the formula.

Modify the formula.

Verify a new version is created and historical calculations remain traceable.

---

# 155. PRODUCTIX-STYLE ACCEPTANCE TEST — CUSTOMER DATA

Create two customers.

Enter customer-specific operational data.

Verify:

```text
Customer A data
```

cannot be incorrectly displayed as:

```text
Customer B data
```

and that customer filtering respects user permissions.

---

# 156. PRODUCTIX-STYLE ACCEPTANCE TEST — KPI CREATION

Create KPI using a saved formula.

Verify:

```text
Formula selected
KPI created
Target configured
Frequency configured
Owner configured
Department configured
KPI activated
Dashboard card created
```

---

# 157. PRODUCTIX-STYLE ACCEPTANCE TEST — USER DATA ENTRY

Login as department user.

Expected:

```text
Assigned Department Dashboard
```

Then:

```text
Operational Data
```

User can:

```text
Enter values
Save
Submit
View resulting KPI
```

User cannot:

```text
Rename variables
Change formula
Change KPI target
Access another department
```

unless explicitly granted permission.

---

# 158. PRODUCTIX-STYLE ACCEPTANCE TEST — KPI DASHBOARD

Verify top-level cards:

```text
Total
On Track
Warning
Critical
Missing Data
```

Verify KPI cards display:

```text
Current
Target
Achievement
Growth
Trend
Prediction
Status
```

Verify filters:

```text
Department
Unit
Customer
KPI
Date
Status
```

---

# 159. PRODUCTIX-STYLE ACCEPTANCE TEST — AI

Select:

```text
Region = Lahore
Unit = Lahore Unit
Date = September 2026
```

Ask:

```text
Which unit has the highest energy cost?
```

Verify the AI only sees authorized data.

Ask:

```text
Why did energy cost increase?
```

Verify response separates:

```text
Observed Data
Analysis
Recommendation
```

If insufficient data exists, AI must say so.

---

# 160. PRODUCTIX-STYLE ACCEPTANCE TEST — AI SPECIALISTS

Test each assistant:

```text
Productivity Assistant
Energy Assistant
HR Assistant
Process Optimization Assistant
```

Verify each has a distinct analytical purpose.

Verify all four respect:

```text
User Permissions
Department Scope
Context Filters
Date Range
Business Unit Scope
```

---

# 161. ENHANCED FINAL PRODUCT FLOW

The final product should combine the original MASTER DEVELOPMENT PROMPT and the Productix-style flow as:

```text
                         COMPANY ADMIN
                              │
                              ▼
                    PERFORMANCE CONTROL CENTER
                              │
        ┌─────────────────────┼──────────────────────┐
        ▼                     ▼                      ▼
   Departments              Users              Business Units
        │                     │                      │
        └─────────────────────┼──────────────────────┘
                              ▼
                       Customers / Units
                              │
                              ▼
                    Variables / Indicators
                              │
                              ▼
                    Operational Tables
                              │
                   ┌──────────┴──────────┐
                   ▼                     ▼
              Unit Variables      Customer Variables
                   │                     │
                   └──────────┬──────────┘
                              ▼
                       Formula Builder
                              │
                              ▼
                       Formula Library
                              │
                              ▼
                       KPI Templates
                              │
                              ▼
                       KPI Configuration
                              │
             ┌────────────────┼────────────────┐
             ▼                ▼                ▼
          Targets         Frequency          Inputs
             │                │                │
             └────────────────┼────────────────┘
                              ▼
                       KPI Assignment
                              │
                              ▼
                        KPI Activated
                              │
                              ▼
                     Department User
                              │
              ┌───────────────┼────────────────┐
              ▼               ▼                ▼
         Data Entry      KPI Dashboard      Reports
              │               │                │
              ▼               ▼                │
         Validation       Current Value       │
              │            Target              │
              ▼            Trend               │
            Save           Growth              │
              │            Prediction          │
              ▼            Status              │
      Background Jobs       Alerts              │
              │               │                │
              └───────────────┼────────────────┘
                              ▼
                     Intelligent Analysis
                              │
               ┌──────────────┼───────────────┐
               ▼              ▼               ▼
         Productivity       Energy           HR
            AI               AI              AI
               │              │               │
               └──────────────┼───────────────┘
                              ▼
                     Process Optimization AI
                              │
                              ▼
                       Recommendations
                              │
                              ▼
                         Action Center
                              │
                              ▼
                       Management Action
                              │
                              ▼
                       Future KPI Results
```

---

# 162. ENHANCED PRODUCT PRINCIPLE

The final system should feel like:

> **Productix-style KPI / Performance Management + ERPNext-native business data + stronger enterprise controls + explainable analytics + AI specialists.**

Do NOT copy the reference product's visual design blindly.

Copy and implement its:

```text
Functional flow
Configuration method
Operational-table concept
Variable/indicator concept
Formula-building concept
Formula-library concept
KPI creation method
KPI assignment method
Simple data-entry method
KPI status dashboard method
Report/analytics flow
AI insight flow
Specialist assistant concept
Context-filter concept
```

Then improve:

```text
ERPNext integration
Security
Auditability
Formula safety
Versioning
Data lineage
Drill-down
Data completeness
AI guardrails
Prediction accuracy
Action Center
Responsive UX
Performance
Scalability
```

---

# 163. IMPORTANT: DO NOT CREATE A CLONE OF THE REFERENCE PRODUCT

The objective is to reproduce the **feature behavior, flow, information architecture, and configuration method** demonstrated by the reference material.

Do not copy:

```text
Branding
Logo
Proprietary visual assets
Exact proprietary wording
Exact visual styling
```

Create an original ERPNext/Frappe product experience.

The implementation should be inspired by the demonstrated functional workflow, not a pixel-for-pixel or branding clone.

---

# 164. FINAL ENHANCED ACCEPTANCE CRITERIA

The application is not complete unless the existing acceptance criteria PLUS the following are satisfied:

## Organization

- Multiple users can be managed.
- Users can be assigned to departments.
- Business units can be configured.
- Customers can be attached to units.
- Department isolation works.

## Variables

- Variables can be created.
- Variables can be renamed at the display-label level.
- Internal identifiers remain stable.
- Variables can map to ERPNext data.
- Variables can be manually entered where required.

## Operational Tables

- Operational Tables can be created.
- Unit/location configuration works.
- Customers can be attached.
- Variables can be selected.
- Tables can be assigned.
- User data entry follows the configured structure.
- Normal users cannot change the column structure.

## Formulas

- Formula Builder works.
- Variables can be selected.
- Formula templates work.
- Relationships such as Sales - Expense = Profit work.
- Formula preview works.
- Formula validation works.
- Circular formulas are rejected.
- Formula Library works.
- Formula versioning works.
- Historical results remain traceable.

## KPIs

- KPIs can be created from templates.
- KPIs can be created from formulas.
- KPIs can be assigned to departments.
- KPIs can be assigned to users where permitted.
- KPI targets work.
- KPI frequencies work.
- KPI inputs are dynamic.
- KPI statuses work.
- Missing-data status works.

## Data Entry

- Operational data entry works.
- KPI data entry works.
- Customer-specific data works.
- Server-side validation works.
- Duplicate prevention works.
- Audit trail works.
- User cannot spoof department/user identity.

## Dashboard

- Company dashboard works.
- Department dashboard works.
- Unit filtering works.
- Customer filtering works.
- KPI cards work.
- Status summaries work.
- Trend works.
- Growth works.
- Prediction works.
- Prediction-vs-actual works.
- Drill-down works.

## Reports

- Operational reports work.
- KPI reports work.
- Cost reports work.
- Trend reports work.
- Growth reports work.
- Prediction reports work.
- Customer reports work.
- Excel export works.
- Permissions are respected.

## AI

- Productivity Assistant works.
- Energy Assistant works.
- HR Assistant works.
- Process Optimization Assistant works.
- Context Filters work.
- AI guardrails work.
- AI only receives authorized data.
- AI distinguishes fact, analysis, and recommendation.
- AI does not fabricate unavailable metrics.
- AI prediction explanations remain consistent with the Prediction Engine.

## Security

- Frontend restrictions are not treated as security.
- Backend authorization works.
- Department isolation works.
- Unit isolation works where configured.
- Customer data isolation works where configured.
- AI data boundaries are enforced server-side.
- Direct API manipulation cannot bypass permissions.

## Recipe Independence

All original Recipe separation and regression requirements remain mandatory.

---

# 165. FINAL MASTER FLOW — AUTHORITATIVE

When there is a question about how the overall KPI product should behave, use this flow as the combined product model:

```text
ERPNext Installation
        │
        ├────────────── Recipe Management
        │                 (COMPLETELY SEPARATE)
        │
        └────────────── KPI Tracking
                          │
                          ▼
                 Performance Setup
                          │
          ┌───────────────┼────────────────┐
          ▼               ▼                ▼
     Departments        Users        Business Units
          │               │                │
          └───────────────┼────────────────┘
                          ▼
                     Customers
                          │
                          ▼
              Variables / Indicators
                          │
                          ▼
                 Operational Tables
                          │
                          ▼
                 Formula Builder
                          │
                          ▼
                  Formula Library
                          │
                          ▼
                  KPI Templates
                          │
                          ▼
                 KPI Configuration
                          │
           ┌──────────────┼──────────────┐
           ▼              ▼              ▼
        Targets       Frequency        Inputs
           │              │              │
           └──────────────┼──────────────┘
                          ▼
                   KPI Assignment
                          │
                          ▼
                    KPI Activated
                          │
                          ▼
                  Department User
                          │
                 ┌────────┴────────┐
                 ▼                 ▼
             Data Entry       KPI Dashboard
                 │                 │
                 ▼                 ├── Current
              Validate             ├── Target
                 │                 ├── Trend
                 ▼                 ├── Growth
               Save               ├── Prediction
                 │                 ├── Status
                 ▼                 └── Alerts
          Background Jobs
                 │
        ┌────────┼─────────┐
        ▼        ▼         ▼
      Trend   Growth   Prediction
        │        │         │
        └────────┼─────────┘
                 ▼
        Prediction vs Actual
                 │
                 ▼
       Intelligent Analysis
                 │
      ┌──────────┼───────────┐
      ▼          ▼           ▼
 Productivity  Energy       HR
      AI          AI          AI
      └──────────┼───────────┘
                 ▼
        Process Optimization AI
                 │
                 ▼
        Context-Filtered Analysis
                 │
                 ▼
         Recommendations
                 │
                 ▼
           Action Center
                 │
                 ▼
        Management Decision
                 │
                 ▼
        Company Performance
```

This combined flow is now part of the implementation requirements.

---

# 166. IMPLEMENTATION INSTRUCTION TO THE AI DEVELOPER

When implementing this project:

1. Read the entire original MASTER DEVELOPMENT PROMPT.
2. Read this entire Productix-style addendum.
3. Treat both as mandatory requirements.
4. Do not remove earlier requirements.
5. Do not replace earlier security rules with weaker Productix-style behavior.
6. Where the reference product and the original prompt overlap, implement the richer version.
7. Where the reference product introduces a new capability, add it.
8. Where the reference product's behavior conflicts with security, use permission-controlled implementation rather than weakening security.
9. Preserve Recipe independence.
10. Use ERPNext/Frappe as the underlying platform.
11. Build a modern dedicated KPI product experience above ERPNext.
12. Prefer ERPNext source data over unnecessary duplicate data.
13. Implement the Variable → Operational Table → Formula → KPI → Dashboard → AI flow.
14. Implement Formula Builder and Formula Library.
15. Implement unit-level and customer-level operational analysis.
16. Implement the four specialized AI assistants.
17. Implement context filters and server-side AI data boundaries.
18. Implement explainable AI outputs.
19. Implement drill-down and data lineage.
20. Test every new workflow before declaring completion.

**Do not declare the project complete merely because KPI cards appear on a dashboard.**

The complete product must support the full configuration, operational-data, formula, KPI, analytics, reporting, AI, alert, and decision-support lifecycle described above.

---

# 167. FINAL PRODUCT DEFINITION

The final application is:

> **A standalone ERPNext/Frappe KPI and Company Performance Management Platform that combines configurable departments, users, business units, operational tables, variables, indicators, formulas, KPI templates, KPI assignment, simple operational data entry, KPI dashboards, reports, trend/growth/prediction analytics, prediction accuracy, intelligent analysis, alerts, notifications, and context-aware specialized AI assistants — while remaining completely independent from the existing Recipe Management application.**

The reference Productix-style flow is a required functional inspiration and enhancement layer.

The original MASTER DEVELOPMENT PROMPT remains fully active.

**Nothing in this addendum removes or relaxes an earlier requirement.**

---
