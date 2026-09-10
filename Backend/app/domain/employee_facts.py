"""
Everything the assistant is allowed to know about one employee.

This replaces an untyped dictionary that was passed between the database, the prompt
builder and the API. The dictionary had two different shapes depending on whether the
employee was found, and callers reached into it by string key, so a missing key surfaced
as a crash deep inside prompt formatting.
"""

from dataclasses import asdict, dataclass, field
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
class SchoolClaim:
    """
    One school verification claim, as HCS-11 holds it.

    Read from HCS-11 rather than the HR database, because HCS-11 owns it. Only what the
    employee is owed about their own claim is carried: the reviewer's name, the internal
    routing verdict and the rule codes stay where they are.
    """

    case_id: str
    child_name: str
    academic_year: str
    status: str
    recommendation: str = ""
    submitted_on: str = ""
    submission_deadline: str = ""
    approved_on: str = ""
    payment_status: str = ""
    awaiting_review: bool = False
    # What the claim still needs, and what is wrong with what arrived. The record used to
    # carry the status word and nothing else, so an employee whose claim was rejected
    # because the documents were for a different child could be told "Under Review" and
    # not one word about why. The upload panel showed all four documents in red while the
    # assistant, asked about the same claim, said everything was fine.
    required_documents: tuple[str, ...] = ()
    missing_documents: tuple[str, ...] = ()
    problems: tuple[str, ...] = ()


@dataclass(frozen=True)
class VisaCase:
    """
    A new joiner's employment visa case, as HCS-11 holds it.

    Read from HCS-11 rather than the HR database, and carrying only what the new joiner is
    owed about their own case. The reviewer, the internal routing verdict and the check
    codes stay where they are, exactly as with `SchoolClaim`.
    """

    case_id: str
    plan_name: str
    status: str
    submission_deadline: str = ""
    submitted_on: str = ""
    required_documents: tuple[str, ...] = ()
    missing_documents: tuple[str, ...] = ()
    problems: tuple[str, ...] = ()

    # ── the employment contract ──────────────────────────────────────────────
    #
    # Flat fields rather than a nested record, because this one is frozen and round-trips
    # through a JSON checkpoint: `from_dictionary` turns lists back into tuples but does
    # not rebuild a nested dataclass, so a nested contract would return as a plain dict and
    # compare unequal to the value that was stored.
    #
    # Read `contract_is_signed`, never `contract_signed_on`. HCS-11 fills the date whenever
    # a job-offer document exists at all — including an unsigned one the joiner uploaded
    # themselves, where it falls back to the day the file arrived. The flag is the one that
    # has consulted HCS-11's own OFFER_SIGNED check. Defaults are the "no contract known"
    # reading, which is what an HCS-11 predating this feature gives us.
    contract_prepared_on: str = ""
    contract_signed_on: str = ""
    contract_is_signed: bool = False
    contract_job_title: str = ""
    contract_start_date: str = ""
    contract_salary_aed: int | None = None


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
    # The education plan this employee is on, as a plan code — EDU_STANDARD,
    # EDU_ENHANCED, or NONE. The ceiling itself lives in the policy, not here.
    education_plan_code: str = ""
    leave_balances: list[LeaveBalance] = field(default_factory=list)
    manager_history: list[ManagerChange] = field(default_factory=list)
    recent_leave_requests: list[LeaveRequest] = field(default_factory=list)
    recent_expense_claims: list[ExpenseClaim] = field(default_factory=list)
    # "Active", "On Leave", "Terminated", or "Onboarding" for somebody who has accepted an
    # offer and not yet started. It rides inside employee_profile rather than taking an
    # allowlist entry of its own, because it is part of who somebody is rather than a
    # subject anybody asks about directly.
    employment_status: str = ""
    # None until HCS-11 has been asked, and after asking if it could not be reached. An
    # empty list means it answered and this employee has no claims — a different thing,
    # and the employee must not be told one when the truth is the other.
    school_claims: list[SchoolClaim] | None = None
    # The same three states, for the visa case of somebody who has not started.
    visa_cases: list[VisaCase] | None = None

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
            education_plan_code=stored.get("education_plan_code", ""),
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
            # .get with a default on both, not stored[...]: a conversation checkpointed
            # before these fields existed must still resume.
            employment_status=stored.get("employment_status", ""),
            school_claims=(
                # Lists back to tuples, as the visa cases below already do: the record is
                # frozen, and a claim rebuilt with a list where it declares a tuple is a
                # different value from the one that was stored.
                [
                    SchoolClaim(
                        **{
                            key: tuple(value) if isinstance(value, list) else value
                            for key, value in claim.items()
                        }
                    )
                    for claim in stored["school_claims"]
                ]
                if stored.get("school_claims") is not None
                else None
            ),
            visa_cases=(
                [
                    VisaCase(
                        **{
                            key: tuple(value) if isinstance(value, list) else value
                            for key, value in case.items()
                        }
                    )
                    for case in stored["visa_cases"]
                ]
                if stored.get("visa_cases") is not None
                else None
            ),
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
            "education_plan_code": self.education_plan_code,
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
            "employment_status": self.employment_status,
            # None survives the round trip, because "not asked" and "asked, and there are
            # none" are different answers and the reply turns on which one it is.
            "school_claims": (
                [asdict(claim) for claim in self.school_claims]
                if self.school_claims is not None
                else None
            ),
            "visa_cases": (
                [asdict(case) for case in self.visa_cases]
                if self.visa_cases is not None
                else None
            ),
        }
