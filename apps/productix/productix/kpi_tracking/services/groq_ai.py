import frappe
import json
import os
import requests

CORE_DIRECTIVE = (
    "You are the Productix KPI & Operations Virtual Assistant — an intelligent, natural, and conversational AI advisor embedded in the enterprise ERP.\n\n"
    "CRITICAL CONVERSATIONAL GUIDELINES:\n"
    "1. NATURAL & CONVERSATIONAL:\n"
    "   - Act like a real, helpful executive chatbot.\n"
    "   - If the user sends a greeting (e.g. 'hi', 'hello', 'hey', 'good morning', etc.), respond naturally and warmly: "
    "     'Hello! I am your KPI & Operations virtual assistant. How can I help you today?'\n"
    "   - For general questions, respond conversationally, directly, and politely.\n\n"
    "2. DIRECT & TO THE POINT:\n"
    "   - Be concise and actionable. Do not give lengthy, unnecessary explanations or repetitive filler paragraphs.\n"
    "   - Answer the specific question asked immediately.\n\n"
    "3. CLEAN & SPACIOUS FORMATTING (NEVER CONGESTED):\n"
    "   - Use clean Markdown with double line breaks between distinct thoughts and sections.\n"
    "   - Use neat bullet points with bold highlights (**Department Name**, **Metric**, **Actual vs Target**) for readability.\n"
    "   - Keep answers easy to scan at a glance.\n\n"
    "4. DATA GROUNDING:\n"
    "   - When answering questions about department metrics, missing submissions, bottlenecks, or performance rankings, reference the real figures provided in the ENTERPRISE OPERATIONAL CONTEXT below.\n"
    "   - If suggesting an alert to be sent to a department with missing data, state the department name and assigned employees clearly."
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
    """Fallback generator providing clean, conversational answers."""
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
    if any(k in q_lower for k in ["missing", "pending", "who has not", "not entered", "entry"]):
        if not missing_list:
            return "✅ **All Data Entries Complete**: All operational departments have submitted their required metrics for the current reporting period."

        pending_depts = [m for m in missing_list if m.get("missing_entries", 0) > 0]
        total_missing = sum(m.get("missing_entries", 0) for m in pending_depts)

        if not pending_depts:
            return "✅ **All Data Entries Complete**: All operational departments have completed their required submissions."

        lines = [
            f"Here is the status of pending submissions for **{company_name}**:\n",
            f"There are **{total_missing} missing metric entries** across **{len(pending_depts)} departments**:\n",
        ]
        for m in pending_depts:
            emps = ", ".join(m.get("assigned_employees", [])) or "No employees assigned"
            lines.append(f"• **{m.get('department')}**: **{m.get('missing_entries')}** pending ({m.get('completed_entries')}/{m.get('required_entries')} done) — Assigned: {emps}\n")

        lines.append("💡 *You can click **📢 Send Alert** below to notify the relevant department employees.*")
        return "\n".join(lines)

    # 3. Critical KPIs Queries
    if any(k in q_lower for k in ["critical", "warning", "below target", "fail", "bad", "worst"]):
        if not crit_kpis:
            return "✅ **No Critical KPI Deviations**: All operational KPIs with logged entries are currently performing within target thresholds."

        lines = [
            f"Here are the **critical and warning metric deviations** requiring attention:\n",
        ]
        for k in crit_kpis[:6]:
            status_icon = "🔴" if k.get("status") == "Critical" else "🟡"
            lines.append(
                f"• {status_icon} **{k.get('kpi_name')}** ({k.get('department')}):\n"
                f"  Actual: **{k.get('actual_value')}** | Target: **{k.get('target_value')} {k.get('unit', '')}** (*{round(float(k.get('achievement_percentage') or 0), 1)}% achieved*)\n"
            )
        return "\n".join(lines)

    # 4. Department Performance / Bottlenecks
    if any(k in q_lower for k in ["department", "lowest", "rank", "score", "bottleneck", "perform"]):
        if not depts_perf:
            return f"**{company_name}** has operational departments configured. Overall Health Index: **{company_score if company_score is not None else '--'}%**."

        sorted_depts = sorted(
            depts_perf,
            key=lambda x: (x.get("score") is None, x.get("score") or 0)
        )
        lines = [
            f"Here is the current **Department Performance Ranking** (Company Health: **{company_score if company_score is not None else '--'}%**):\n",
        ]
        for d in sorted_depts:
            s_val = f"**{d.get('score')}%**" if d.get("score") is not None else "*No Data Logged*"
            lines.append(f"• **{d.get('department')}**: Health Score {s_val} (On Track: {d.get('on_track', 0)}, Warning: {d.get('warning', 0)}, Critical: {d.get('critical', 0)}, Missing: {d.get('missing', 0)})\n")

        return "\n".join(lines)

    # 5. Default General Summary
    lines = [
        f"Here is a quick operational overview for **{company_name}**:\n",
        f"• **Company Health Index**: **{company_score if company_score is not None else '--'}%**\n",
        f"• **Active Departments**: **{len(depts_perf)}**\n",
        f"• **Active Alerts**: **{len(alerts)}**\n",
        f"• **Departments with Pending Submissions**: **{sum(1 for m in missing_list if m.get('missing_entries', 0) > 0)}**\n",
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

    return "\n".join(lines)


def build_context_data(department=None, business_unit=None, customer=None,
                       from_date=None, to_date=None, kpi=None):
    from productix.kpi_tracking.services.analytics import get_company_performance

    context = {}
    context["company"] = frappe.db.get_single_value("KPI Settings", "company") or "Productix Industries"

    # Company overview
    company_perf = get_company_performance()
    context["company_score"] = company_perf.get("score")
    context["company_growth"] = company_perf.get("growth")
    context["departments_performance"] = company_perf.get("departments", [])

    # Missing data summary derived directly from active departments and KPI definitions
    try:
        departments = frappe.db.get_all("KPI Department", filters={"is_active": 1}, fields=["name", "department_name"])
        missing_summary = []
        for d in departments:
            total_kpis = frappe.db.count("KPI Definition", {"department": d.name, "is_active": 1})
            entries_count = frappe.db.count("KPI Data Entry", {"department": d.name, "docstatus": 1})
            missing_count = max(0, total_kpis - entries_count)
            employees = frappe.db.get_all("KPI User Assignment", filters={"department": d.name, "is_active": 1}, pluck="user")
            missing_summary.append({
                "department": d.department_name,
                "required_entries": total_kpis,
                "completed_entries": min(entries_count, total_kpis),
                "missing_entries": missing_count,
                "assigned_employees": employees,
            })
        context["missing_data_summary"] = missing_summary
    except Exception:
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

    return context


def get_suggested_questions(specialist_type, department=None):
    questions = {
        "productivity": [
            "Which departments have missing data entries?",
            "Which KPIs are currently critical or below target?",
            "Which department is performing lowest right now?",
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
            "Which quality or defect rate KPIs are in warning status?",
            "What is the root cause of recent performance variances?",
            "How do we improve first-pass yield to target?",
        ],
    }
    return questions.get(specialist_type, questions["productivity"])
