"""
The assistant may only use what it is shown, and it was being shown very little.

The database held who approved each leave request and each expense claim, what each claim
was for, the clause it was assessed under, and the balances for more than one year. None
of it reached the prompt. So the assistant answered "that information is not available in
your record" about facts that were sitting in the record, one field away.

Two separate mistakes made that happen, and both are covered here: the fields were not
rendered, and the ones that were rendered did not survive the trip through a saved
conversation.
"""

import pytest

from app.database.employee_lookup import get_employee_facts_for
from app.domain.employee_facts import EmployeeFacts
from app.domain.enums import HrDataField
from app.workflow.evidence_formatting import format_employee_facts

EVERY_FIELD = [field.value for field in HrDataField]


@pytest.fixture
def ahmed(temporary_database):
    return get_employee_facts_for("EMP001")


def shown(facts, fields=None) -> str:
    return format_employee_facts(facts, fields or EVERY_FIELD)


def test_who_approved_a_leave_request_is_shown(ahmed):
    """"Who approved my January leave?" is unanswerable without it."""
    assert "approved by Maitha Al Mazrouei" in shown(ahmed)


def test_who_decided_an_expense_claim_is_shown(ahmed):
    assert "decided by Maitha Al Mazrouei" in shown(ahmed)
    # Not every claim was decided by the same person, and the difference is the answer
    # to "which of these did Rashid approve?".
    assert "decided by Rashid Al Ketbi" in shown(ahmed)


def test_what_a_claim_was_for_and_the_clause_it_was_judged_by_are_shown(ahmed):
    rendered = shown(ahmed)

    assert "AED 225 per head" in rendered, "the detail a per-head cap is checked against"
    assert "HC-PC-005 §5.5.1" in rendered, "why a claim was allowed or refused"


def test_more_than_one_leave_year_is_shown(ahmed):
    """"How does this year compare with last?" needs both years, not just a total."""
    rendered = shown(ahmed)

    assert "2026 Annual leave" in rendered and "24 entitled, 12 used, 15 remaining" in rendered
    assert "2025 Annual leave" in rendered and "24 entitled, 21 used, 3 remaining" in rendered


def test_the_sick_leave_tranches_are_shown(temporary_database):
    """Ninety days at three pay rates, not one number."""
    rendered = shown(get_employee_facts_for("EMP006"))

    assert "paid at 100%" in rendered
    assert "paid at 50%" in rendered
    assert "15 entitled, 15 used, 0 remaining" in rendered


def test_a_part_time_pattern_is_shown(temporary_database):
    """Otherwise a 14.4-day entitlement looks like an error rather than a calculation."""
    rendered = shown(get_employee_facts_for("EMP007"))

    assert "0.6 of full time" in rendered


def test_a_single_balance_is_broken_down_too(temporary_database):
    rendered = shown(get_employee_facts_for("EMP004"), [HrDataField.ANNUAL_LEAVE_BALANCE.value])

    assert "21 entitled" in rendered
    assert "6 used" in rendered


def test_an_entitlement_that_disagrees_with_the_policy_ladder_is_shown(temporary_database):
    rendered = shown(get_employee_facts_for("EMP008"), [HrDataField.ANNUAL_LEAVE_BALANCE.value])

    assert "26 entitled" in rendered
    assert "5 used" in rendered


def test_a_part_time_entitlement_is_shown_as_the_record_holds_it(temporary_database):
    rendered = shown(get_employee_facts_for("EMP007"), [HrDataField.ANNUAL_LEAVE_BALANCE.value])

    assert "14 entitled" in rendered
    assert "4 used" in rendered


def test_none_of_it_is_lost_on_the_way_through_a_saved_conversation(ahmed):
    """
    The record is stored as a dictionary in the conversation's state and rebuilt from it
    before the prompt is written. A field the dictionary does not carry is a field the
    model never sees, however well the database holds it.
    """
    rebuilt = EmployeeFacts.from_dictionary(ahmed.as_dictionary())

    assert shown(rebuilt) == shown(ahmed)
