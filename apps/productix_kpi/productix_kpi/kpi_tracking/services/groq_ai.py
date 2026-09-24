import frappe
import json
import os
import requests

CORE_DIRECTIVE = (
    "You are the Productix KPI & Operations Virtual Assistant — an executive-grade, highly structured operational advisor embedded in the enterprise ERP.\n\n"
    "CRITICAL CONVERSATIONAL & FORMATTING RULES:\n"
    "1. STRUCTURE & CONCISENESS (NEVER CONGESTED OR VERBOSE):\n"
    "   - Keep answers structured, crisp, and direct to the point. Avoid dense walls of text or conversational fluff.\n"
    "   - Use clean Markdown with double line breaks between points and sections.\n"
    "   - Present recommendations and insights as clean bullet points with bold highlights.\n\n"
    "2. STRICT DATA ACCURACY (NO HALLUCINATIONS):\n"
    "   - Ground all statements in the ENTERPRISE OPERATIONAL CONTEXT provided below.\n"
    "   - If departments have missing data entries, accurately list each department, the exact number of missing metrics, and assigned employees.\n"
    "   - Never claim all submissions are complete if there are departments with missing entries > 0.\n\n"
    "3. ACTIONABLE GUIDANCE:\n"
    "   - For operational improvement questions, provide 3 to 4 high-impact, prioritized, department-specific action steps based on actual KPI variances.\n\n"
    "4. GREETINGS & CASUAL INPUTS:\n"
    "   - For simple greetings ('hi', 'hello', 'hey'), respond concisely: 'Hello! I am your KPI & Operations Assistant. How can I assist you with operational metrics, missing submissions, or department performance today?'"
)

SPECIALIST_PROMPTS = {
    "productivity": (
        CORE_DIRECTIVE + "\n\n"
        "Focus Area: Company Overall Health Index, department performance bottlenecks, missing operational submissions, and target achievement."
    ),
    "energy": (
        CORE_DIRECTIVE + "\n\n"
        "Focus Area: Power and electricity consumption, fuel efficiency, energy cost per batch, and utilities variance."
    ),
    "hr": (
        CORE_DIRECTIVE + "\n\n"
        "Focus Area: Human capital, operator efficiency, department staffing, missing submission follow-ups, and safety compliance."
    ),
    "process": (
        CORE_DIRECTIVE + "\n\n"
        "Focus Area: First-pass quality yield, scrap rate, defect analysis, cycle times, and batch variance."
    ),
}

FALLBACK_MODELS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
    "groq/compound",
    "groq/compound-mini",
]


