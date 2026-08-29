"""
The two deterministic corrections applied after the model routes a question.

The model is good at spotting the policy angle and unreliable about two things: noticing
that a question is also about the person asking it, and knowing when to give up.
"""

import pytest

from app.domain.enums import HrDataField, RequiredEvidence
from app.workflow.nodes.route_subqueries import (
    _do_not_refuse_a_confident_hr_question,
    _include_personal_record_when_asked_about_oneself,
)


@pytest.mark.parametrize(
    "question",
    [
        "How many days do I have left?",
        "What is my annual leave balance?",
        "Who is my manager?",
        "كم رصيدي من الإجازات؟",
    ],
)
def test_a_question_about_oneself_also_reads_the_employees_record(question):
    evidence, fields = _include_personal_record_when_asked_about_oneself(
        question, RequiredEvidence.POLICY, []
    )

    assert evidence == RequiredEvidence.BOTH
    assert fields, "some part of the employee's record must be read"


def test_a_general_question_is_left_as_a_policy_question():
    evidence, fields = _include_personal_record_when_asked_about_oneself(
        "What is the carry over limit?", RequiredEvidence.POLICY, []
    )

    assert evidence == RequiredEvidence.POLICY
    assert fields == []


def test_a_personal_question_is_never_refused_outright():
    evidence, _ = _include_personal_record_when_asked_about_oneself(
        "What is my leave balance?", RequiredEvidence.UNSUPPORTED, []
    )

    assert evidence == RequiredEvidence.HR_DATA


def test_a_confident_hr_question_is_answered_rather_than_refused():
    """
    The refusal route is new and has no tuning behind it. Refusing something the previous
    system answered is a regression an employee notices immediately.
    """
    confident_hr_question = {"question_intent": "hr_question", "intent_confidence": 0.92}

    assert (
        _do_not_refuse_a_confident_hr_question(confident_hr_question, RequiredEvidence.UNSUPPORTED)
        == RequiredEvidence.POLICY
    )


def test_an_uncertain_question_may_still_be_refused():
    uncertain = {"question_intent": "hr_question", "intent_confidence": 0.4}

    assert (
        _do_not_refuse_a_confident_hr_question(uncertain, RequiredEvidence.UNSUPPORTED)
        == RequiredEvidence.UNSUPPORTED
    )


def test_only_allowed_employee_fields_can_be_requested():
    """
    The list of readable fields is the authorisation boundary. Anything outside it is
    dropped before the record is read, so the model cannot name a column or another
    person's record.
    """
    from pydantic import ValidationError

    from app.workflow.structured_outputs import SourceRoutingDecision

    with pytest.raises(ValidationError):
        SourceRoutingDecision.model_validate(
            {"required_evidence": "hr_data", "requested_hr_data_fields": ["salary"]}
        )

    allowed = SourceRoutingDecision.model_validate(
        {"required_evidence": "hr_data", "requested_hr_data_fields": ["annual_leave_balance"]}
    )
    assert allowed.requested_hr_data_fields == [HrDataField.ANNUAL_LEAVE_BALANCE]
