"""
Reading one employee's record outside a web request.

The workflow runs its own steps rather than handling an HTTP request, so it opens and
closes a session here instead of receiving one through a dependency.
"""

from typing import Any

from app.database.engine import SessionLocal
from app.domain.employee_facts import EmployeeFacts
from app.repositories import employee_repository


def get_employee_facts_for(employee_id: str) -> EmployeeFacts:
    """One employee's record. Raises EmployeeNotFoundError if there is no such person."""
    session = SessionLocal()
    try:
        return employee_repository.get_employee_facts(session, employee_id)
    finally:
        session.close()


def get_employee_record_as_dictionary(employee_id: str) -> dict[str, Any]:
    """The same record in its dictionary form."""
    return get_employee_facts_for(employee_id).as_dictionary()