def get_ai_response(specialist_type, question, context_data, filters=None, history=None):
    settings = frappe.get_cached_doc("KPI Settings")
    if not settings.enable_ai_assistants:
        return {"error": "AI Assistants are disabled in KPI Settings."}

    api_key = None
    try:
        api_key = settings.get_password("groq_api_key", raise_exception=False)
    except Exception:
        api_key = None

    if not api_key:
        api_key = frappe.conf.get("groq_api_key") or os.environ.get("GROQ_API_KEY")

    if not api_key:
        diagnostic_text = generate_local_diagnostic(specialist_type, question, context_data)
        return {
            "response": diagnostic_text,
            "has_key": False,
            "specialist": specialist_type,
            "model": "Rule-Based Assistant",
        }

    configured_model = (settings.groq_model or "").strip()
    if not configured_model or configured_model not in FALLBACK_MODELS:
        configured_model = "openai/gpt-oss-120b"

    models_to_try = [configured_model] + [m for m in FALLBACK_MODELS if m != configured_model]

    system_prompt = SPECIALIST_PROMPTS.get(specialist_type, SPECIALIST_PROMPTS["productivity"])

    # Build live operational context summary
    context_str = format_context_for_prompt(context_data, filters)
    if context_str:
        system_prompt += f"\n\n--- ENTERPRISE OPERATIONAL CONTEXT (LIVE DATABASE DATA) ---\n{context_str}"

    # Build chat messages with history
    messages = [{"role": "system", "content": system_prompt}]

    if history and isinstance(history, list):
        for msg in history[-8:]:
            role = "assistant" if msg.get("type") == "ai" or msg.get("role") == "assistant" else "user"
            content = msg.get("content") or msg.get("message") or ""
            if content and not content.startswith("<i class="):
                messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": question})

    last_error = None
    for model in models_to_try:
        try:
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": 0.5,
                    "max_tokens": 1000,
                },
                timeout=25,
            )

            if response.status_code == 200:
                data = response.json()
                if model != settings.groq_model:
                    try:
                        frappe.db.set_single_value("KPI Settings", "groq_model", model)
                    except Exception:
                        pass

                return {
                    "response": data["choices"][0]["message"]["content"],
                    "model": model,
                    "has_key": True,
                    "specialist": specialist_type,
                    "tokens_used": data.get("usage", {}).get("total_tokens", 0),
                }

            if response.status_code == 401:
                return {
                    "error": "Invalid Groq API Key (401 Unauthorized). Please check your key in KPI Settings.",
                    "has_key": False,
                }

            if response.status_code == 404:
                last_error = f"Model {model} not found on Groq."
                continue

            if response.status_code in (429, 500, 502, 503):
                try:
                    err_msg = response.json().get("error", {}).get("message", response.text)
                except Exception:
                    err_msg = response.text
                last_error = f"Groq ({model}): {err_msg}"
                continue

            response.raise_for_status()

        except requests.exceptions.RequestException as e:
            last_error = str(e)
            continue

    frappe.log_error(f"Groq AI error: {last_error}", "KPI AI Assistant Error")

    diagnostic_text = generate_local_diagnostic(specialist_type, question, context_data)
    return {
        "response": diagnostic_text,
        "has_key": True,
        "model": "Assistant Fallback",
    }


