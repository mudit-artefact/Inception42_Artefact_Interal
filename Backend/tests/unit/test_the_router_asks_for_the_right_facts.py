"""
A field that is not asked for is not read.

Routing names which of the employee's facts an answer may use, and anything unnamed is
left out of the prompt entirely. When the model named nothing at all, the fallback used
to be the profile — job title, department, grade — whatever the question was about. So
"how does my balance compare with last year" was answered from a record deliberately
stripped of the balances, and the assistant reported the information was unavailable.
"""

import pytest

from app.domain.enums import HrDataField
from app.workflow.nodes.route_subqueries import _fields_the_question_points_at


@pytest.mark.parametrize(
    "question, needed",
    [
        ("How does my leave balance this year compare with last year?",
         HrDataField.ANNUAL_LEAVE_BALANCE),
        ("How many sick days do I have left?", HrDataField.SICK_LEAVE_BALANCE),
        ("Who approved my January leave?", HrDataField.RECENT_LEAVE_REQUESTS),
        ("Which of my expense claims did Fatima approve?", HrDataField.RECENT_EXPENSE_CLAIMS),
        ("Who is my line manager?", HrDataField.LINE_MANAGER),
        ("Am I still on probation?", HrDataField.PROBATION_STATUS),
        ("Can I fly business class?", HrDataField.EMPLOYEE_PROFILE),
        ("كم رصيدي من الإجازات؟", HrDataField.ANNUAL_LEAVE_BALANCE),
    ],
)
def test_the_guess_covers_what_the_question_is_about(question, needed):
    assert needed in _fields_the_question_points_at(question)


def test_something_unrecognised_still_reads_the_profile():
    """A guess that returns nothing would read no record at all."""
    assert _fields_the_question_points_at("tell me about myself") == [
        HrDataField.EMPLOYEE_PROFILE
    ]


def test_every_field_the_routing_prompt_describes_is_a_field_that_exists():
    """
    The instructions describe each label so the model can choose between them. A label
    described but not defined would be requested and then silently dropped.
    """
    from app.workflow.prompts import SOURCE_ROUTING_INSTRUCTIONS

    for field in HrDataField:
        assert f"- {field.value}:" in SOURCE_ROUTING_INSTRUCTIONS, (
            f"{field.value} is readable but the router is never told what is in it"
        )


# ── Recognising that a question is about the person asking ───────────────────


def _reads_as_being_about_the_asker(question: str) -> bool:
    """The two patterns that together decide a question is personal, as routing uses them."""
    from app.workflow.nodes.route_subqueries import (
        FIRST_PERSON_PATTERN,
        PERSONAL_SUBJECT_PATTERN,
    )

    return bool(FIRST_PERSON_PATTERN.search(question)) and bool(
        PERSONAL_SUBJECT_PATTERN.search(question)
    )


@pytest.mark.parametrize(
    "question",
    [
        "Trace my reporting line all the way to the top.",
        "Who do I report to?",
        "How many annual days have I used, and how many are left?",
        "Give me a summary of my record.",
        "My February London claim was AED 950 a night. Was that within policy?",
        "I need to fly to London for three nights. What cabin class do I travel in?",
        "كم يوم إجازة سنوية أستحق؟",
        "هل أقدر أشتغل من البيت يوم واحد في الأسبوع؟",
    ],
)
def test_a_question_about_the_asker_is_recognised_as_one(question):
    """
    Missing one of these sends a question about the employee to the policy documents.

    "Trace my reporting line to the top" matched nothing and was answered "I cannot trace
    this from the policy extracts" — the org chart, looked up in the rule book. The
    Arabic entries are here because Arabic marks the first person on the verb rather than
    with a separate word, so a list of possessive nouns misses the most natural way to
    ask about your own leave.
    """
    assert _reads_as_being_about_the_asker(question)


@pytest.mark.parametrize(
    "question",
    [
        "What is Fatima Al Qubaisi's remaining annual leave balance?",
        "What is Aisha Al Mazrouei's probation status?",
        "What is the carry-over limit?",
        "How many days of maternity leave are allowed?",
    ],
)
def test_a_question_about_somebody_else_is_not(question):
    """
    The widening above must not turn another person's record into the caller's own.

    This is the half that matters for privacy: the pattern decides whether to read the
    employee record at all, and a colleague's name is not a licence to read it.
    """
    assert not _reads_as_being_about_the_asker(question)


# ── Reaching the policy from a question about your own record ────────────────


@pytest.mark.parametrize(
    "question",
    [
        "How many of my 34 sick days were paid at half pay?",
        "Was my February London claim of AED 950 a night within policy?",
        "Who had to approve my AED 1,200 claim from November 2025?",
        "Am I eligible to work from home two days a week?",
        "What notice do I need for my December leave?",
        "How many days am I entitled to?",
    ],
)
def test_a_question_judged_against_a_rule_reaches_the_policy(question):
    """
    Routing adds the employee's record to a policy question. This is the other direction.

    Without it, a question about your own record could never pick up the rule it has to be
    judged against: "how many of my 34 sick days were at half pay?" fetched the 34 and
    none of the pay bands, and the assistant said it could not confirm anything while
    holding half the evidence.
    """
    from app.domain.enums import RequiredEvidence
    from app.workflow.nodes.route_subqueries import (
        _include_personal_record_when_asked_about_oneself,
    )

    required_evidence, _ = _include_personal_record_when_asked_about_oneself(
        question, RequiredEvidence.HR_DATA, [HrDataField.ANNUAL_LEAVE_BALANCE]
    )

    assert required_evidence == RequiredEvidence.BOTH


@pytest.mark.parametrize(
    "question",
    [
        "Who is my line manager?",
        "What is the status of my October leave request?",
        "Give me a summary of my record.",
    ],
)
def test_a_plain_lookup_is_left_alone(question):
    """
    The widening must not send every question to the policy documents as well.

    A search that is never needed costs time on every turn and puts extracts in front of
    the model that have nothing to do with the question.
    """
    from app.domain.enums import RequiredEvidence
    from app.workflow.nodes.route_subqueries import (
        _include_personal_record_when_asked_about_oneself,
    )

    required_evidence, _ = _include_personal_record_when_asked_about_oneself(
        question, RequiredEvidence.HR_DATA, [HrDataField.EMPLOYEE_PROFILE]
    )

    assert required_evidence == RequiredEvidence.HR_DATA
