"""
Step 3: decide what each part of the question has to be answered from.

Every part is routed on its own, so a message asking two things can send one part to the
policy documents and decline the other. The model proposes each route, then two
deterministic rules correct its two predictable mistakes.
"""

import logging
import re

from app.domain.enums import HrDataField, QuestionIntent, RequiredEvidence
from app.workflow.conversation_state import ConversationState
from app.workflow.language_model_client import generate_structured_output
from app.workflow.prompts import SOURCE_ROUTING_INSTRUCTIONS
from app.workflow.structured_outputs import SourceRoutingDecision

logger = logging.getLogger(__name__)

CONFIDENT_ENOUGH_TO_ANSWER = 0.8

# "my", "I", and their Arabic equivalents — someone asking about themselves.
FIRST_PERSON_PATTERN = re.compile(
    r"\b(my|mine|i|i'm|i've|me)\b|رصيدي|مديري|إجازتي|لدي|عندي", re.IGNORECASE
)

# What a question is about, and the facts needed to answer it. Used only when the model
# named no fields at all: reading the profile and nothing else is how "compare my balance
# with last year" came to be answered "that is not in your record".
FIELDS_FOR_SUBJECT = (
    (re.compile(r"balance|remaining|left|entitle|accru|carry[- ]?over|leave|رصيد|إجاز", re.I),
     [HrDataField.ANNUAL_LEAVE_BALANCE, HrDataField.SICK_LEAVE_BALANCE,
      HrDataField.CARRY_OVER_DAYS, HrDataField.YEARS_OF_SERVICE]),
    (re.compile(r"sick|medical|مرض", re.I),
     [HrDataField.SICK_LEAVE_BALANCE, HrDataField.RECENT_LEAVE_REQUESTS]),
    (re.compile(r"manager|report|supervis|مدير", re.I),
     [HrDataField.LINE_MANAGER, HrDataField.MANAGER_HISTORY]),
    (re.compile(r"probation|تجربة", re.I),
     [HrDataField.PROBATION_STATUS, HrDataField.EMPLOYEE_PROFILE]),
    (re.compile(r"expense|claim|reimburse|نفقات|مصروف", re.I),
     [HrDataField.RECENT_EXPENSE_CLAIMS, HrDataField.EMPLOYEE_PROFILE]),
    (re.compile(r"request|applied|booked|طلب", re.I),
     [HrDataField.RECENT_LEAVE_REQUESTS]),
    (re.compile(r"approv|signed off|authoris|decided|وافق", re.I),
     [HrDataField.RECENT_LEAVE_REQUESTS, HrDataField.RECENT_EXPENSE_CLAIMS,
      HrDataField.LINE_MANAGER]),
    (re.compile(r"travel|flight|class|grade|درجة|سفر", re.I),
     [HrDataField.EMPLOYEE_PROFILE]),
)

# Words that point at something recorded about a specific employee.
PERSONAL_SUBJECT_PATTERN = re.compile(
    r"\b(balance|remaining|left|manager|probation|entitle\w*|accrued|carry[- ]?over"
    r"|days?\s+off|service)\b|رصيد|مدير|إجاز|تجربة",
    re.IGNORECASE,
)


def route_each_subquery(state: ConversationState) -> dict:
    """
    Choose, for every part, between policy documents, the employee's own record, both,
    or neither.

    A question that was never split arrives here as a single part, so the common case
    costs exactly the one model call it always did.
    """
    parts = state.get("subqueries") or [
        state.get("retrieval_query") or state["employee_question"]
    ]

    plans = [
        _plan_for_one_part(state, index, part) for index, part in enumerate(parts, start=1)
    ]

    return {
        "subquery_plans": plans,
        "required_evidence": _summarise_routes(plans),
        "requested_hr_data_fields": _every_field_asked_for(plans),
        "routing_reason": "; ".join(plan["routing_reason"] for plan in plans if plan["routing_reason"]),
    }