def generate_local_diagnostic(specialist_type, question, context_data):
    """Fallback generator providing clean, structured, scannable operational answers."""
    q_lower = (question or "").strip().lower()

    # 1. Greetings
    if q_lower in ["hi", "hello", "hey", "good morning", "good afternoon", "good evening", "hi there", "greetings"]:
        return "Hello! I am your KPI & Operations virtual assistant. How can I help you today?"

    if not context_data:
        return "I am connected and ready. What operational metrics or department data would you like to analyze?"

    missing_list = context_data.get("missing_data_summary", [])
    crit_kpis = context_data.get("critical_kpis", [])
    depts_perf = context_data.get("departments_performance", [])
    company_score = context_data.get("company_score")
    company_name = context_data.get("company", "Productix ERP")
    alerts = context_data.get("active_alerts", [])

    # 2. Missing Data Queries
    if any(k in q_lower for k in ["missing", "pending", "who has not", "not entered", "entry", "unsubmitted"]):
        pending_depts = [m for m in missing_list if m.get("missing_entries", 0) > 0]
        total_missing = sum(m.get("missing_entries", 0) for m in pending_depts)

        if not pending_depts:
            return "✅ **All Data Entries Complete**\n\nAll operational departments have submitted their required metrics for the active reporting period."

        lines = [
            f"**Pending KPI Submissions Status — {company_name}**\n",
            f"There are **{total_missing} missing metric entries** across **{len(pending_depts)} departments**:\n",
        ]
        for m in pending_depts:
            emps = ", ".join(m.get("assigned_employees", [])) or "No employees assigned"
            lines.append(f"• **{m.get('department')}**: **{m.get('missing_entries')}** pending metric(s) ({m.get('completed_entries', 0)}/{m.get('required_entries', 0)} logged) — Assigned: *{emps}*\n")

        lines.append("💡 *You can click **📢 Send Alert** below to notify the relevant department employees.*")
        return "\n".join(lines)

    # 3. Machine Health Queries
    if any(k in q_lower for k in ["machine", "equipment", "motor", "pump", "compressor", "line health", "health score", "maintenance"]):
        ms = context_data.get("machines_summary")
        if not ms or ms.get("total", 0) == 0:
            return (
                "⚙️ **Machine Health Fleet Status**\n\n"
                "There are currently **0 active machines** registered in the Machine Health Monitoring system.\n\n"
                "To begin monitoring equipment vibration, temperature, and pressure parameters, register machines under **Machine List** and link them to operational departments."
            )

        crit_machines = ms.get("critical_machines", [])
        lines = [
            f"⚙️ **Machine Fleet Health Status — {company_name}**\n",
            f"Active Fleet: **{ms['total']} machines** | 🟢 Healthy: **{ms['healthy']}** | 🟡 Good: **{ms['good']}** | 🟠 Warning: **{ms['warning']}** | 🔴 Critical: **{ms['critical']}**\n",
        ]

        if crit_machines:
            lines.append(f"**Attention Required ({len(crit_machines)} machines at risk):**\n")
            for m in crit_machines:
                status_icon = "🔴" if m.get("health_status") == "Critical" else "🟠"
                lines.append(
                    f"• {status_icon} **{m.get('machine_name')}** (`{m.get('machine_code')}` in *{m.get('department')}*)\n"
                    f"   - **Health Score**: **{m.get('health_score') or 0}/100** ({m.get('health_status')})\n"
                    f"   - **Status**: {m.get('operating_status', 'Operational')} | **Days Since Maintenance**: {m.get('days_since_maintenance') or 'Unknown'}\n"
                )
            lines.append("\n🛠️ **Recommended Action Plan:**\n1. Prioritize immediate diagnostic sensor readings on critical equipment.\n2. Schedule preventive lubrication and alignment checks to prevent unplanned line shutdowns.\n3. Cross-reference telemetry with related Production output KPIs.")
        else:
            lines.append("✅ **All Equipment Operating Within Normal Parameters**\n\nEvery monitored machine in the fleet is operating at Good or Healthy condition. Continue standard weekly calibration intervals.")

        return "\n".join(lines)

    # 4. Operational Output / Improvement Queries
    if any(k in q_lower for k in ["improve", "output", "operational output", "efficiency", "better", "recommend", "optimize", "action plan"]):
        crit_list = [k for k in crit_kpis if k.get("status") == "Critical"]
        pending_depts = [m for m in missing_list if m.get("missing_entries", 0) > 0]

        lines = [
            f"**Operational Output & Performance Action Plan — {company_name}**\n",
            f"Company Health Index is currently at **{company_score if company_score is not None else '--'}%**.\n",
            "Here are the **top priority operational actions** to improve output:\n",
        ]

        # Action 1: Address Critical Bottlenecks
        if crit_list:
            top_crit = crit_list[0]
            lines.append(f"1. **Remediate Critical KPI Bottleneck**\n   • Focus on **{top_crit.get('kpi_name')}** in **{top_crit.get('department')}** (Actual: **{top_crit.get('actual_value')}** vs Target: **{top_crit.get('target_value')} {top_crit.get('unit', '')}**, {round(float(top_crit.get('achievement_percentage') or 0), 1)}% achieved).\n")
        else:
            lines.append("1. **Maintain Target Throughput**\n   • Key production and quality metrics are within standard operating bands; sustain current cycle times.\n")

        # Action 2: Eliminate Data Blindspots
        if pending_depts:
            top_pending = pending_depts[0]
            lines.append(f"2. **Close Data Blindspots & Complete Pending Submissions**\n   • Ensure timely reporting from **{top_pending.get('department')}** ({top_pending.get('missing_entries')} metrics pending) to maintain real-time visibility.\n")
        else:
            lines.append("2. **Real-time Monitoring**\n   • Data completeness is 100%; verify telemetry signals and operational logs daily.\n")

        # Action 3: Department Score Alignment
        lowest_depts = sorted([d for d in depts_perf if d.get("score") is not None], key=lambda x: x.get("score", 0))
        if lowest_depts:
            low_d = lowest_depts[0]
            lines.append(f"3. **Targeted Department Support**\n   • Support **{low_d.get('department')}** (current score: **{low_d.get('score')}%**) with dedicated resource allocation and equipment checks.\n")
        else:
            lines.append("3. **Cross-Departmental Synchronization**\n   • Review handoff delays between Supply Chain, Production, and Quality Control.\n")

        lines.append("4. **Preventive Machine & Line Maintenance**\n   • Execute scheduled calibration and maintenance cycles to reduce unplanned line stops.\n")

        return "\n".join(lines)

    # 5. Critical KPIs Queries
    if any(k in q_lower for k in ["critical", "warning", "below target", "fail", "bad", "worst"]):
        if not crit_kpis:
            return "✅ **No Critical KPI Deviations**\n\nAll operational KPIs with logged entries are currently performing within target thresholds."

        lines = [
            f"**Critical and Warning Metric Deviations — {company_name}**\n",
        ]
        for k in crit_kpis[:6]:
            status_icon = "🔴" if k.get("status") == "Critical" else "🟡"
            lines.append(
                f"• {status_icon} **{k.get('kpi_name')}** ({k.get('department')}):\n"
                f"  Actual: **{k.get('actual_value')}** | Target: **{k.get('target_value')} {k.get('unit', '')}** (*{round(float(k.get('achievement_percentage') or 0), 1)}% achieved*)\n"
            )
        return "\n".join(lines)

    # 6. Department Performance / Bottlenecks
    if any(k in q_lower for k in ["department", "lowest", "rank", "score", "bottleneck", "perform"]):
        if not depts_perf:
            return f"**{company_name}** has operational departments configured. Overall Health Index: **{company_score if company_score is not None else '--'}%**."

        sorted_depts = sorted(
            depts_perf,
            key=lambda x: (x.get("score") is None, x.get("score") or 0)
        )
        lines = [
            f"**Department Performance Ranking — {company_name}** (Health Index: **{company_score if company_score is not None else '--'}%**):\n",
        ]
        for d in sorted_depts:
            s_val = f"**{d.get('score')}%**" if d.get("score") is not None else "*No Data Logged*"
            lines.append(f"• **{d.get('department')}**: Health Score {s_val} — On Track: **{d.get('on_track', 0)}**, Warning: **{d.get('warning', 0)}**, Critical: **{d.get('critical', 0)}**, Missing: **{d.get('missing', 0)}**\n")

        return "\n".join(lines)

    # 6. Default General Summary
    pending_count = sum(1 for m in missing_list if m.get('missing_entries', 0) > 0)
    lines = [
        f"**Operational Summary — {company_name}**\n",
        f"• **Company Health Index**: **{company_score if company_score is not None else '--'}%**\n",
        f"• **Active Departments**: **{len(depts_perf)}**\n",
        f"• **Active Alerts**: **{len(alerts)}**\n",
        f"• **Departments with Pending Submissions**: **{pending_count}**\n",
        "What specific metric or department would you like to explore?"
    ]
    return "\n".join(lines)


