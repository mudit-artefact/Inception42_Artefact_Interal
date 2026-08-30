"""
Reading and updating employee records.

Every function takes the database session it should use, so callers control the
transaction and tests can hand in a temporary database.
"""

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.errors import EmployeeNotFoundError
from app.database.tables import Employee, LeaveBalance as LeaveBalanceRow, ManagerHistory
from app.domain.employee_facts import (
    EmployeeFacts,
    ExpenseClaim,
    LeaveBalance,
    LeaveRequest,
    ManagerChange,
)

logger = logging.getLogger(__name__)

DEFAULT_ANNUAL_LEAVE_BALANCE = 20
DEFAULT_SICK_LEAVE_BALANCE = 10


def list_employee_identifiers(session: Session) -> list[str]:
    """Every employee identifier, in order."""
    return [
        employee.user_id for employee in session.query(Employee).order_by(Employee.user_id).all()
    ]


def get_employee_facts(session: Session, employee_id: str) -> EmployeeFacts:
    """
    One employee's full record.

    Raises EmployeeNotFoundError when there is no such employee. This used to return a
    made-up employee called "Employee" with twenty invented leave days, which meant an
    unknown identifier produced a confident answer built on fabricated facts, and the
    employee lookup endpoint answered 200 instead of 404.
    """
    employee = session.query(Employee).filter(Employee.user_id == employee_id).first()
    if employee is None:
        raise EmployeeNotFoundError(employee_id)

    leave_balances = [
        LeaveBalance(
            leave_type=balance.leave_type,
            entitled_days=balance.entitled_days,
            used_days=balance.used_days,
            remaining_days=balance.remaining_days,
            carry_over_days=balance.carry_over_days,
            unit=balance.unit,
            year=balance.year,
            pay_rate_pct=balance.pay_rate_pct,
            accrued_days=balance.accrued_days,
        )
        for balance in employee.leave_balances
    ]

    annual_leave_balance = DEFAULT_ANNUAL_LEAVE_BALANCE
    sick_leave_balance = DEFAULT_SICK_LEAVE_BALANCE
    carry_over_days = 0

    # A record holds more than one leave year, so the year has to be chosen rather than
    # arrived at. Picking whichever row happened to come last returned the *previous*
    # year's balance — a wrong number, quietly, where the old code merely had one row to
    # find. "The most recent year on file" rather than today's date, so the demonstration
    # data still answers correctly as it ages.
    current_leave_year = max((balance.year for balance in leave_balances), default=None)

    this_year = [balance for balance in leave_balances if balance.year == current_leave_year]
    annual_rows = [b for b in this_year if "annual" in b.leave_type.lower()]
    if annual_rows:
        annual_leave_balance = annual_rows[0].remaining_days
        carry_over_days = annual_rows[0].carry_over_days

    # Sick leave is one 90-day entitlement paid at three rates (HC-PC-002 §2.2.1), held
    # as one row per tranche. Summing matters: this used to assign rather than add, so
    # with three matching rows the last one won and the balance reported was whatever
    # remained of the *unpaid* tranche — a number printed into every citation.
    sick_tranches = [b for b in this_year if "sick" in b.leave_type.lower()]
    if sick_tranches:
        sick_leave_balance = sum(tranche.remaining_days for tranche in sick_tranches)

    return EmployeeFacts(
        employee_id=employee.user_id,
        name=employee.name,
        name_in_arabic=employee.name_ar,
        role=employee.role,
        job_title=employee.job_title or employee.role,
        department=employee.department,
        grade=employee.grade,
        email=employee.email,
        phone=employee.phone,
        location=employee.location,
        start_date=employee.start_date,
        years_of_service=employee.years_of_service,
        probation_status=employee.probation_status,
        manager_name=employee.manager_name,
        manager_email=employee.manager_email,
        manager_role=employee.manager_role,
        employment_fraction=employee.employment_fraction,
        annual_leave_balance=annual_leave_balance,
        sick_leave_balance=sick_leave_balance,
        carry_over_days=carry_over_days,
        leave_balances=leave_balances,
        manager_history=[
            ManagerChange(
                previous_manager=change.previous_manager,
                current_manager=change.current_manager,
                effective_date=change.effective_date,
                reason=change.change_reason,
            )
            for change in sorted(
                employee.manager_history, key=lambda change: change.effective_date, reverse=True
            )
        ],
        recent_leave_requests=[
            LeaveRequest(
                leave_type=request.leave_type,
                start_date=request.start_date,
                end_date=request.end_date,
                days=request.days_requested,
                status=request.status,
                approver=request.approver_name,
                notes=request.notes,
            )
            for request in sorted(
                employee.leave_requests, key=lambda request: request.start_date, reverse=True
            )
        ],
        recent_expense_claims=[
            ExpenseClaim(
                category=claim.category,
                amount_aed=claim.amount_aed,
                claim_date=claim.claim_date,
                status=claim.status,
                approver=claim.approver,
                description=claim.description,
                policy_reference=claim.policy_reference,
            )
            for claim in sorted(
                employee.expense_claims, key=lambda claim: claim.claim_date, reverse=True
            )
        ],
    )


def change_line_manager(
    session: Session,
    employee_id: str,
    manager_name: str,
    manager_email: str | None,
    manager_role: str,
    reason: str,
) -> dict:
    """Record a new line manager and keep the previous one in the history."""
    employee = session.query(Employee).filter(Employee.user_id == employee_id).first()
    if employee is None:
        raise EmployeeNotFoundError(employee_id)

    previous_manager = employee.manager_name
    effective_date = datetime.utcnow().strftime("%Y-%m-%d")

    employee.manager_name = manager_name
    employee.manager_email = manager_email or employee.manager_email
    employee.manager_role = manager_role
    session.add(
        ManagerHistory(
            employee_id=employee_id,
            previous_manager=previous_manager,
            current_manager=manager_name,
            effective_date=effective_date,
            change_reason=reason,
        )
    )
    session.commit()

    return {
        "employee_id": employee_id,
        "name": employee.name,
        "previous_manager": previous_manager,
        "current_manager": manager_name,
        "effective_date": effective_date,
        "change_reason": reason,
    }


def change_leave_balance(
    session: Session,
    employee_id: str,
    leave_type: str,
    remaining_days: int,
    used_days: int | None,
    carry_over_days: int | None,
) -> dict:
    """Adjust one of an employee's leave balances."""
    employee = session.query(Employee).filter(Employee.user_id == employee_id).first()
    if employee is None:
        raise EmployeeNotFoundError(employee_id)

    balance = (
        session.query(LeaveBalanceRow)
        .filter(
            LeaveBalanceRow.employee_id == employee_id,
            LeaveBalanceRow.leave_type.ilike(f"%{leave_type}%"),
        )
        .first()
    )
    if balance is None:
        raise EmployeeNotFoundError(f"{employee_id} has no '{leave_type}' balance")

    balance.remaining_days = remaining_days
    if used_days is not None:
        balance.used_days = used_days
    if carry_over_days is not None:
        balance.carry_over_days = carry_over_days
    session.commit()

    return {
        "employee_id": employee_id,
        "leave_type": balance.leave_type,
        "remaining_days": balance.remaining_days,
        "used_days": balance.used_days,
        "entitled_days": balance.entitled_days,
        "carry_over_days": balance.carry_over_days,
    }
