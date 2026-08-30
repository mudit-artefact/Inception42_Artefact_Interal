"""
Turning employee records into the profile the web interface shows.

This mapping used to be a private function inside the HTTP router module, imported by
three other modules including the agent — so the agent depended on the web layer just to
convert a record into a profile.
"""

from sqlalchemy.orm import Session

from app.domain.employee_facts import EmployeeFacts
from app.domain.policy_catalog import english_documents
from app.repositories import employee_repository
from app.schemas.employee import EmployeeProfile, LeaveBalanceItem, PolicyLink

PROBATION_IN_PROGRESS = "Active"


def list_employee_profiles(session: Session) -> list[EmployeeProfile]:
    """Every employee, as the sidebar's people switcher shows them."""
    return [
        build_profile(employee_repository.get_employee_facts(session, employee_id))
        for employee_id in employee_repository.list_employee_identifiers(session)
    ]


def get_employee_profile(session: Session, employee_id: str) -> EmployeeProfile:
    """One employee's profile. Raises EmployeeNotFoundError if there is no such person."""
    return build_profile(employee_repository.get_employee_facts(session, employee_id))


def build_profile(facts: EmployeeFacts) -> EmployeeProfile:
    """Present an employee's record as the profile the web interface reads."""
    return EmployeeProfile(
        user_id=facts.employee_id,
        id=facts.employee_id,
        name=facts.name,
        name_ar=facts.name_in_arabic,
        role=facts.role,
        jobTitle=facts.job_title,
        department=facts.department,
        grade=facts.grade,
        annual_leave_balance=facts.annual_leave_balance,
        sick_leave_balance=facts.sick_leave_balance,
        carry_over_days=facts.carry_over_days,
        probation_status=facts.probation_status,
        years_of_service=facts.years_of_service,
        manager=facts.manager_name,
        email=facts.email,
        start_date=facts.start_date,
        balances=_balances_for_the_current_leave_year(facts),
        policyLinks=choose_quick_links_for(facts.probation_status),
    )


def choose_quick_links_for(probation_status: str) -> list[PolicyLink]:
    """
    The handful of policies shown beside an employee's profile.

    Somebody still on probation is shown the probation policy; everybody else is shown
    the expenses policy in its place.
    """
    shown_topics = (
        ["probation", "annual", "sick", "remote"]
        if probation_status == PROBATION_IN_PROGRESS
        else ["annual", "sick", "remote", "expenses"]
    )
    documents_by_topic = {document.topic_key: document for document in english_documents()}
    return [
        PolicyLink(
            id=f"pol-{topic}",
            title=documents_by_topic[topic].title,
            section=documents_by_topic[topic].quick_link_section,
            url="#",
        )
        for topic in shown_topics
        if topic in documents_by_topic
    ]


def _balances_for_the_current_leave_year(facts: EmployeeFacts) -> list[LeaveBalanceItem]:
    """
    This year's balances only, newest year wins.

    The record keeps last year's rows so the assistant can answer "how does this compare
    with last year". The sidebar is a statement of where somebody stands today, and
    sending both years put two rows labelled "Annual leave" side by side with no year
    against either — one of them last year's, and neither of them explained. The
    assistant reads `facts.leave_balances` directly and is unaffected by this.
    """
    if not facts.leave_balances:
        return []

    current_year = max(balance.year for balance in facts.leave_balances)
    return [
        LeaveBalanceItem(
            type=balance.leave_type,
            used=balance.used_days,
            entitled=balance.entitled_days,
            remaining=balance.remaining_days,
            carry_over=balance.carry_over_days,
            year=balance.year,
            unit=balance.unit,
        )
        for balance in facts.leave_balances
        if balance.year == current_year
    ]