def format_context_for_prompt(context_data, filters=None):
    if not context_data:
        return ""

    lines = []
    company = context_data.get("company", "Productix ERP")
    lines.append(f"Company: {company}")

    if "company_score" in context_data:
        lines.append(f"Company Overall Health Index: {context_data['company_score']}% (Growth: {context_data.get('company_growth', '0')}%)")

    # Department Summaries
    depts = context_data.get("departments_performance", [])
    if depts:
        lines.append("\nDepartment Performance:")
        for d in depts:
            ds = d.get("score") if d.get("score") is not None else "No Data"
            lines.append(
                f" - {d.get('department')}: Score={ds}%, On Track={d.get('on_track', 0)}, "
                f"Warning={d.get('warning', 0)}, Critical={d.get('critical', 0)}, Missing={d.get('missing', 0)} (Total KPIs: {d.get('total_kpis', 0)})"
            )

    # Missing Data Entries Breakdown
    missing = context_data.get("missing_data_summary", [])
    if missing:
        lines.append("\nPending Data Submissions by Department:")
        for m in missing:
            assigned = ", ".join(m.get("assigned_employees", [])) or "No employees assigned"
            lines.append(
                f" - {m.get('department')}: {m.get('missing_entries', 0)} missing entries "
                f"({m.get('completed_entries', 0)}/{m.get('required_entries', 0)} completed). Assigned: [{assigned}]"
            )

    # Critical & Warning KPIs
    crit_kpis = context_data.get("critical_kpis", [])
    if crit_kpis:
        lines.append("\nCritical / Warning KPIs:")
        for k in crit_kpis[:10]:
            lines.append(f" - [{k.get('status')}] {k.get('kpi_name')} ({k.get('department')}): Actual={k.get('actual_value')}, Target={k.get('target_value')} {k.get('unit', '')}, Achieved={k.get('achievement_percentage')}%")

    # Active Alerts
    alerts = context_data.get("active_alerts", [])
    if alerts:
        lines.append(f"\nActive Alerts ({len(alerts)} items):")
        for a in alerts[:6]:
            lines.append(f" - [{a.get('severity')}] {a.get('alert_type')} ({a.get('department')}): {a.get('message')}")

    # Machine Health Fleet Overview
    ms = context_data.get("machines_summary")
    if ms and ms.get("total", 0) > 0:
        lines.append(
            f"\nMachine Health Fleet Overview ({ms['total']} Active Machines): "
            f"Healthy={ms['healthy']}, Good={ms['good']}, Warning={ms['warning']}, Critical={ms['critical']}"
        )
        crit_machines = ms.get("critical_machines", [])
        if crit_machines:
            lines.append("Critical / Warning Equipment:")
            for m in crit_machines[:8]:
                lines.append(
                    f" - [{m.get('health_status')}] {m.get('machine_name')} ({m.get('machine_code')}, {m.get('department')}): "
                    f"Health Score={m.get('health_score')}/100, Operating={m.get('operating_status')}, "
                    f"Days Since Maint={m.get('days_since_maintenance') or 'N/A'}"
                )

    return "\n".join(lines)


