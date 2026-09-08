"""
Somebody who has accepted an offer and not started.

HCS-11 calls them "Onboarding" and opens a visa case for them. They are on the same list
as everybody else and may ask anything they like, but there is no leave record to act on
and no number to quote about one.

Two things are easy to get wrong here and both are covered below. The first is telling
somebody who has submitted their passport that they have no case, because the verification
service happened to be unreachable. The second is quoting a leave balance to somebody who
has not begun to accrue one — which the code did, inventing twenty days out of nothing.
"""

import dataclasses

import pytest

from app.database.seed_employees import build_seed_employees
from app.domain.employee_facts import EmployeeFacts, VisaCase
from app.domain.enums import FallbackReason, HrDataField, QuestionIntent
from app.services.citation_builder import build_employee_record_citation
from app.workflow.evidence_formatting import format_employee_facts
from app.workflow.routing_rules import decide_after_understanding

RECORD = dict(
    employee_id="EMP015", name="Daniel Okonkwo", name_in_arabic="دانيال أوكونكو",
    role="Senior Consultant", job_title="Senior Consultant", department="Client Delivery",
    grade="Grade 5", email="daniel.okonkwo@hcservices.ae", phone="", location="",
    start_date="2026-11-15", years_of_service=0, probation_status="Not started",
    manager_name="Sultan Al Neyadi", manager_email="", manager_role="Manager",
    employment_fraction=1.0, annual_leave_balance=0, sick_leave_balance=0, carry_over_days=0,
)

STANDARD_ROUTE = VisaCase(
    case_id="VISA0003",
    plan_name="Employment visa — no degree required",
    status="Awaiting Submission",
    submission_deadline="2026-10-07",
    required_documents=("passport", "photograph", "job_offer"),
    missing_documents=("passport", "photograph", "job_offer"),
)


def facts(*, status="Onboarding", cases=None):
    return EmployeeFacts(**RECORD, employment_status=status, visa_cases=cases)


# ── the visa case ────────────────────────────────────────────────────────────


def test_the_case_names_the_route_and_what_is_still_outstanding():
    said = format_employee_facts(facts(cases=[STANDARD_ROUTE]), [HrDataField.VISA_CASE_STATUS])

    assert "no degree required" in said
    assert "Awaiting Submission" in said
    assert "still outstanding" in said
    assert "2026-10-07" in said


def test_the_route_decides_the_documents_not_the_policys_first_table():
    """
    Daniel is on the route that needs no academic certificate. An answer that lists four
    documents has read the policy and not his case, which is the whole point of holding
    the case as a fact about him.
    """
    said = format_employee_facts(facts(cases=[STANDARD_ROUTE]), [HrDataField.VISA_CASE_STATUS])

    assert "passport copy" in said and "photograph" in said and "signed job-offer form" in said
    assert "academic certificate" not in said


def test_nothing_outstanding_is_said_plainly():
    ready = dataclasses.replace(
        STANDARD_ROUTE, status="Ready for the PRO", missing_documents=(), submitted_on="2026-09-07"
    )
    said = format_employee_facts(facts(cases=[ready]), [HrDataField.VISA_CASE_STATUS])

    assert "nothing outstanding" in said
    assert "still outstanding" not in said


def test_no_case_and_no_answer_are_not_the_same_thing():
    """The distinction the whole three-state convention exists for."""
    unreachable = format_employee_facts(facts(cases=None), [HrDataField.VISA_CASE_STATUS])
    none_open = format_employee_facts(facts(cases=[]), [HrDataField.VISA_CASE_STATUS])

    assert "could not be reached" in unreachable
    assert "no visa case" not in unreachable
    assert "no visa case" in none_open


def test_the_services_own_working_is_not_carried_into_the_record():
    """
    The routing verdict, the check codes, the reviewer and the nationality read off the
    passport are HCS-11's business. They are not on the dataclass at all, so they cannot
    reach an answer by accident.
    """
    carried = {field.name for field in dataclasses.fields(VisaCase)}

    assert not carried & {"route", "outcome", "checks", "nationality",
                          "assigned_reviewer", "legal_entity", "job_title"}


@pytest.mark.parametrize("cases", [None, [], [STANDARD_ROUTE]])
def test_the_case_survives_being_stored_and_read_back(cases):
    """None must survive as None: it is not the same as an empty list."""
    stored = facts(cases=cases).as_dictionary()

    assert EmployeeFacts.from_dictionary(stored).visa_cases == cases


# ── no number about leave they have not begun to accrue ──────────────────────


def test_a_new_joiner_is_not_given_a_leave_balance():
    """
    This used to report twenty annual days and ten sick days for anybody with no balance
    rows — figures nobody granted and no row held. Zero would be no better: it reads as an
    entitlement spent rather than one that has not started.
    """
    said = format_employee_facts(
        facts(), [HrDataField.ANNUAL_LEAVE_BALANCE, HrDataField.SICK_LEAVE_BALANCE]
    )

    # No quantity of leave at all — not the invented twenty, and not a bare zero. The
    # start date is a date, not a balance, so it is allowed to carry digits.
    from app.workflow.answer_validation import QUANTITY_PATTERN

    assert not [match.group(0) for match in QUANTITY_PATTERN.finditer(said)]
    assert "none yet" in said
    assert "2026-11-15" in said


