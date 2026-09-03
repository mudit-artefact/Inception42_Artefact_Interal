"""Writing the starting employee and HCS-11 records into an empty database."""

import logging

from sqlalchemy.orm import Session

from app.database.seed_employees import build_seed_employees, build_seed_hcs11_master_data
from app.database.tables import (
    AcademicCycle,
    BenefitPlanRule,
    Dependent,
    Employee,
    ExpenseClaim,
    LeaveBalance,
    LeaveRequest,
    ManagerHistory,
    Notification,
    SchoolVerificationCase,
)

logger = logging.getLogger(__name__)


def seed_database(session: Session, force: bool = False) -> int:
    """
    Add the starting employees and HCS-11 master data, unless the database already has some.

    Returns how many employees were added.
    """
    existing_count = session.query(Employee).count()
    if existing_count > 0 and not force:
        logger.info(f"The database already holds {existing_count} employees; leaving it alone")
        return 0

    if force and existing_count > 0:
        logger.info("Clearing the database before seeding it again")
        _delete_everything(session)

    # 1. Master Data (Plans & Cycles)
    master_data = build_seed_hcs11_master_data()
    for rule in master_data["plan_rules"]:
        session.merge(rule)
    for cycle in master_data["cycles"]:
        session.merge(cycle)
    session.flush()

    # 2. Employees & Related HR records
    employees_to_add = build_seed_employees()
    for record in employees_to_add:
        employee = record["employee"]
        session.add(employee)
        session.flush()

        for related_records in (
            record["balances"],
            record["manager_history"],
            record["leave_requests"],
            record["expense_claims"],
        ):
            for related_record in related_records:
                related_record.employee_id = employee.user_id
                session.add(related_record)

    session.flush()

    # 3. Dependents & School Verification Cases
    for dependent in master_data["dependents"]:
        session.merge(dependent)
    session.flush()

    for case in master_data["cases"]:
        session.merge(case)

    session.commit()
    logger.info(f"Seeded {len(employees_to_add)} employees and {len(master_data['dependents'])} dependents")
    return len(employees_to_add)


def _delete_everything(session: Session) -> None:
    """Remove records child-first, so no row is orphaned mid-delete."""
    for table in (
        Notification,
        SchoolVerificationCase,
        Dependent,
        AcademicCycle,
        BenefitPlanRule,
        ExpenseClaim,
        LeaveRequest,
        ManagerHistory,
        LeaveBalance,
        Employee,
    ):
        session.query(table).delete()
    session.commit()