def build_context_data(department=None, business_unit=None, customer=None,
                       from_date=None, to_date=None, kpi=None):
    from productix_kpi.kpi_tracking.services.analytics import get_company_performance

    context = {}
    context["company"] = frappe.db.get_single_value("KPI Settings", "company") or "Productix Industries"

    # Company overview
    company_perf = get_company_performance()
    context["company_score"] = company_perf.get("score")
    context["company_growth"] = company_perf.get("growth")
    context["departments_performance"] = company_perf.get("departments", [])

    # Live missing data summary derived from active period monitoring
    try:
        from productix_kpi.kpi_tracking.api.data_entry import _get_data_entry_monitoring_internal
        monitoring = _get_data_entry_monitoring_internal()
        missing_summary = []
        for d in monitoring.get("departments", []):
            missing_summary.append({
                "department": d["department"],
                "department_code": d["department_code"],
                "required_entries": d["required_entries"],
                "completed_entries": d["completed_entries"],
                "missing_entries": d["missing_entries"],
                "completion_percentage": d["completion_percentage"],
                "assigned_employees": d.get("assigned_employees", []),
                "period": d.get("period", ""),
                "frequency": d.get("frequency", "Monthly"),
            })
        context["missing_data_summary"] = missing_summary
    except Exception as e:
        frappe.log_error(f"Error building AI missing data context: {str(e)}", "KPI AI Context")
        context["missing_data_summary"] = []

    # Critical & Warning KPIs
    critical_entries = frappe.db.get_all(
        "KPI Data Entry",
        filters={"docstatus": 1, "status": ["in", ["Critical", "Warning"]]},
        fields=["kpi", "department", "actual_value", "target_value",
                "achievement_percentage", "status", "period", "entry_date", "entered_by"],
        order_by="entry_date desc", limit_page_length=15,
    )
    for ce in critical_entries:
        ce["kpi_name"] = frappe.db.get_value("KPI Definition", ce.kpi, "kpi_name") or ce.kpi
        ce["unit"] = frappe.db.get_value("KPI Definition", ce.kpi, "unit") or ""
    context["critical_kpis"] = critical_entries

    # Recent entries
    entry_filters = {"docstatus": 1}
    if department:
        entry_filters["department"] = department
    if kpi:
        entry_filters["kpi"] = kpi

    entries = frappe.db.get_all(
        "KPI Data Entry", filters=entry_filters,
        fields=["kpi", "department", "actual_value", "target_value",
                "achievement_percentage", "status", "period", "entry_date", "entered_by"],
        order_by="entry_date desc", limit_page_length=20,
    )
    context["recent_kpi_entries"] = entries

    # Active alerts
    alert_filters = {"status": ["in", ["Active", "Acknowledged"]]}
    if department:
        alert_filters["department"] = department
    alerts = frappe.db.get_all(
        "KPI Alert", filters=alert_filters,
        fields=["kpi", "department", "alert_type", "severity", "message", "trigger_period"],
        order_by="creation desc", limit_page_length=10,
    )
    context["active_alerts"] = alerts

    # Live Machine Health Summary
    try:
        if frappe.db.table_exists("Machine"):
            m_filters = {"is_active": 1}
            if department:
                m_filters["department"] = department
            machines = frappe.db.get_all(
                "Machine",
                filters=m_filters,
                fields=[
                    "name", "machine_name", "machine_code", "machine_type",
                    "department", "operating_status", "health_score", "health_status",
                    "last_reading_date", "days_since_maintenance", "location",
                ],
                order_by="health_score asc",
            )
            total_m = len(machines)
            healthy_m = sum(1 for m in machines if m.get("health_status") == "Healthy")
            good_m = sum(1 for m in machines if m.get("health_status") == "Good")
            warning_m = sum(1 for m in machines if m.get("health_status") == "Warning")
            critical_m = sum(1 for m in machines if m.get("health_status") == "Critical")
            context["machines_summary"] = {
                "total": total_m,
                "healthy": healthy_m,
                "good": good_m,
                "warning": warning_m,
                "critical": critical_m,
                "machines": machines,
                "critical_machines": [m for m in machines if m.get("health_status") in ("Critical", "Warning")],
            }
    except Exception as e:
        frappe.log_error(f"Error building AI machine context: {str(e)}", "KPI AI Context")
        context["machines_summary"] = {"total": 0, "healthy": 0, "good": 0, "warning": 0, "critical": 0, "machines": []}

    return context


def get_suggested_questions(specialist_type, department=None):
    questions = {
        "productivity": [
            "Which departments have missing data entries?",
            "Which KPIs are currently critical or below target?",
            "What is the current health status of our machines?",
            "How can we improve overall operational output?",
        ],
        "energy": [
            "Which energy KPIs are showing negative variances?",
            "How can we optimize power consumption per batch?",
            "What are our top utility efficiency opportunities?",
        ],
        "hr": [
            "Who has not entered required data for their department?",
            "Which departments have low completion rates?",
            "What is the safety compliance status across departments?",
        ],
        "process": [
            "What is the health score of our machines and equipment?",
            "Which quality or defect rate KPIs are in warning status?",
            "What is the root cause of recent performance variances?",
            "How do we improve first-pass yield to target?",
        ],
    }
    return questions.get(specialist_type, questions["productivity"])
