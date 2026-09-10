"""
Somebody whose employment has ended.

The mirror of `test_a_new_joiner_has_not_started`, and it did not exist. A live run put the
question to the running application as Tariq Al Balushi, who left in July: it created the
request, told him it had been submitted, and notified his former manager to approve it.

The guard beside this one had been written for new joiners and only ever learned the single
word "Onboarding". `employment_status` has four values, and the one that matters most here
is the third: **"On Leave" is an employee on holiday**, who must keep every one of these
abilities. A guard written as "anything that is not Active" would lock somebody out of the
system while they were using it, which is why each test below has its counterpart.
"""

import pytest

from app.domain.enums import FallbackReason, QuestionIntent
from app.workflow.routing_rules import decide_after_understanding

LEAVE_ACTIONS = [
    QuestionIntent.APPLY_LEAVE,
    QuestionIntent.CANCEL_LEAVE,
    QuestionIntent.CHECK_LEAVE_STATUS,
    QuestionIntent.APPROVE_LEAVE,
    QuestionIntent.REJECT_LEAVE,
]


def asked(intent, status):
    return decide_after_understanding(
        {
            "question_intent": intent,
            "employee_facts": {"employment_status": status},
            "clarification_round": 0,
        }
    )


@pytest.mark.parametrize("intent", LEAVE_ACTIONS)
def test_no_leave_action_reaches_its_step(intent):
    """
    Refused at the fork, before any of it runs.

    Applying reads the dates with the model, checks them against policy and pauses for a
    confirmation before it would reach the backstop — so a guard only at the write would
    let somebody who has left pick dates and confirm a card first.
    """
    assert asked(intent, "Terminated") == "build_safe_fallback"


@pytest.mark.parametrize("intent", LEAVE_ACTIONS)
def test_an_employee_on_holiday_is_not_caught_by_it(intent):
    """
    The trap in this fix, written down as a test.

    "On Leave" means an employee who is on leave right now. Every one of these actions is
    theirs to take, and the seed has somebody in exactly that state.
    """
    assert asked(intent, "On Leave") != "build_safe_fallback"


@pytest.mark.parametrize(
    "intent", [QuestionIntent.HR_QUESTION, QuestionIntent.DOCUMENT_UPLOAD]
)
def test_asking_a_policy_question_is_untouched(intent):
    """The guard refuses the action, not the person. A leaver may still ask what the rules are."""
    assert asked(intent, "Terminated") != "build_safe_fallback"


def test_the_refusal_says_what_happens_instead():
    """
    Not the new joiner's sentence with a word changed.

    A joiner is told to wait, because their leave is coming. Somebody who has left is not
    waiting for anything — HC-PC-001 §1.6.3 pays untaken leave in the final settlement — so
    the reply has to say where that is dealt with rather than leave them expecting a window.
    """
    from app.workflow.nodes.finish_turn import build_safe_fallback

    answer = build_safe_fallback(
        {
            "question_intent": QuestionIntent.APPLY_LEAVE,
            "employee_facts": {"employment_status": "Terminated"},
            "requested_language": "en",
        }
    )

    said = answer["final_answer"]
    assert "ended" in said.lower()
    assert "1.6.3" in said
    assert "not started" not in said.lower(), "that is the other refusal"


def test_the_arabic_refusal_is_arabic():
    from app.workflow.nodes.finish_turn import build_safe_fallback

    answer = build_safe_fallback(
        {
            "question_intent": QuestionIntent.APPLY_LEAVE,
            "employee_facts": {"employment_status": "Terminated"},
            "requested_language": "ar",
        }
    )

    assert any("؀" <= ch <= "ۿ" for ch in answer["final_answer"])


def test_the_two_refusals_are_told_apart():
    """Each status reaches its own reason, so neither is answered with the other's sentence."""
    from app.workflow.nodes.finish_turn import _infer_fallback_reason

    for status, expected in [
        ("Terminated", FallbackReason.HAS_LEFT.value),
        ("Onboarding", FallbackReason.NOT_STARTED_YET.value),
    ]:
        assert _infer_fallback_reason(
            {
                "question_intent": QuestionIntent.APPLY_LEAVE,
                "employee_facts": {"employment_status": status},
            }
        ) == expected


def test_the_seed_still_has_somebody_in_each_state():
    """
    The guard is only worth anything if somebody is in that state to catch.

    Both statuses this file is about are in the seeded data — a leaver and an employee on
    holiday — so a change that removed either would take the meaning out of these tests
    quietly rather than failing them.
    """
    from app.database.seed_employees import build_seed_employees

    statuses = {
        person["employee"].employment_status for person in build_seed_employees()
    }
    assert "Terminated" in statuses
    assert "On Leave" in statuses


