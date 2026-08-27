"""
app/prompts.py — Bilingual system prompt templates for HCS-01 with SQL Database Context
"""

# ── Main RAG System Prompt ────────────────────────────────────────

SYSTEM_PROMPT_TEMPLATE = """\
You are the HC Services Policy & Leave Concierge (HCS-01), an authoritative and \
helpful HR assistant for HC Services employees.

TARGET RESPONSE LANGUAGE: {target_language_label}
INSTRUCTION: You MUST respond exclusively in {target_language_label}. \
Do not mix languages. If the context is in a different language, \
translate and synthesise the answer fluently in {target_language_label}.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EMPLOYEE RELATIONAL DATABASE (SQL Omni HR)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Employee ID       : {employee_id}
Employee Name     : {employee_name}
Role / Job Title  : {employee_role} (Grade: {employee_grade})
Department        : {employee_department}
Email / Phone     : {employee_email} | {employee_phone}
Work Location     : {employee_location}
Start Date        : {employee_start_date} ({years_of_service} years of service)
Probation Status  : {probation_status}

CURRENT LINE MANAGER (SQL Database):
- Name            : {manager_name}
- Email           : {manager_email}
- Role            : {manager_role}

MANAGER TRANSITION HISTORY (SQL Database):
{manager_history_summary}

LIVE LEAVE BALANCES (SQL Database):
{leave_balances_summary}

RECENT LEAVE REQUESTS & APPROVALS (SQL Database):
{recent_leave_requests_summary}

RECENT EXPENSE CLAIMS (SQL Database):
{recent_expense_claims_summary}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RETRIEVED HR POLICY CONTEXT (Qdrant Vector Store)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{retrieved_chunks}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INSTRUCTIONS FOR GROUNDED & PERSONALIZED ANSWERS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. For user-specific details (e.g., current line manager, previous managers, remaining leaves, used days, probation, or past leave requests), ALWAYS rely on the ground-truth EMPLOYEE RELATIONAL DATABASE (SQL) records above.
2. Cross-reference the employee's personal SQL data with the RETRIEVED HR POLICY CONTEXT to provide personalized, accurate, and actionable answers (e.g. checking their actual leave balance against policy rules or noting their specific manager who must approve requests).
3. If the user asks about changes to their manager or history, cite the exact records from the MANAGER TRANSITION HISTORY table.
4. Keep answers direct, concise, and professional. Use bullet points where appropriate to minimize latency.
5. Do NOT include inline citation markers like [Source: HC-PC-001]; the user interface presents policy source citations separately.
6. If a general policy question cannot be answered from the retrieved context, state:
   "I'm unable to find this information in the current policy documents. Please contact People & Culture at people@hcservices.ae."
7. Never fabricate policies or employee facts.
"""

LANGUAGE_LABELS = {
    "en": "English",
    "ar": "Arabic (العربية)",
}


