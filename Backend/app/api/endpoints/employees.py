"""
The HR directory endpoints.

Replaces app/mock_omni.py, which was three things at once: a router, a schema module and
a mapper. Nothing here is mocked — it reads the real HR database — so the old name was
also misleading.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.engine import get_database_session
from app.repositories import employee_repository
from app.schemas.employee import (
    EmployeeProfile,
    LeaveRequestItem,
    PendingApprovalItem,
    UpdateLeaveBalanceRequest,
    UpdateManagerRequest,
)
from app.services import employee_directory_service, leave_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/omni", tags=["Omni HR Database"])


@router.get(
    "/employees",
    response_model=list[EmployeeProfile],
    summary="List every employee",
)
async def list_employees(
    session: Session = Depends(get_database_session),
) -> list[EmployeeProfile]:
    return employee_directory_service.list_employee_profiles(session)


@router.get(
    "/employee/{employee_id}",
    response_model=EmployeeProfile,
    summary="One employee's profile",
)
async def get_employee(
    employee_id: str,
    session: Session = Depends(get_database_session),
) -> EmployeeProfile:
    """Answers 404 when there is no such employee."""
    return employee_directory_service.get_employee_profile(session, employee_id.upper())


@router.get(
    "/employee/{employee_id}/leave-requests",
    response_model=list[LeaveRequestItem],
    summary="One employee's leave requests, newest first",
)
async def list_leave_requests(
    employee_id: str,
    session: Session = Depends(get_database_session),
) -> list[LeaveRequestItem]:
    """
    What this person has asked for. Every status, not only the ones still waiting.

    The rows have always been here; nothing served them. The assistant reads them as prose
    through `get_employee_facts`, and the same query answers this.
    """
    return [
        LeaveRequestItem(**request)
        for request in leave_service.get_leave_requests(employee_id.upper(), session=session)
    ]


@router.get(
    "/employee/{employee_id}/approvals",
    response_model=list[PendingApprovalItem],
    summary="Leave requests waiting on this person's decision",
)
async def list_pending_approvals(
    employee_id: str,
    session: Session = Depends(get_database_session),
) -> list[PendingApprovalItem]:
    """
    What this person has to decide. Empty for anybody who manages nobody.

    Reading only. Approving and rejecting stay where they are — reachable through the
    assistant, which only ever offers a manager the requests on their own list. Those
    functions do not check that the approver is entitled to the request they name, so a
    write route here would let anyone approve anything by guessing a number. That check is
    owed before this pair gains a sibling that writes.
    """
    return [
        PendingApprovalItem(**approval)
        for approval in leave_service.get_manager_pending_approvals(
            employee_id.upper(), session=session
        )
    ]


@router.patch(
    "/employees/{employee_id}/manager",
    summary="Change an employee's line manager",
)
async def update_manager(
    employee_id: str,
    request: UpdateManagerRequest,
    session: Session = Depends(get_database_session),
) -> dict:
    return employee_repository.change_line_manager(
        session=session,
        employee_id=employee_id,
        manager_name=request.manager_name,
        manager_email=request.manager_email,
        manager_role=request.manager_role or "Line Manager",
        reason=request.reason or "Department restructuring & reassignment",
    )


@router.patch(
    "/employees/{employee_id}/leave-balance",
    summary="Adjust one of an employee's leave balances",
)
async def update_leave_balance(
    employee_id: str,
    request: UpdateLeaveBalanceRequest,
    session: Session = Depends(get_database_session),
) -> dict:
    return employee_repository.change_leave_balance(
        session=session,
        employee_id=employee_id,
        leave_type=request.leave_type,
        remaining_days=request.remaining_days,
        used_days=request.used_days,
        carry_over_days=request.carry_over_days,
    )
