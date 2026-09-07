"""
What one employee is actually entitled to towards their children's schooling.

Until this existed the assistant answered the question from a sentence typed into the
workflow: "up to AED 45,000 per eligible child", said to everyone who asked. AED 45,000 is
a real figure — it is the ceiling on the Enhanced plan — but it is not most people's
ceiling. Of the twelve seeded employees, six are on Standard at AED 25,000 and one has no
education plan at all, so seven of the twelve were told a limit far above their own.

The plan rules carry their own effective dates, so the answer says which year it is for
rather than implying it is permanent.
"""

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.database.engine import SessionLocal
from app.database.tables import BenefitPlanRule, Dependent, Employee

logger = logging.getLogger(__name__)

# The plan code meaning "this employee has no education allowance". It is a real row in
# the rules table with a limit of zero, not a missing one.
NO_EDUCATION_PLAN = "NONE"


def get_education_entitlement(
    employee_id: str, session: Optional[Session] = None
) -> dict[str, Any]:
    """
    This employee's education plan, its ceiling, and what it asks them to send in.

    Returns `entitled: False` when they are on no plan, so the caller states that rather
    than quoting somebody else's number.
    """
    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        employee = (
            session.query(Employee).filter(Employee.user_id == employee_id).first()
        )
        if employee is None:
            return {"entitled": False, "reason": "no such employee"}

        plan_code = employee.benefit_plan_code
        if not plan_code or plan_code == NO_EDUCATION_PLAN:
            return {
                "entitled": False,
                "reason": "no education plan",
                "plan_code": plan_code,
            }

        rule = (
            session.query(BenefitPlanRule)
            .filter(BenefitPlanRule.plan_code == plan_code)
            .first()
        )
        if rule is None:
            logger.warning(f"{employee_id} is on plan {plan_code}, which has no rule row")
            return {"entitled": False, "reason": "no rule for plan", "plan_code": plan_code}

        enrolled_children = (
            session.query(Dependent)
            .filter(
                Dependent.employee_id == employee_id,
                Dependent.relationship_type == rule.eligible_relationship,
                Dependent.dependent_status == rule.dependent_status_required,
            )
            .all()
        )

        return {
            "entitled": True,
            "plan_code": rule.plan_code,
            "plan_name": rule.plan_name,
            "annual_limit_aed": rule.annual_limit_aed,
            "required_documents": [
                document.strip()
                for document in (rule.required_documents or "").split("|")
                if document.strip()
            ],
            "academic_year_start": rule.effective_start,
            "academic_year_end": rule.effective_end,
            "children_on_record": [
                {
                    "name": f"{child.first_name} {child.last_name}",
                    "enrolment": child.school_enrolment_status,
                }
                for child in enrolled_children
            ],
        }
    finally:
        if close_session:
            session.close()