def build_system_prompt(
    target_language: str,
    sql_context: dict,
    retrieved_chunks: str,
) -> str:
    """
    Render the system prompt with full SQL relational state and policy context.
    """
    lang_label = LANGUAGE_LABELS.get(target_language, "English")

    # Format manager history
    mgr_hist_list = sql_context.get("manager_history", [])
    if mgr_hist_list:
        mgr_lines = [
            f"- Effective {h['effective_date']}: Manager changed from '{h['previous_manager']}' to '{h['current_manager']}' (Reason: {h.get('reason', 'N/A')})"
            for h in mgr_hist_list
        ]
        mgr_history_summary = "\n".join(mgr_lines)
    else:
        mgr_history_summary = "- No historical manager transitions recorded (Current manager assigned at start date)."

    # Format leave balances
    balances_list = sql_context.get("balances", [])
    if balances_list:
        bal_lines = [
            f"- {b['type']}: {b['remaining']} remaining / {b['used']} used (Entitled: {b['entitled']} {b.get('unit', 'days')}, Carry-over: {b.get('carry_over', 0)} days)"
            for b in balances_list
        ]
        leave_balances_summary = "\n".join(bal_lines)
    else:
        leave_balances_summary = (
            f"- Annual Leave: {sql_context.get('annual_leave_balance', 20)} days remaining\n"
            f"- Sick Leave: {sql_context.get('sick_leave_balance', 10)} days remaining\n"
            f"- Carry-Over: {sql_context.get('carry_over_days', 0)} days"
        )

    # Format recent leave requests
    reqs_list = sql_context.get("recent_leave_requests", [])
    if reqs_list:
        req_lines = [
            f"- {r['start_date']} to {r['end_date']} ({r['days']} days {r['leave_type']}): Status = {r['status']}, Approver = {r['approver']} (Notes: {r.get('notes', 'None')})"
            for r in reqs_list
        ]
        recent_leave_requests_summary = "\n".join(req_lines)
    else:
        recent_leave_requests_summary = "- No recent leave requests on record."

    # Format recent expense claims
    exp_list = sql_context.get("recent_expense_claims", [])
    if exp_list:
        exp_lines = [
            f"- {e['date']}: {e['category']} — AED {e['amount_aed']:.2f} (Status: {e['status']}, Approver: {e['approver']})"
            for e in exp_list
        ]
        recent_expense_claims_summary = "\n".join(exp_lines)
    else:
        recent_expense_claims_summary = "- No recent expense claims on record."

    emp_name = sql_context.get("name", "Employee")
    if target_language == "ar" and sql_context.get("name_ar"):
        emp_name = sql_context.get("name_ar")

    return SYSTEM_PROMPT_TEMPLATE.format(
        target_language_label=lang_label,
        employee_id=sql_context.get("user_id", "EMP001"),
        employee_name=emp_name,
        employee_role=sql_context.get("job_title") or sql_context.get("role", "Staff"),
        employee_grade=sql_context.get("grade", "Grade 9"),
        employee_department=sql_context.get("department", "General"),
        employee_email=sql_context.get("email", ""),
        employee_phone=sql_context.get("phone", "+971 50 123 4567"),
        employee_location=sql_context.get("location", "Dubai Office"),
        employee_start_date=sql_context.get("start_date", "2022-03-15"),
        years_of_service=sql_context.get("years_of_service", 0),
        probation_status=sql_context.get("probation_status", "Passed"),
        manager_name=sql_context.get("manager_name", "Line Manager"),
        manager_email=sql_context.get("manager_email", ""),
        manager_role=sql_context.get("manager_role", "Line Manager"),
        manager_history_summary=mgr_history_summary,
        leave_balances_summary=leave_balances_summary,
        recent_leave_requests_summary=recent_leave_requests_summary,
        recent_expense_claims_summary=recent_expense_claims_summary,
        retrieved_chunks=retrieved_chunks,
    )


# ── Chunk Formatting Helper ───────────────────────────────────────

def format_chunks(chunks: list[dict]) -> str:
    """
    Format retrieved Qdrant chunks into the policy context block.
    Includes text rules and visual diagram transcriptions directly from PDF pages.
    """
    if not chunks:
        return "[No relevant policy sections found for this query.]"

    lines = []
    for i, chunk in enumerate(chunks, start=1):
        source = chunk.get("source", "Unknown")
        title = chunk.get("title", "")
        section = chunk.get("section", "")
        page_num = chunk.get("page_number", 1)
        text = chunk.get("text", "").strip()
        score = chunk.get("score", 0.0)
        has_image = chunk.get("has_image", False)
        
        ref = f"{title} ({source})" if title else source
        ref += f" — {section} [Page {page_num} of PDF]"
        if has_image:
            ref += " [Visual Diagram Embedded in PDF]"
            
        chunk_str = f"[Context {i} | Source: {ref} | Relevance: {score:.2f}]\n{text}"
        lines.append(chunk_str + "\n")

    return "\n---\n".join(lines)
