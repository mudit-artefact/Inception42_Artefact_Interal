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
# A real visa case always says what is still wanted and what came back wrong. This
# fixture said neither, which let "you have documents outstanding" be tested without
# anything outstanding ever being true — the exact claim that turned out to be false on a
# new joiner who had sent all four.
A_VISA_CASE = {"case_id": "VISA0001", "plan_name": "Employment visa — degree required",
               "status": "Awaiting Submission",
               "missing_documents": ("passport", "photograph"), "problems": ()}
A_FINISHED_VISA_CASE = {"case_id": "VISA0002", "plan_name": "Employment visa — degree required",
                        "status": "Ready for the PRO",
                        "missing_documents": (), "problems": ()}
A_VISA_CASE_WITH_A_FAULT = {"case_id": "VISA0003", "plan_name": "Employment visa",
                            "status": "Under Review", "missing_documents": (),
                            "problems": ("The photograph cannot be used: the background is blue.",)}


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


def test_a_new_joiner_is_handed_to_the_visa_window(hcs11):
    """
    It used to apologise and send them to People & Culture, because the window did not
    exist. Now it opens it — carried on the action payload, the way five of the six cards
    the interface can draw are chosen.
    """
    hcs11(school=[], visa=[A_VISA_CASE])

    reply = finish_turn.generate_document_upload_prompt(asked_to_submit(plan="NONE"))

    assert reply["action_payload"] == {
        "action_type": "VISA_DOCUMENT_UPLOAD",
        "case_id": "VISA0001",
    }
    assert "visa" in reply["final_answer"].lower()
    # Not the school button: that one is drawn off the intent label, and a new joiner has
    # no school claim to send anything to.
    assert not offers_the_button(reply)
    assert "Upload Documents" not in reply["final_answer"]


def test_the_visa_window_is_never_offered_to_somebody_with_no_visa_case(hcs11):
    hcs11(school=[], visa=[])

    reply = finish_turn.generate_document_upload_prompt(asked_to_submit(plan="NONE"))

    assert reply["action_payload"] is None


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


# ── the window they asked for, not the one they happen to have ────────────────
#
# A new joiner typed "I want to submit for schooling" and was handed the visa window
# without a word. They had already been told, one turn earlier, that schooling was not on
# their package — and then watched a window open as though it were. The step chose from
# what the person *had*; nothing in it ever read what they had *asked for*.
#
# `document_kind` is that missing half. `understand_query` reads it off their words; the
# lookup below still answers what exists. Both are needed, and neither substitutes.


def naming(kind, plan="NONE", language="en"):
    """The same request, with the kind the employee named attached."""
    return {**asked_to_submit(plan=plan, language=language), "document_kind": kind}


def test_asking_for_schooling_does_not_open_the_visa_window(hcs11):
    """The bug, exactly: schooling asked for, visa window given, question unanswered."""
    hcs11(school=[], visa=[A_VISA_CASE])

    reply = finish_turn.generate_document_upload_prompt(naming("school"))

    assert "no education allowance" in reply["final_answer"].lower()
    assert not offers_the_button(reply), "the school button must not be drawn"


def test_it_still_says_the_visa_documents_are_waiting(hcs11):
    """
    Refusing and then stopping would be honest and unhelpful. They have documents
    outstanding and we know it.
    """
    hcs11(school=[], visa=[A_VISA_CASE])

    reply = finish_turn.generate_document_upload_prompt(naming("school"))

    assert reply["action_payload"]["action_type"] == "VISA_DOCUMENT_UPLOAD"
    assert reply["action_payload"]["case_id"] == "VISA0001"


def test_the_refusal_comes_before_the_offer(hcs11):
    """
    Order is the whole point. An offer first reads as the answer, and somebody walks away
    believing they submitted for schooling.
    """
    hcs11(school=[], visa=[A_VISA_CASE])

    answer = finish_turn.generate_document_upload_prompt(naming("school"))["final_answer"]

    assert answer.lower().index("no education allowance") < answer.lower().index("visa")


def test_asking_for_visa_opens_the_visa_window(hcs11):
    hcs11(school=[], visa=[A_VISA_CASE])

    reply = finish_turn.generate_document_upload_prompt(naming("visa"))

    assert reply["action_payload"]["action_type"] == "VISA_DOCUMENT_UPLOAD"


def test_asking_for_visa_is_not_answered_with_the_school_window(hcs11):
    """The same fault mirrored: an employee with a claim asking about visa documents."""
    hcs11(school=[AN_OPEN_CLAIM], visa=[])

    reply = finish_turn.generate_document_upload_prompt(naming("visa", plan="EDU_STANDARD"))

    assert not offers_the_button(reply), "the school button must not be drawn"
    assert reply["action_payload"] is None


def test_naming_nothing_still_opens_whichever_they_have(hcs11):
    """
    Somebody who says only "upload my documents" has named nothing to honour, and there
    is no point asking which when only one is possible.
    """
    hcs11(school=[], visa=[A_VISA_CASE])

    reply = finish_turn.generate_document_upload_prompt(naming(None))

    assert reply["action_payload"]["action_type"] == "VISA_DOCUMENT_UPLOAD"