def _plan_for_one_part(state: ConversationState, index: int, part: str) -> dict:
    """Where one part must be answered from, and which employee facts it may read."""
    decision = generate_structured_output(
        messages=[
            {"role": "system", "content": SOURCE_ROUTING_INSTRUCTIONS},
            {"role": "user", "content": f'The employee asked: "{part}"'},
        ],
        output_model=SourceRoutingDecision,
    )

    required_evidence = decision.required_evidence
    requested_fields = list(decision.requested_hr_data_fields)

    required_evidence, requested_fields = _include_personal_record_when_asked_about_oneself(
        part, required_evidence, requested_fields
    )
    required_evidence = _do_not_refuse_a_confident_hr_question(state, required_evidence)

    logger.info(
        f"Part {index} needs {required_evidence} "
        f"(fields: {[field.value for field in requested_fields] or 'none'})"
    )

    return {
        "index": index,
        "question": part,
        "required_evidence": required_evidence.value,
        "requested_hr_data_fields": [field.value for field in requested_fields],
        "routing_reason": decision.reason,
    }


def _summarise_routes(plans: list[dict]) -> str:
    """
    The turn as a whole, in the same vocabulary one part uses.

    The parts that cannot be served are left out: a message where one part is answerable
    is an answerable message, and only a message where nothing is answerable is refused.
    """
    servable = {
        plan["required_evidence"]
        for plan in plans
        if plan["required_evidence"] != RequiredEvidence.UNSUPPORTED
    }
    if not servable:
        return RequiredEvidence.UNSUPPORTED.value
    if servable == {RequiredEvidence.POLICY.value}:
        return RequiredEvidence.POLICY.value
    if servable == {RequiredEvidence.HR_DATA.value}:
        return RequiredEvidence.HR_DATA.value
    return RequiredEvidence.BOTH.value


def _every_field_asked_for(plans: list[dict]) -> list[str]:
    """Each employee fact any part needs, named once, in the order the parts asked."""
    fields: list[str] = []
    for plan in plans:
        for field in plan["requested_hr_data_fields"]:
            if field not in fields:
                fields.append(field)
    return fields


def _include_personal_record_when_asked_about_oneself(
    question: str,
    required_evidence: RequiredEvidence,
    requested_fields: list[HrDataField],
) -> tuple[RequiredEvidence, list[HrDataField]]:
    """
    "How many days do I have left?" is about this employee, whatever the model said.

    Cheap insurance: the model reliably spots the policy angle and intermittently forgets
    that the question is also personal.
    """
    asks_about_self = bool(FIRST_PERSON_PATTERN.search(question)) and bool(
        PERSONAL_SUBJECT_PATTERN.search(question)
    )
    if not asks_about_self:
        return required_evidence, requested_fields

    if required_evidence == RequiredEvidence.POLICY:
        required_evidence = RequiredEvidence.BOTH
    elif required_evidence == RequiredEvidence.UNSUPPORTED:
        required_evidence = RequiredEvidence.HR_DATA

    if not requested_fields:
        requested_fields = _fields_the_question_points_at(question)

    return required_evidence, requested_fields


def _fields_the_question_points_at(question: str) -> list[HrDataField]:
    """
    A reasonable guess at what to read, when the model named nothing.

    It used to fall back to the profile — job title, department, grade — whatever the
    question was about. So "how does my balance compare with last year" was answered from
    a record that had been asked for everything except the balances, and the assistant
    reported that the information was unavailable while it sat one field away.
    """
    fields: list[HrDataField] = []
    for subject, needed in FIELDS_FOR_SUBJECT:
        if subject.search(question):
            fields.extend(field for field in needed if field not in fields)
    return fields or [HrDataField.EMPLOYEE_PROFILE]


def _do_not_refuse_a_confident_hr_question(
    state: ConversationState, required_evidence: RequiredEvidence
) -> RequiredEvidence:
    """
    Refuse only when the question really cannot be served.

    Without this the "unsupported" route turns into a refusal machine: it has no tuning
    behind it, and refusing a question the old system answered is a regression an
    employee feels immediately.
    """
    if required_evidence != RequiredEvidence.UNSUPPORTED:
        return required_evidence

    is_a_confident_hr_question = (
        state.get("question_intent") == QuestionIntent.HR_QUESTION
        and state.get("intent_confidence", 0.0) >= CONFIDENT_ENOUGH_TO_ANSWER
    )
    if is_a_confident_hr_question:
        logger.info("Overriding 'unsupported': this reads as a confident HR question")
        return RequiredEvidence.POLICY
    return required_evidence