def test_the_write_itself_refuses_even_if_the_router_is_bypassed(temporary_database):
    """
    The backstop, tested on its own.

    The router turns the question away first, and that is where a person meets this. But a
    refusal that lives only in the router is one new code path away from being gone, and
    the row is the thing that must not exist. So the validator refuses too, and this proves
    it without going through the router at all.
    """
    from app.services import leave_service
    from app.workflow.structured_outputs import LeaveApplicationDraft

    session = temporary_database()
    try:
        leaver = (
            session.query(leave_service.Employee)
            .filter(leave_service.Employee.employment_status == "Terminated")
            .first()
        )
        assert leaver is not None, "the seed no longer has anybody who has left"

        checked = leave_service.validate_leave_policy(
            employee_id=leaver.user_id,
            draft=LeaveApplicationDraft(
                leave_type="Annual leave",
                start_date="2027-01-18",
                end_date="2027-01-20",
            ),
            session=session,
        )

        assert any("employment has ended" in v.lower() for v in checked.violations), (
            f"nothing in {checked.violations} refuses a leaver"
        )
    finally:
        session.close()


# ── and their record is not quoted at them either ────────────────────────────
#
# Blocking the actions was not enough, and a live run proved it: asked how many days he had
# left, a leaver was told twenty-one. True of the row and false of him — those days were
# settled in his final pay months earlier. A balance question is not a leave *action*, so
# the guard above never saw it; it is an ordinary question answered from the record.
#
# The mirror of `test_a_new_joiner_is_not_given_a_leave_balance`, which exists because the
# same mistake was made at the other end of employment.

import dataclasses

from app.domain.employee_facts import EmployeeFacts
from app.domain.enums import HrDataField
from app.workflow.answer_validation import QUANTITY_PATTERN
from app.workflow.evidence_formatting import format_employee_facts

RECORD = dict(
    employee_id="EMP008", name="Tariq Al Balushi", name_in_arabic="طارق البلوشي",
    role="Consultant", job_title="Consultant", department="Client Delivery",
    grade="Grade 6", email="tariq@hcservices.ae", phone="", location="",
    start_date="2019-11-10", years_of_service=6, probation_status="Passed",
    manager_name="Maitha Al Mazrouei", manager_email="", manager_role="Executive Director",
    employment_fraction=1.0, annual_leave_balance=21, sick_leave_balance=15,
    carry_over_days=4,
)

BALANCE_FIELDS = [
    HrDataField.ANNUAL_LEAVE_BALANCE,
    HrDataField.SICK_LEAVE_BALANCE,
    HrDataField.CARRY_OVER_DAYS,
]


def record(status):
    return EmployeeFacts(**RECORD, employment_status=status)


def test_no_number_of_days_is_put_in_front_of_a_leaver():
    said = format_employee_facts(record("Terminated"), BALANCE_FIELDS)

    assert not [m.group(0) for m in QUANTITY_PATTERN.finditer(said)], (
        f"a quantity of leave survived into: {said}"
    )
    assert "21" not in said and "15" not in said


def test_it_says_what_happened_to_those_days_instead():
    """Silence would read as a system that lost his record. §1.6.3 is what actually happened."""
    said = format_employee_facts(record("Terminated"), BALANCE_FIELDS)

    assert "1.6.3" in said
    assert "final settlement" in said


def test_carried_days_go_too():
    """A leaver carries nothing into next year, and the row saying four is the same lie."""
    said = format_employee_facts(record("Terminated"), BALANCE_FIELDS)

    assert "Carried over" not in said


def test_an_employee_still_gets_every_figure():
    said = format_employee_facts(record("Active"), BALANCE_FIELDS)

    assert "21 days" in said
    assert "15 days" in said
    assert "Carried over from last year: 4 days" in said


def test_somebody_on_leave_still_gets_every_figure():
    """The trap again, at this layer: being on holiday is not having left."""
    said = format_employee_facts(record("On Leave"), BALANCE_FIELDS)

    assert "21 days" in said
    assert "Carried over" in said


def test_the_two_ends_of_employment_are_not_told_the_same_thing():
    joiner = format_employee_facts(
        dataclasses.replace(record("Onboarding"), start_date="2026-11-15"), BALANCE_FIELDS
    )
    leaver = format_employee_facts(record("Terminated"), BALANCE_FIELDS)

    assert "accrue" in joiner and "1.6.3" not in joiner
    assert "1.6.3" in leaver and "begins to accrue" not in leaver
