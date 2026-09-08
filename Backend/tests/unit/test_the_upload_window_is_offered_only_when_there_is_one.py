"""
"Can I submit the docs?"

The upload prompt used to be offered to anybody who asked. Shamma has no education
allowance and was told "the window lists what your claim still needs" about a claim that
does not exist. So was Tariq, who left in July and whose record still carries a plan he is
no longer eligible for. So, once they were added, were the four new joiners — who need the
visa window, not this one.

Checking the plan on the record catches Shamma and misses Tariq: a leaver's plan is a
leftover, and only HCS-11 knows the claim is gone. So the question put to HCS-11 is what
cases the person actually has, which answers "is there anything to send?" and "which
window?" in one call.

`read_school_claims` and `read_visa_case` are patched here so the tests state their own
facts and never depend on HCS-11 being up.
"""

import pytest

from app.domain.enums import AnswerStatus, QuestionIntent
from app.workflow.nodes import finish_turn

AN_OPEN_CLAIM = {"case_id": "CASE0003", "child_name": "Layla", "status": "Under Review",
                 "payment_status": "Not Ready"}
A_PAID_CLAIM = {"case_id": "CASE0009", "child_name": "Omar", "status": "Approved",
                "payment_status": "Paid"}
A_VISA_CASE = {"case_id": "VISA0001", "plan_name": "Employment visa — degree required",
               "status": "Ready for the PRO"}


@pytest.fixture
def hcs11(monkeypatch):
    """Say what HCS-11 holds for this person, without needing HCS-11."""
    def holding(*, school=(), visa=()):
        monkeypatch.setattr(finish_turn, "read_school_claims", lambda _: school)
        monkeypatch.setattr(finish_turn, "read_visa_case", lambda _: visa)
    return holding


def asked_to_submit(plan="EDU_STANDARD", language="en"):
    return {
        "employee_id": "EMP007",
        "employee_question": "can I submit the docs",
        "requested_language": language,
        "employee_facts": {"education_plan_code": plan},
    }


def offers_the_button(reply) -> bool:
    """
    The interface draws the button off the intent label. A reply that reports an ordinary
    question draws none — which is the whole mechanism, so it is what the tests assert.
    """
    return reply.get("question_intent") is None


# ── when there is something to send ──────────────────────────────────────────


def test_an_open_claim_still_gets_the_window(hcs11):
    hcs11(school=[AN_OPEN_CLAIM])

    reply = finish_turn.generate_document_upload_prompt(asked_to_submit())

    assert offers_the_button(reply)
    assert "Upload Documents" in reply["final_answer"]


def test_a_paid_claim_is_closed_and_does_not_count(hcs11):
    """The upload window filters these out too, so the chat must not promise one."""
    hcs11(school=[A_PAID_CLAIM])

    reply = finish_turn.generate_document_upload_prompt(asked_to_submit())

    assert not offers_the_button(reply)


def test_one_open_claim_among_closed_ones_is_enough(hcs11):
    hcs11(school=[A_PAID_CLAIM, AN_OPEN_CLAIM])

    assert offers_the_button(finish_turn.generate_document_upload_prompt(asked_to_submit()))


# ── when there is not ────────────────────────────────────────────────────────


def test_no_education_allowance_is_told_so_and_gets_no_button(hcs11):
    """Shamma. The case this was reported on."""
    hcs11(school=[], visa=[])

    reply = finish_turn.generate_document_upload_prompt(asked_to_submit(plan="NONE"))

    assert not offers_the_button(reply)
    assert "no education allowance" in reply["final_answer"]
    assert "Upload Documents" not in reply["final_answer"]
    assert reply["action_payload"] is None


def test_a_plan_with_no_open_claim_is_told_something_different(hcs11):
    """
    Tariq. His record still says Standard, so a check against the plan would have offered
    him the window. Only HCS-11 knows the claim is gone.
    """
    hcs11(school=[], visa=[])

    reply = finish_turn.generate_document_upload_prompt(asked_to_submit(plan="EDU_STANDARD"))

    assert not offers_the_button(reply)
    assert "no open claim" in reply["final_answer"]
    assert "no education allowance" not in reply["final_answer"]


def test_a_new_joiner_is_told_theirs_is_a_visa_case(hcs11):
    hcs11(school=[], visa=[A_VISA_CASE])

    reply = finish_turn.generate_document_upload_prompt(asked_to_submit(plan="NONE"))

    assert not offers_the_button(reply)
    assert "visa" in reply["final_answer"].lower()
    assert "Upload Documents" not in reply["final_answer"]


@pytest.mark.parametrize("plan", ["NONE", "", None])
def test_every_way_of_recording_no_plan_is_read_the_same(hcs11, plan):
    hcs11(school=[], visa=[])

    reply = finish_turn.generate_document_upload_prompt(asked_to_submit(plan=plan))

    assert "no education allowance" in reply["final_answer"]


def test_the_refusal_is_written_in_the_employees_language(hcs11):
    hcs11(school=[], visa=[])

    reply = finish_turn.generate_document_upload_prompt(
        asked_to_submit(plan="NONE", language="ar")
    )

    assert "بدل تعليم" in reply["final_answer"]


# ── when HCS-11 cannot be asked ──────────────────────────────────────────────


def test_an_unreachable_service_does_not_block_somebody_who_may_have_a_claim(hcs11):
    """
    Fails open on purpose. The window reports a connection failure clearly itself, and
    turning away an employee who does have a claim is the worse mistake.
    """
    hcs11(school=None, visa=None)

    reply = finish_turn.generate_document_upload_prompt(asked_to_submit())

    assert offers_the_button(reply)
    assert "Upload Documents" in reply["final_answer"]


def test_a_definite_answer_from_either_side_is_still_believed(hcs11):
    """One service answering and the other failing is not the same as neither answering."""
    hcs11(school=[], visa=None)

    assert not offers_the_button(finish_turn.generate_document_upload_prompt(asked_to_submit()))


# ── what the reply reports about itself ──────────────────────────────────────


def test_the_reply_is_verified_rather_than_a_refusal(hcs11):
    """
    It is a correct answer to what was asked, not a failure. Reporting it as refused would
    label it "not in scope" in the interface, which it is not.
    """
    hcs11(school=[], visa=[])

    reply = finish_turn.generate_document_upload_prompt(asked_to_submit(plan="NONE"))

    assert reply["answer_status"] == AnswerStatus.VERIFIED.value
    assert reply["question_intent"] == QuestionIntent.HR_QUESTION.value
