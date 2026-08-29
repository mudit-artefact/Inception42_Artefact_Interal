"""
A record holds more than one leave year, and the right one has to be chosen.

Adding last year's balances so that "how does this year compare?" could be answered
introduced a second row per leave type. The reader took whichever row came last, which
was the *previous* year — so the assistant confidently reported a balance that was a year
out of date. Nothing failed; the number was simply wrong.

This is the same shape as the sick-leave tranche bug: several rows match a loose test,
and the loop assigns rather than chooses.
"""

import pytest

from app.database.tables import Employee, LeaveBalance
from app.repositories.employee_repository import get_employee_facts


@pytest.fixture
def employee_with_two_leave_years(temporary_database):
    """One employee, this year and last, with deliberately different balances."""
    session = temporary_database()
    try:
        session.query(LeaveBalance).delete()
        session.query(Employee).delete()
        session.add(Employee(
            user_id="EMP900", name="Two Years", name_ar="سنتان", role="Consultant",
            job_title="Consultant", department="Strategy", grade="Grade 4",
            email="two.years@hcservices.ae", start_date="2022-01-01", years_of_service=4,
            probation_status="Passed", manager_name="A Manager",
        ))
        session.flush()
        # Last year, deliberately listed after this year so "the last row wins" fails.
        session.add(LeaveBalance(employee_id="EMP900", leave_type="Annual leave",
                                 entitled_days=24, used_days=9, remaining_days=15,
                                 carry_over_days=3, year=2026))
        session.add(LeaveBalance(employee_id="EMP900", leave_type="Annual leave",
                                 entitled_days=24, used_days=22, remaining_days=2,
                                 carry_over_days=0, year=2025))
        session.commit()
        yield
    finally:
        session.close()


def test_the_current_year_balance_is_reported(employee_with_two_leave_years, temporary_database):
    session = temporary_database()
    try:
        facts = get_employee_facts(session, "EMP900")
    finally:
        session.close()

    assert facts.annual_leave_balance == 15, "last year's balance was reported as this year's"
    assert facts.carry_over_days == 3


def test_both_years_are_still_available_to_read(employee_with_two_leave_years, temporary_database):
    """
    The older year is kept, not filtered away: comparing this year with last is one of
    the questions the record exists to answer.
    """
    session = temporary_database()
    try:
        facts = get_employee_facts(session, "EMP900")
    finally:
        session.close()

    years = {balance.year for balance in facts.leave_balances}
    assert years == {2025, 2026}


def test_sick_leave_sums_its_tranches_rather_than_taking_the_last(temporary_database):
    """
    Ninety days held as three rows. Assigning instead of summing reported whatever was
    left of the unpaid tranche — a number that then went into every citation.
    """
    session = temporary_database()
    try:
        facts = get_employee_facts(session, "EMP001")
    finally:
        session.close()

    assert facts.sick_leave_balance == 80, "10 of 90 days used, so 80 remain"