def test_an_employee_who_has_started_still_gets_their_balance():
    started = dataclasses.replace(
        facts(status="Active"), annual_leave_balance=15, sick_leave_balance=80
    )
    said = format_employee_facts(
        started, [HrDataField.ANNUAL_LEAVE_BALANCE, HrDataField.SICK_LEAVE_BALANCE]
    )

    assert "15 days" in said and "80 days" in said
    assert "none yet" not in said


def test_the_citation_does_not_print_a_balance_either():
    """The sources panel is read as closely as the answer, and said 0 days remaining."""
    citation = build_employee_record_citation(facts())

    assert "days remaining" not in citation.snippet
    assert "Not started yet" in citation.snippet


def test_the_profile_says_they_have_not_started_rather_than_when_they_started():
    said = format_employee_facts(facts(), [HrDataField.EMPLOYEE_PROFILE])

    assert "Has not started yet" in said
    assert "2026-11-15" in said


# ── they may ask anything; they may act on nothing ───────────────────────────


@pytest.mark.parametrize(
    "intent",
    [
        QuestionIntent.APPLY_LEAVE,
        QuestionIntent.CANCEL_LEAVE,
        QuestionIntent.CHECK_LEAVE_STATUS,
        QuestionIntent.APPROVE_LEAVE,
        QuestionIntent.REJECT_LEAVE,
    ],
)
def test_no_leave_action_reaches_its_step(intent):
    """
    Refused at the fork, not at the write. Applying reads the request with the model,
    checks it against policy and pauses twice before it would reach a refusal — so guarding
    only at the end would let a new joiner pick dates and confirm a card first.
    """
    where = decide_after_understanding(
        {
            "question_intent": intent,
            "employee_facts": {"employment_status": "Onboarding"},
            "clarification_round": 0,
        }
    )

    assert where == "build_safe_fallback"


@pytest.mark.parametrize(
    "intent", [QuestionIntent.HR_QUESTION, QuestionIntent.DOCUMENT_UPLOAD]
)
def test_asking_and_sending_documents_are_untouched(intent):
    """The guard refuses the action, not the person."""
    where = decide_after_understanding(
        {
            "question_intent": intent,
            "employee_facts": {"employment_status": "Onboarding"},
            "clarification_round": 0,
        }
    )

    assert where != "build_safe_fallback"


def test_an_employee_who_has_started_is_unaffected():
    where = decide_after_understanding(
        {
            "question_intent": QuestionIntent.APPLY_LEAVE,
            "employee_facts": {"employment_status": "Active"},
            "clarification_round": 0,
        }
    )

    assert where == "handle_leave_application"


def test_the_refusal_says_why_and_offers_what_is_left():
    from app.workflow.nodes.finish_turn import build_safe_fallback

    for language, expected in (("en", "not started"), ("ar", "لم تباشر")):
        reply = build_safe_fallback(
            {
                "question_intent": QuestionIntent.APPLY_LEAVE,
                "employee_facts": {"employment_status": "Onboarding"},
                "requested_language": language,
            }
        )

        assert reply["fallback_reason"] == FallbackReason.NOT_STARTED_YET.value
        assert expected in reply["final_answer"]
        assert reply["action_payload"] is None


# ── the seed itself ──────────────────────────────────────────────────────────


def test_the_joining_cohort_is_seeded_the_way_the_guard_expects():
    joining = [
        record for record in build_seed_employees()
        if record["employee"].employment_status == "Onboarding"
    ]

    assert {record["employee"].user_id for record in joining} == {
        "EMP013", "EMP014", "EMP015", "EMP016"
    }
    for record in joining:
        employee = record["employee"]
        # No leave rows, because none exist before a first day.
        assert record["balances"] == []
        assert record["leave_requests"] == []
        # An outside email address in an answer is rejected by the answer check, so their
        # own address must be a company one.
        assert employee.email.endswith("@hcservices.ae"), employee.user_id
        assert employee.probation_status == "Not started"


# ── the classifier has to know a visa question is an HR question ─────────────


def test_visa_is_named_as_an_hr_subject():
    """
    It was not, and the list of HR subjects is what the classifier reads. In English the
    model inferred it anyway; in Arabic it did not, and "أين وصلت معاملة تأشيرتي؟" was
    refused as though somebody had asked about the weather. Naming the subject fixed both.
    """
    from app.workflow import prompts

    guidance = prompts.QUERY_UNDERSTANDING_INSTRUCTIONS

    assert "employment visa documents" in guidance
    assert "تأشيرتي" in guidance


def test_the_assistant_says_it_handles_visa_documents():
    """It used to say the opposite out loud, and send visa questions to People & Culture."""
    from app.workflow import prompts

    for language in ("en", "ar"):
        text = prompts.WHAT_I_CAN_DO[language]
        assert "visa" in text.lower() or "تأشيرة" in text

    # Renewal and family sponsorship are still outside HC-PC-013, and still disclaimed.
    assert "renewal" in prompts.WHAT_I_CAN_DO["en"].lower()