def test_naming_schooling_with_a_real_claim_opens_the_school_window(hcs11):
    hcs11(school=[AN_OPEN_CLAIM], visa=[])

    reply = finish_turn.generate_document_upload_prompt(naming("school", plan="EDU_STANDARD"))

    assert offers_the_button(reply), "she has a claim; the button belongs here"


def test_the_refusal_is_written_in_arabic_when_the_question_was(hcs11):
    hcs11(school=[], visa=[A_VISA_CASE])

    answer = finish_turn.generate_document_upload_prompt(
        naming("school", language="ar")
    )["final_answer"]

    assert "بدل تعليم" in answer


# ── "outstanding" is a claim, and claims get checked ──────────────────────────
#
# A new joiner who had sent all four of her visa documents asked to submit school
# documents and was told "you do have employment visa documents outstanding", with a
# button to send them again. Her case was complete and already with HC Services.
#
# The message had never been conditional on anything but the case existing. It is the
# same fault as every other one this file guards against — a sentence asserting something
# nobody looked up — and it was written into the fix for the bug above it.


def test_nothing_is_called_outstanding_when_everything_has_arrived(hcs11):
    hcs11(school=[], visa=[A_FINISHED_VISA_CASE])

    reply = finish_turn.generate_document_upload_prompt(naming("school"))

    answer = reply["final_answer"].lower()
    # Not the word itself — the reply says "there is nothing outstanding", which is the
    # point. What must not appear is the claim that documents are.
    assert "do have employment visa documents outstanding" not in answer
    assert "have all arrived" in answer
    assert reply["action_payload"] is None


def test_a_finished_case_is_not_offered_the_window_again(hcs11):
    hcs11(school=[], visa=[A_FINISHED_VISA_CASE])

    reply = finish_turn.generate_document_upload_prompt(naming("visa"))

    assert reply["action_payload"] is None, "nothing left to send, so no button"
    assert "nothing further to send" in reply["final_answer"].lower()


def test_a_document_that_came_back_wrong_still_counts_as_outstanding(hcs11):
    """
    Everything has arrived and one of them is no good. That is something to do, and the
    window is how it gets done.
    """
    hcs11(school=[], visa=[A_VISA_CASE_WITH_A_FAULT])

    reply = finish_turn.generate_document_upload_prompt(naming("visa"))

    assert reply["action_payload"]["action_type"] == "VISA_DOCUMENT_UPLOAD"


def test_the_refusal_is_still_first_when_the_visa_case_is_done(hcs11):
    hcs11(school=[], visa=[A_FINISHED_VISA_CASE])

    answer = finish_turn.generate_document_upload_prompt(naming("school"))["final_answer"].lower()

    assert answer.index("no education allowance") < answer.index("visa")


# ── the refusal answers the question that was asked ──────────────────────────
#
# Both directions, together, because the bug was the difference between them. Asking for
# schooling without a claim named the schooling and then offered the visa; asking for the
# visa without a case named neither and explained an education allowance instead — the
# schooling refusal, handed to somebody who had said nothing about schooling.


def test_asking_for_the_visa_without_a_case_says_so_first(hcs11):
    """The reported fault: a visa question was answered with a schooling explanation."""
    hcs11(school=[AN_OPEN_CLAIM], visa=[])

    answer = finish_turn.generate_document_upload_prompt(
        {**asked_to_submit(), "document_kind": "visa"}
    )

    assert "no employment visa case" in answer["final_answer"].lower()
    # The old answer opened on the education allowance and never mentioned the visa.
    assert not answer["final_answer"].lower().startswith("you do have an education")


def test_the_school_claim_is_offered_after_the_refusal_not_instead_of_it(hcs11):
    hcs11(school=[AN_OPEN_CLAIM], visa=[])

    answer = finish_turn.generate_document_upload_prompt(
        {**asked_to_submit(), "document_kind": "visa"}
    )

    said = answer["final_answer"]
    assert said.lower().index("visa") < said.lower().index("schooling")
    # The school button is the one card drawn from the intent rather than the payload.
    assert answer["question_intent"] == QuestionIntent.DOCUMENT_UPLOAD.value


def test_no_visa_case_and_no_claim_offers_nothing(hcs11):
    hcs11(school=[], visa=[])

    answer = finish_turn.generate_document_upload_prompt(
        {**asked_to_submit(plan="NONE"), "document_kind": "visa"}
    )

    assert answer["action_payload"] is None
    assert "no employment visa case" in answer["final_answer"].lower()


def test_a_paid_claim_is_not_offered_as_somewhere_to_send_visa_documents(hcs11):
    """A closed claim is not an open one, in this direction as in the other."""
    hcs11(school=[A_PAID_CLAIM], visa=[])

    answer = finish_turn.generate_document_upload_prompt(
        {**asked_to_submit(), "document_kind": "visa"}
    )

    assert answer["action_payload"] is None
    assert "schooling verification claim open" not in answer["final_answer"]


def test_hcs11_being_unreachable_does_not_deny_a_visa_case(hcs11):
    """
    `None` means it could not be asked.

    Telling somebody who has a case that they have none is the one wrong answer that
    matters here, and it is worse than a window that opens onto an error.
    """
    hcs11(school=None, visa=None)

    answer = finish_turn.generate_document_upload_prompt(
        {**asked_to_submit(), "document_kind": "visa"}
    )

    assert answer["action_payload"] is not None
    assert "no employment visa case" not in answer["final_answer"].lower()
