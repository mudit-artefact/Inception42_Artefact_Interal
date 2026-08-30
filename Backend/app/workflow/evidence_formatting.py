"""Turning retrieved evidence into the text the model reads."""

from app.domain.employee_facts import EmployeeFacts
from app.domain.enums import HrDataField

NO_POLICY_EXTRACTS = "(no policy extracts were retrieved for this question)"
NO_EMPLOYEE_FACTS = "(no facts from this employee's record were needed for this question)"

EMPLOYEE_RECORD_HEADING = "THIS EMPLOYEE'S OWN RECORD"
POLICY_EXTRACTS_HEADING = "POLICY EXTRACTS"
NOTHING_FOUND_FOR_THIS_PART = (
    "NOTHING WAS FOUND FOR THIS PART. It cannot be answered from HC Services policy or "
    "from this employee's record."
)


def build_evidence_block(parts: list[dict]) -> str:
    """
    The whole of the evidence, written out part by part, as one block for the model.

    Every part is labelled with the question it was gathered for, so the model can see
    which extract belongs to which part — and, just as importantly, which part has
    nothing behind it and must therefore be declined rather than answered from memory.

    A single part used to be left unlabelled, on the grounds that there was nothing to
    tell apart. That quietly removed the only place the question appeared when a
    follow-up had been reworded, so the model was given the evidence without the question
    it was gathered for. Label it always; `build_checkable_evidence` is what keeps the
    labels away from the check.
    """
    if not parts:
        return ""
    return "\n\n".join(
        f'PART {part["index"]} — "{part["question"]}"\n{_evidence_for_one_part(part)}'
        for part in parts
    )


def build_checkable_evidence(parts: list[dict]) -> str:
    """
    The same evidence with the questions stripped out, for the check on the answer.

    The block above and this one look almost identical, and the difference is the whole
    point. The block above names the question each extract was gathered for, because the
    model needs to know which part it is answering. This one must not, because it is what
    every figure in the answer is held against — and a question is not evidence.

    While one string did both jobs, a number the employee typed counted as proof of
    itself: "can I carry over 25 days?" and the answer "yes, 25 days" passed the check on
    the strength of the 25 in the question.
    """
    if not parts:
        return ""
    return "\n\n".join(_evidence_for_one_part(part) for part in parts)


def _evidence_for_one_part(part: dict) -> str:
    """One part's evidence: its facts, its extracts, or a plain statement of neither."""
    if not part.get("has_evidence"):
        return NOTHING_FOUND_FOR_THIS_PART

    sections = []
    if part.get("employee_facts_text"):
        sections.append(f"{EMPLOYEE_RECORD_HEADING}\n{part['employee_facts_text']}")
    if part.get("policy_passages"):
        sections.append(
            f"{POLICY_EXTRACTS_HEADING}\n{format_policy_passages(part['policy_passages'])}"
        )
    return "\n\n".join(sections) or NOTHING_FOUND_FOR_THIS_PART


def format_policy_passages(passages: list[dict]) -> str:
    """The retrieved policy extracts, numbered, with where each came from."""
    if not passages:
        return NO_POLICY_EXTRACTS

    formatted_passages = []
    for position, passage in enumerate(passages, start=1):
        origin = f"{passage.get('title', '')} — {passage.get('section', '')}"
        page = passage.get("page_number")
        if page:
            origin += f", page {page}"
        origin += _when_this_rule_applied(passage)
        formatted_passages.append(f"[{position}] {origin}\n{passage.get('text', '')}")

    return "\n\n".join(formatted_passages)


def _when_this_rule_applied(passage: dict) -> str:
    """
    The version an extract comes from, and the window it was in force.

    This is the only point at which any of that reaches the model. A superseded rule is
    retrieved deliberately — a question about an event last year should be answered with
    last year's rule — so the model has to be told which it is looking at, in the line it
    already reads to know where an extract came from.
    """
    version = passage.get("policy_version")
    if not version:
        return ""

    effective_from = passage.get("effective_from") or "?"
    if passage.get("status") == "superseded":
        effective_to = passage.get("effective_to") or "?"
        return (
            f"  (Version {version}, IN FORCE {effective_from} TO {effective_to} — "
            f"SUPERSEDED: apply only to events in that window)"
        )
    return f"  (Version {version}, in force from {effective_from} — current)"


