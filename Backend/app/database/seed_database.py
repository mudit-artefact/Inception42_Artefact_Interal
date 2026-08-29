"""Writing the starting employee records into an empty database."""

import logging

from sqlalchemy.orm import Session

from app.database.seed_employees import build_seed_employees
from app.database.tables import Employee, ExpenseClaim, LeaveBalance, LeaveRequest, ManagerHistory

logger = logging.getLogger(__name__)


def seed_database(session: Session, force: bool = False) -> int:
    """
    Add the starting employees, unless the database already has some.

    Returns how many employees were added.
    """
    existing_count = session.query(Employee).count()
    if existing_count > 0 and not force:
        logger.info(f"The database already holds {existing_count} employees; leaving it alone")
        return 0

    if force and existing_count > 0:
        logger.info("Clearing the database before seeding it again")
        _delete_everything(session)

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

    session.commit()
    logger.info(f"Seeded {len(employees_to_add)} employees")
    return len(employees_to_add)


def _delete_everything(session: Session) -> None:
    """Remove records child-first, so no row is orphaned mid-delete."""
    for table in (ExpenseClaim, LeaveRequest, ManagerHistory, LeaveBalance, Employee):
        session.query(table).delete()
    session.commit()
