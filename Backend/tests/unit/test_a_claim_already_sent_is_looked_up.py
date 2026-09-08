"""
"Was my application submitted successfully?"

The answer was the Upload Documents button — the same button the employee had just used.
Two things were wrong with it.

The step matched status questions against a list of about thirty spellings of them:
"submitted successfully", "are they approved", "when will". An employee who wrote
"successfuly" with one l matched none of them and got the plain upload prompt. One who
spelled it correctly got a fixed paragraph that told them to click the button anyway and
promised a review in "2-3 business days" — a figure typed into a Python file, grounded in
nothing.

Neither is the upload step's job. Where a claim has got to is a fact about the employee,
so it is read from HCS-11, authorised, cited and checked like every other fact about
them. HCS-11 already published it and HCS-01 already knew how to ask; nothing asked.
"""

import dataclasses

import pytest

from app.domain.employee_facts import EmployeeFacts, SchoolClaim
from app.domain.enums import HrDataField
from app.workflow import prompts
from app.workflow.evidence_formatting import format_employee_facts

RECORD = dict(
    employee_id="EMP001", name="Alia Al Suwaidi", name_in_arabic="", role="",
    job_title="", department="", grade="", email="", phone="", location="",
    start_date="", years_of_service=1, probation_status="", manager_name="",
    manager_email="", manager_role="", employment_fraction=1.0,
    annual_leave_balance=0, sick_leave_balance=0, carry_over_days=0,
)

APPROVED = SchoolClaim(
    case_id="CASE0001", child_name="Zayed Al Suwaidi", academic_year="2026–2027",
    status="Approved", recommendation="approve", submitted_on="2026-09-07",
    submission_deadline="2026-10-15", approved_on="2026-09-07",
    payment_status="Ready", awaiting_review=False,
)

NEEDS_MORE = SchoolClaim(
    case_id="CASE0002", child_name="Fatima Al Suwaidi", academic_year="2026–2027",
    status="Under Review", recommendation="request_documents", submitted_on="2026-09-08",
    submission_deadline="2026-10-15", payment_status="Not Ready", awaiting_review=True,
)


def shown(claims):
    facts = EmployeeFacts(**RECORD, school_claims=claims)
    return format_employee_facts(facts, [HrDataField.SCHOOL_CLAIM_STATUS])


def test_each_childs_claim_is_named_with_where_it_stands():
    said = shown([APPROVED, NEEDS_MORE])

    assert "Zayed Al Suwaidi" in said and "Approved" in said
    assert "Fatima Al Suwaidi" in said and "Under Review" in said
    assert "2026-10-15" in said


def test_it_says_when_the_employee_still_has_something_to_do():
    """
    The difference an employee actually needs. "Under Review" alone does not say whether
    the ball is with them or with a reviewer, and those need opposite actions.
    """
    assert "further documents have been requested" in shown([NEEDS_MORE])
    assert "nothing further needed from the employee" in shown(
        [dataclasses.replace(NEEDS_MORE, recommendation="approve")]
    )


def test_no_claim_and_no_answer_are_not_the_same_thing():
    """
    The distinction this rests on. Telling somebody who has submitted a claim that they
    have none, because another service was briefly unreachable, is the one wrong answer
    that matters here.
    """
    unreachable = shown(None)
    none_submitted = shown([])

    assert "could not be reached" in unreachable
    assert "no claim has been submitted" not in unreachable
    assert "no claim has been submitted" in none_submitted


def test_the_reviewers_working_is_not_shown_to_the_employee():
    """
    HCS-11's internal routing verdict, its rule codes and the reviewer's name are its
    working, not the employee's business — so they are not carried into the record at all.
    """
    carried = {each.name for each in dataclasses.fields(SchoolClaim)}

    assert not carried & {"assigned_reviewer", "route", "rules_outcome",
                          "matching_outcome", "rule_results", "employee_issues"}


def test_the_field_is_on_the_authorisation_list():
    """
    Which is what makes it citable and checkable. A fact reached outside that list is a
    fact no permission was granted for.
    """
    assert HrDataField.SCHOOL_CLAIM_STATUS in set(HrDataField)
    assert "school_claim_status" in prompts.SOURCE_ROUTING_INSTRUCTIONS


def test_the_classifier_is_told_a_sent_claim_is_a_question_not_an_upload():
    guidance = prompts.QUERY_UNDERSTANDING_INSTRUCTIONS

    assert "was my application submitted?" in guidance
    assert "already made" in guidance.lower()


@pytest.mark.parametrize(
    "message",
    [
        "was my app submitted successfuly ?",
        "was my application submitted successfully?",
        "are my documents reviewed?",
        "I want to upload my school documents",
    ],
)
def test_the_upload_step_has_only_one_reply_left(message):
    """
    It used to hold a second reply for status questions and a list of about thirty
    spellings to find it by, so the answer turned on how the employee spelled
    "successfully". Whatever reaches this step now gets the button and nothing else — and
    in particular never the "2-3 business days" that used to be typed into it.
    """
    from app.workflow.nodes.finish_turn import generate_document_upload_prompt

    answer = generate_document_upload_prompt({"employee_question": message})["final_answer"]

    assert answer in (prompts.DOCUMENT_UPLOAD_RESPONSE,
                      prompts.DOCUMENT_UPLOAD_RESPONSE_WITH_FILES)
    assert "business days" not in answer


@pytest.mark.parametrize(
    "claims",
    [None, [], [APPROVED], [APPROVED, NEEDS_MORE]],
)
def test_the_claims_survive_being_stored_and_read_back(claims):
    """
    The record crosses the conversation's saved state as a dictionary. An earlier field
    was lost exactly here, and None must survive as None — it is not the same as [].
    """
    facts = EmployeeFacts(**RECORD, school_claims=claims)

    assert EmployeeFacts.from_dictionary(facts.as_dictionary()).school_claims == claims