def format_employee_facts(facts: EmployeeFacts, allowed_fields: list[str]) -> str:
    """
    Only the facts the routing step asked for, written out for the model.

    Anything not named is left out entirely, so the model cannot repeat a detail that was
    never relevant to the question.
    """
    if not allowed_fields:
        return NO_EMPLOYEE_FACTS

    requested = set(allowed_fields)
    lines: list[str] = [f"Employee: {facts.name} ({facts.employee_id})"]

    if HrDataField.EMPLOYEE_PROFILE in requested:
        lines.append(f"Role: {facts.job_title}, {facts.department} (grade {facts.grade})")
        lines.append(f"Started: {facts.start_date}")
        if facts.employment_fraction < 1.0:
            lines.append(
                f"Works {facts.employment_fraction} of full time, so leave is pro-rated"
            )
    if HrDataField.YEARS_OF_SERVICE in requested:
        lines.append(f"Years of service: {facts.years_of_service}")
    if HrDataField.PROBATION_STATUS in requested:
        lines.append(f"Probation status: {facts.probation_status}")
    if HrDataField.LINE_MANAGER in requested:
        lines.append(f"Line manager: {facts.manager_name} ({facts.manager_role})")
    if HrDataField.ANNUAL_LEAVE_BALANCE in requested:
        lines.append(f"Annual leave remaining: {facts.annual_leave_balance} days")
        lines.extend(_balance_rows(facts, "annual"))
    if HrDataField.SICK_LEAVE_BALANCE in requested:
        lines.append(f"Sick leave remaining: {facts.sick_leave_balance} days in total")
        lines.extend(_balance_rows(facts, "sick"))
    if HrDataField.CARRY_OVER_DAYS in requested:
        lines.append(f"Carried over from last year: {facts.carry_over_days} days")

    if HrDataField.MANAGER_HISTORY in requested and facts.manager_history:
        lines.append("Previous line managers:")
        lines.extend(
            f"  - {change.effective_date}: {change.previous_manager} became "
            f"{change.current_manager} ({change.reason})"
            for change in facts.manager_history
        )

    if HrDataField.RECENT_LEAVE_REQUESTS in requested and facts.recent_leave_requests:
        lines.append("Recent leave requests:")
        lines.extend(
            f"  - {request.leave_type}, {request.start_date} to {request.end_date}, "
            f"{request.days} days, {request.status}"
            f"{f', approved by {request.approver}' if request.approver else ''}"
            for request in facts.recent_leave_requests
        )

    if HrDataField.RECENT_EXPENSE_CLAIMS in requested and facts.recent_expense_claims:
        lines.append("Recent expense claims:")
        lines.extend(_claim_row(claim) for claim in facts.recent_expense_claims)

    return "\n".join(lines)


def _balance_rows(facts: EmployeeFacts, leave_type: str) -> list[str]:
    """
    Every year and every pay rate held for one kind of leave.

    The single "remaining" figure above answers "how many days do I have left" and
    nothing else. It cannot answer how this year compares with last, or how much of a
    long sick absence is paid in full — both of which the record knows and used to keep
    to itself, so the assistant said the information was not available while it sat one
    field away.
    """
    matching = [
        balance for balance in facts.leave_balances
        if leave_type in balance.leave_type.lower()
    ]
    if len(matching) < 2:
        return []

    rows = ["  Broken down:"]
    for balance in sorted(matching, key=lambda b: (-b.year, b.leave_type)):
        detail = (
            f"    - {balance.year} {balance.leave_type}: {balance.entitled_days} entitled, "
            f"{balance.used_days} used, {balance.remaining_days} remaining"
        )
        if balance.carry_over_days:
            detail += f", {balance.carry_over_days} carried over"
        if balance.pay_rate_pct is not None:
            detail += f", paid at {balance.pay_rate_pct}%"
        if balance.accrued_days and balance.accrued_days != balance.entitled_days:
            detail += f", {balance.accrued_days} accrued so far"
        rows.append(detail)
    return rows


def _claim_row(claim) -> str:
    """One expense claim, including who approved it and what it was assessed under."""
    row = f"  - {claim.category}, AED {claim.amount_aed}, {claim.claim_date}, {claim.status}"
    if claim.approver:
        row += f", decided by {claim.approver}"
    if claim.description:
        row += f" — {claim.description}"
    if claim.policy_reference:
        row += f" (assessed under {claim.policy_reference})"
    return row
