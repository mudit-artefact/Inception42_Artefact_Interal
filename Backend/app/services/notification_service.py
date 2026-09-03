"""
Notification Service: Managing real-time and persisted employee & manager notifications.
"""

from datetime import datetime
import json
import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.database.engine import SessionLocal
from app.database.tables import Employee, Notification

logger = logging.getLogger(__name__)


def create_notification(
    recipient_id: str,
    event_type: str,
    title: str,
    message: str,
    sender_id: Optional[str] = None,
    action_url: str = "",
    action_payload: Optional[dict[str, Any]] = None,
    session: Optional[Session] = None,
) -> dict[str, Any]:
    """Create and persist a notification for an employee or manager."""
    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        payload_str = json.dumps(action_payload) if action_payload else "{}"
        notification = Notification(
            recipient_id=recipient_id,
            sender_id=sender_id,
            event_type=event_type,
            title=title,
            message=message,
            action_url=action_url,
            action_payload=payload_str,
            is_read=0,
            created_at=datetime.utcnow(),
        )
        session.add(notification)
        session.commit()
        session.refresh(notification)

        logger.info(
            f"Created notification #{notification.id} for {recipient_id}: [{event_type}] {title}"
        )
        return _format_notification(notification)
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to create notification for {recipient_id}: {e}", exc_info=True)
        raise
    finally:
        if close_session:
            session.close()


def list_employee_notifications(
    employee_id: str,
    unread_only: bool = False,
    limit: int = 20,
    session: Optional[Session] = None,
) -> list[dict[str, Any]]:
    """List notifications for an employee in descending chronological order."""
    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        query = session.query(Notification).filter(Notification.recipient_id == employee_id)
        if unread_only:
            query = query.filter(Notification.is_read == 0)

        records = query.order_by(Notification.created_at.desc()).limit(limit).all()
        return [_format_notification(n) for n in records]
    finally:
        if close_session:
            session.close()


def count_unread_notifications(
    employee_id: str,
    session: Optional[Session] = None,
) -> int:
    """Count number of unread notifications for an employee."""
    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        return (
            session.query(Notification)
            .filter(Notification.recipient_id == employee_id, Notification.is_read == 0)
            .count()
        )
    finally:
        if close_session:
            session.close()


def mark_notification_as_read(
    notification_id: int,
    session: Optional[Session] = None,
) -> dict[str, Any]:
    """Mark a single notification as read."""
    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        notif = session.query(Notification).filter(Notification.id == notification_id).first()
        if not notif:
            return {"success": False, "message": f"Notification #{notification_id} not found."}

        notif.is_read = 1
        session.commit()
        return {"success": True, "notification_id": notification_id, "is_read": True}
    except Exception as e:
        session.rollback()
        logger.error(f"Error marking notification #{notification_id} as read: {e}", exc_info=True)
        return {"success": False, "message": str(e)}
    finally:
        if close_session:
            session.close()


def mark_all_notifications_as_read(
    employee_id: str,
    session: Optional[Session] = None,
) -> dict[str, Any]:
    """Mark all notifications for an employee as read."""
    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        session.query(Notification).filter(
            Notification.recipient_id == employee_id,
            Notification.is_read == 0,
        ).update({"is_read": 1})
        session.commit()
        return {"success": True, "employee_id": employee_id}
    except Exception as e:
        session.rollback()
        logger.error(f"Error marking all notifications for {employee_id} as read: {e}", exc_info=True)
        return {"success": False, "message": str(e)}
    finally:
        if close_session:
            session.close()


def _format_notification(n: Notification) -> dict[str, Any]:
    payload = {}
    if n.action_payload:
        try:
            payload = json.loads(n.action_payload)
        except Exception:
            payload = {}

    return {
        "id": n.id,
        "recipient_id": n.recipient_id,
        "sender_id": n.sender_id,
        "event_type": n.event_type,
        "title": n.title,
        "message": n.message,
        "action_url": n.action_url or "",
        "action_payload": payload,
        "is_read": bool(n.is_read),
        "created_at": n.created_at.strftime("%Y-%m-%d %H:%M:%S") if n.created_at else "",
    }
