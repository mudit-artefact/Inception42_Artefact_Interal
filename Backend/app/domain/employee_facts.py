"""
Everything the assistant is allowed to know about one employee.

This replaces an untyped dictionary that was passed between the database, the prompt
builder and the API. The dictionary had two different shapes depending on whether the
employee was found, and callers reached into it by string key, so a missing key surfaced
as a crash deep inside prompt formatting.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LeaveBalance:
    leave_type: str
    entitled_days: int
    used_days: int
    remaining_days: int
    carry_over_days: int
    unit: str
    # A record holds more than one leave year. Without this the rows are
    # indistinguishable, and last year's balance can be read as this year's.
    year: int = 0
    # 100, 50 or 0 for the sick leave tranches; None where pay rate does not apply.
    pay_rate_pct: int | None = None
    # Earned so far this year, which is less than entitled for anyone part-way through
    # their first year (HC-PC-001 §1.3.1).
    accrued_days: float = 0.0


@dataclass(frozen=True)
class ManagerChange:
    previous_manager: str
    current_manager: str
    effective_date: str
    reason: str


@dataclass(frozen=True)
class LeaveRequest:
    leave_type: str
    start_date: str
    end_date: str
    days: int
    status: str
    approver: str
    notes: str


@dataclass(frozen=True)
class ExpenseClaim:
    category: str
    amount_aed: float
    claim_date: str
    status: str
    approver: str
    # What was bought — the city, the nights, the head count. Without it the hotel caps
    # and per-head limits cannot be checked against the claim.
    description: str = ""
    # The clause the claim was assessed under, so "why was this rejected?" is answered
    # from the record rather than inferred.
    policy_reference: str = ""


@dataclass(frozen=True)
class EmployeeFacts:
    """One employee's record, as read from the HR database."""

    employee_id: str
    name: str
    name_in_arabic: str
    role: str
    job_title: str
    department: str
    grade: str
    email: str
    phone: str
    location: str
    start_date: str
    years_of_service: int
    probation_status: str
    manager_name: str
    manager_email: str
    manager_role: str
    # 1.0 is full time. Annual leave is pro-rated against it (HC-PC-001 §1.2.3).
    employment_fraction: float
    annual_leave_balance: int
    sick_leave_balance: int
    carry_over_days: int
    leave_balances: list[LeaveBalance] = field(default_factory=list)
    manager_history: list[ManagerChange] = field(default_factory=list)
    recent_leave_requests: list[LeaveRequest] = field(default_factory=list)
    recent_expense_claims: list[ExpenseClaim] = field(default_factory=list)

    @classmethod
    def from_dictionary(cls, stored: dict[str, Any]) -> "EmployeeFacts":
        """Rebuild a record from the dictionary form held in a conversation's state."""
        return cls(
            employee_id=stored["user_id"],
            name=stored["name"],
            name_in_arabic=stored["name_ar"],
            role=stored["role"],
            job_title=stored["job_title"],
            department=stored["department"],
            grade=stored["grade"],
            email=stored["email"],
            phone=stored["phone"],
            location=stored["location"],
            start_date=stored["start_date"],
            years_of_service=stored["years_of_service"],
            probation_status=stored["probation_status"],
            manager_name=stored["manager_name"],
            manager_email=stored["manager_email"],
            manager_role=stored["manager_role"],
            employment_fraction=stored.get("employment_fraction", 1.0),
            annual_leave_balance=stored["annual_leave_balance"],
            sick_leave_balance=stored["sick_leave_balance"],
            carry_over_days=stored["carry_over_days"],
            leave_balances=[
                LeaveBalance(
                    leave_type=balance["type"],
                    entitled_days=balance["entitled"],
                    used_days=balance["used"],
                    remaining_days=balance["remaining"],
                    carry_over_days=balance["carry_over"],
                    unit=balance["unit"],
                    year=balance.get("year", 0),
                    pay_rate_pct=balance.get("pay_rate_pct"),
                    accrued_days=balance.get("accrued", 0.0),
                )
                for balance in stored.get("balances", [])
            ],
            manager_history=[
                ManagerChange(**change) for change in stored.get("manager_history", [])
            ],
            recent_leave_requests=[
                LeaveRequest(**request) for request in stored.get("recent_leave_requests", [])
            ],
            recent_expense_claims=[
                ExpenseClaim(
                    category=claim["category"],
                    amount_aed=claim["amount_aed"],
                    claim_date=claim["date"],
                    status=claim["status"],
                    approver=claim["approver"],
                    description=claim.get("description", ""),
                    policy_reference=claim.get("policy_reference", ""),
                )
                for claim in stored.get("recent_expense_claims", [])
            ],
        )

    def as_dictionary(self) -> dict[str, Any]:
        """The shape older callers, including the prompt builder, still expect."""
        return {
            "user_id": self.employee_id,
            "name": self.name,
            "name_ar": self.name_in_arabic,
            "role": self.role,
            "job_title": self.job_title,
            "department": self.department,
            "grade": self.grade,
            "email": self.email,
            "phone": self.phone,
            "location": self.location,
            "start_date": self.start_date,
            "years_of_service": self.years_of_service,
            "probation_status": self.probation_status,
            "manager_name": self.manager_name,
            "manager_email": self.manager_email,
            "manager_role": self.manager_role,
            "employment_fraction": self.employment_fraction,
            "annual_leave_balance": self.annual_leave_balance,
            "sick_leave_balance": self.sick_leave_balance,
            "carry_over_days": self.carry_over_days,
            "balances": [
                {
                    "type": balance.leave_type,
                    "entitled": balance.entitled_days,
                    "used": balance.used_days,
                    "remaining": balance.remaining_days,
                    "carry_over": balance.carry_over_days,
                    "unit": balance.unit,
                    "year": balance.year,
                    "pay_rate_pct": balance.pay_rate_pct,
                    "accrued": balance.accrued_days,
                }
                for balance in self.leave_balances
            ],
            "manager_history": [
                {
                    "previous_manager": change.previous_manager,
                    "current_manager": change.current_manager,
                    "effective_date": change.effective_date,
                    "reason": change.reason,
                }
                for change in self.manager_history
            ],
            "recent_leave_requests": [
                {
                    "leave_type": request.leave_type,
                    "start_date": request.start_date,
                    "end_date": request.end_date,
                    "days": request.days,
                    "status": request.status,
                    "approver": request.approver,
                    "notes": request.notes,
                }
                for request in self.recent_leave_requests
            ],
            "recent_expense_claims": [
                {
                    "category": claim.category,
                    "amount_aed": claim.amount_aed,
                    "date": claim.claim_date,
                    "status": claim.status,
                    "approver": claim.approver,
                    "description": claim.description,
                    "policy_reference": claim.policy_reference,
                }
                for claim in self.recent_expense_claims
            ],
        }
