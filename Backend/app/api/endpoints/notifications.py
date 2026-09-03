"""
Endpoints for reading and managing employee notifications.
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.engine import get_database_session
from app.services import notification_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


class NotificationResponse(BaseModel):
    id: int
    recipient_id: str
    sender_id: Optional[str] = None
    event_type: str
    title: str
    message: str
    action_url: str = ""
    action_payload: dict[str, Any] = Field(default_factory=dict)
    is_read: bool
    created_at: str


class NotificationListResponse(BaseModel):
    employee_id: str
    unread_count: int
    notifications: list[NotificationResponse]


@router.get(
    "/{employee_id}",
    response_model=NotificationListResponse,
    summary="List notifications for an employee",
)
async def get_employee_notifications(
    employee_id: str,
    unread_only: bool = False,
    limit: int = 20,
    session: Session = Depends(get_database_session),
) -> NotificationListResponse:
    notifs = notification_service.list_employee_notifications(
        employee_id=employee_id.upper(),
        unread_only=unread_only,
        limit=limit,
        session=session,
    )
    unread_count = notification_service.count_unread_notifications(
        employee_id=employee_id.upper(),
        session=session,
    )
    return NotificationListResponse(
        employee_id=employee_id.upper(),
        unread_count=unread_count,
        notifications=[NotificationResponse(**n) for n in notifs],
    )


@router.patch(
    "/{notification_id}/read",
    summary="Mark a single notification as read",
)
@router.post(
    "/{notification_id}/read",
    summary="Mark a single notification as read (POST)",
)
async def mark_read(
    notification_id: int,
    session: Session = Depends(get_database_session),
) -> dict:
    res = notification_service.mark_notification_as_read(notification_id, session=session)
    if not res.get("success"):
        raise HTTPException(status_code=404, detail=res.get("message", "Notification not found"))
    return res


@router.patch(
    "/{employee_id}/read-all",
    summary="Mark all notifications for an employee as read",
)
@router.post(
    "/{employee_id}/read-all",
    summary="Mark all notifications for an employee as read (POST)",
)
async def mark_all_read(
    employee_id: str,
    session: Session = Depends(get_database_session),
) -> dict:
    return notification_service.mark_all_notifications_as_read(employee_id.upper(), session=session)
