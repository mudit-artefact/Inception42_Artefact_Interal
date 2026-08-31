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
#
# Arabic marks the first person on the verb rather than with a separate word, so a list
# of possessive nouns misses "أستحق" ("am I entitled to") entirely — which is how an
# Arabic speaker most naturally asks about their own leave. The verb prefixes are here
# for that reason.
FIRST_PERSON_PATTERN = re.compile(
    r"\b(my|mine|i|i'm|i've|me)\b"
    r"|رصيدي|مديري|إجازتي|لدي|عندي|أستحق|استحق|أقدر|اقدر|سجلي|خدمتي|راتبي"
    r"|لي\b|علي\b",
    re.IGNORECASE,
)

# What a question is about, and the facts needed to answer it. Used only when the model
# named no fields at all: reading the profile and nothing else is how "compare my balance
# with last year" came to be answered "that is not in your record".
FIELDS_FOR_SUBJECT = (
    (re.compile(r"balance|remaining|left|entitle|accru|carry[- ]?over|leaves?|رصيد|إجاز", re.I),
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

# Words that mean a rule has to be read, not just a record. A question carrying one of
# these cannot be answered from the employee's file alone, however personal it sounds:
# "how many of my 34 sick days were at half pay" needs the pay bands, and "was my claim
# within policy" needs the cap it is being judged against.
POLICY_JUDGEMENT_PATTERN = re.compile(
    r"\b(polic\w+|rule\w*|entitle\w*|eligib\w*|allowed|permitted|cap|caps|capped"
    r"|limit\w*|threshold\w*|band\w*|rate\w*|tranche\w*|half\s+pay|full\s+pay"
    r"|notice|approv\w*|qualif\w*|carry[- ]?over|forfeit\w*|within\s+policy"
    r"|supposed\s+to|should\s+(?:i|have)|am\s+i\s+able)\b"
    r"|سياس|قاعد|مسموح|يحق|استحق|حد\s*أقصى|نصف\s+الأجر",
    re.IGNORECASE,
)

# Words that point at something recorded about a specific employee.
#
# The list is added to whenever a question that was plainly about the asker fails to
# match. "Trace my reporting line to the top" matched nothing here, so it was sent to the
# policy documents and answered "I cannot trace this from the policy extracts" — a
# question about the org chart, looked up in the rule book. `test_the_router_asks_for_the
# _right_facts` walks every scenario question through this, so the next gap is a failing
# test rather than a bad answer in front of a client.
PERSONAL_SUBJECT_PATTERN = re.compile(
    r"\b(balance|remaining|left|manager|probation|entitle\w*|accrued|carry[- ]?over"
    r"|days?\s+off|service|report(?:s|ing|ed)?|reporting\s+line|line\s+manager"
    r"|record|grade|claim\w*|expense\w*|request\w*|used|taken|absence|sick"
    r"|leaves?|paid|pay|approv\w*|class|flight|fly|travel|trip|per\s+diem"
    r"|remote|wfh|work\s+from\s+home|working\s+from\s+home|eligib\w*|entitle\w*"
    r"|start(?:ed|ing)?\s+date|job\s+title|department)\b"
    r"|رصيد|مدير|إجاز|تجربة|سجل|مطالب|درجت|خدمت|عن\s*بُ?عد|البيت|المنزل|بدل",
    re.IGNORECASE,
)


# Words that name a rule, a limit or an eligibility test — something only the policy
# documents can settle. A question can carry these AND be about the person asking, and
# then it needs both sources.
POLICY_SUBJECT_PATTERN = re.compile(
    r"\b(polic\w*|rule|entitle\w*|eligib\w*|allowed|permitted|cap|caps|capped|limit\w*"
    r"|threshold\w*|notice|approv\w*|within|qualif\w*|band\w*|rate|rates|pay|paid"
    r"|full\s+pay|half\s+pay|unpaid|carry[- ]?over|forfeit\w*|deadline)\b"
    r"|سياس|قاعد|يحق|مسموح|حد|نسب|مدفوع|موافق",
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
    required_evidence = _include_the_policy_when_a_rule_is_in_question(part, required_evidence)
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
    elif required_evidence == RequiredEvidence.HR_DATA and POLICY_JUDGEMENT_PATTERN.search(
        question
    ):
        # The mirror image of the line above, and it was missing for a long time. Routing
        # would add the employee's record to a policy question but never add the policy to
        # a question about the record, so "how many of my 34 sick days were paid at half
        # pay?" fetched the 34 and none of the rules that decide how they were paid. The
        # answer was that it could not confirm anything — while sitting on half the
        # evidence.
        required_evidence = RequiredEvidence.BOTH

    # Added to what the model asked for, not used only when it asked for nothing.
    #
    # "How many annual leave days am I entitled to?" was routed with years_of_service
    # alone. The record then described Sara by her length of service and not by her
    # entitlement, so the only entitlement in front of the model was the policy ladder —
    # and it answered 21 where her contract says 24, fluently and wrongly. The model had
    # named a field, so the fallback never ran; it was one field short, which is the
    # failure the routing instructions already call the common mistake.
    #
    # Over-reading is close to harmless here: every field is the caller's own, and the
    # enum is the authorisation boundary either way.
    for field in _fields_the_question_points_at(question):
        if field not in requested_fields:
            requested_fields.append(field)

    # If asking generally about leaves/balances without specifying "annual" or "sick", fetch both:
    is_specific_annual = bool(re.search(r"\bannual\b|السنوي", question, re.I))
    is_specific_sick = bool(re.search(r"\bsick\b|medical\b|مرض", question, re.I))
    if not is_specific_annual and not is_specific_sick:
        if HrDataField.ANNUAL_LEAVE_BALANCE in requested_fields and HrDataField.SICK_LEAVE_BALANCE not in requested_fields:
            requested_fields.append(HrDataField.SICK_LEAVE_BALANCE)
        if HrDataField.SICK_LEAVE_BALANCE in requested_fields and HrDataField.ANNUAL_LEAVE_BALANCE not in requested_fields:
            requested_fields.append(HrDataField.ANNUAL_LEAVE_BALANCE)

    return required_evidence, requested_fields


def _include_the_policy_when_a_rule_is_in_question(
    question: str, required_evidence: RequiredEvidence
) -> RequiredEvidence:
    """
    The mirror of the rule above, which was missing for a long time.

    Its counterpart adds the employee's record to a question routed at the policy. Nothing
    did the reverse, so a question routed at the record could never pick up the rule it
    had to be judged against. "How many of my 34 sick days were paid at half pay?" read
    the record, found 34 days, and never fetched the pay bands that answer the question —
    the assistant then said it could not confirm it, while the table sat unretrieved.

    Six questions needing both sources were put to the router and four came back naming
    one. This is the backstop for the two that a better model still gets wrong.
    """
    if required_evidence != RequiredEvidence.HR_DATA:
        return required_evidence
    if not POLICY_SUBJECT_PATTERN.search(question):
        return required_evidence

    logger.info("The record alone cannot settle this: adding the policy documents")
    return RequiredEvidence.BOTH


def _fields_the_question_points_at(question: str) -> list[HrDataField]:
    """
    What the words of the question say the answer will need.

    It used to fall back to the profile — job title, department, grade — whatever the
    question was about. So "how does my balance compare with last year" was answered from
    a record that had been asked for everything except the balances, and the assistant
    reported that the information was unavailable while it sat one field away.

    The profile is returned only when nothing at all is recognised, so that a question
    reading as personal always reads something. When the subject IS recognised, adding
    the profile as well would be noise.
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
