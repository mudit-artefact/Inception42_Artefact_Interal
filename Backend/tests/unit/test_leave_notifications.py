"""
Unit tests for Leave Agent Notifications (Manager dispatch on request, Employee dispatch on approval/rejection).
"""

import pytest
from app.database.engine import SessionLocal
from app.database.tables import Employee, LeaveRequest, Notification
from app.services.leave_service import (
    approve_leave_request,
    commit_leave_request,
    reject_leave_request,
    validate_leave_policy,
)
from app.services.notification_service import (
    count_unread_notifications,
    create_notification,
    list_employee_notifications,
    mark_all_notifications_as_read,
    mark_notification_as_read,
)
from app.workflow.structured_outputs import LeaveApplicationDraft


def test_create_and_list_notifications(temporary_database):
    session = temporary_database()
    try:
        notif = create_notification(
            recipient_id="EMP001",
            sender_id="EMP003",
            event_type="LEAVE_APPROVED",
            title="Leave Approved",
            message="Your leave request has been approved.",
            action_payload={"request_id": 10},
            session=session,
        )
        assert notif["id"] is not None
        assert notif["recipient_id"] == "EMP001"
        assert notif["is_read"] is False

        # Query list
        notifs = list_employee_notifications("EMP001", session=session)
        assert len(notifs) >= 1
        assert any(n["title"] == "Leave Approved" for n in notifs)

        # Unread count
        unread = count_unread_notifications("EMP001", session=session)
        assert unread >= 1

        # Mark read
        res = mark_notification_as_read(notif["id"], session=session)
        assert res["success"] is True

        unread_after = count_unread_notifications("EMP001", session=session)
        assert unread_after == unread - 1
    finally:
        session.close()


def test_leave_application_dispatches_notification_to_manager(temporary_database):
    """
    When Alia (EMP001) submits leave, a notification must be dispatched to her manager Maitha (EMP003).
    """
    session = temporary_database()
    try:
        # Clear prior notifications for clean count
        session.query(Notification).filter(Notification.recipient_id == "EMP003").delete()
        session.commit()

        draft = LeaveApplicationDraft(
            leave_type="Annual leave",
            start_date="2026-10-12",
            end_date="2026-10-16",
            days_requested=5,
            reason="Autumn vacation",
            is_complete=True,
        )
        validation = validate_leave_policy("EMP001", draft, session=session)
        assert validation.is_valid is True

        receipt = commit_leave_request("EMP001", validation, reason=draft.reason, session=session)
        assert receipt["status"] == "Pending"

        # Check that Maitha (EMP003) received the notification
        manager_notifs = list_employee_notifications("EMP003", session=session)
        assert len(manager_notifs) >= 1

        req_notif = next((n for n in manager_notifs if n["event_type"] == "LEAVE_REQUESTED"), None)
        assert req_notif is not None
        assert "Alia Al Suwaidi" in req_notif["message"]
        assert req_notif["action_payload"]["request_id"] == receipt["request_id"]
    finally:
        session.close()


def test_manager_approval_dispatches_notification_to_employee(temporary_database):
    """
    When Maitha approves Alia's leave request, Alia must receive a LEAVE_APPROVED notification.
    """
    session = temporary_database()
    try:
        # Create a pending request for Alia
        req = LeaveRequest(
            employee_id="EMP001",
            leave_type="Annual Leave",
            start_date="2026-07-06",
            end_date="2026-07-10",
            days_requested=5,
            status="Pending",
            approver_name="Maitha Al Mazrouei",
        )
        session.add(req)
        session.commit()
        session.refresh(req)

        # Clear Alia's notifications
        session.query(Notification).filter(Notification.recipient_id == "EMP001").delete()
        session.commit()

        # Maitha approves
        res = approve_leave_request(manager_id="EMP003", request_id=req.id, session=session)
        assert res["success"] is True

        # Check Alia's notifications
        alia_notifs = list_employee_notifications("EMP001", session=session)
        assert len(alia_notifs) >= 1

        app_notif = next((n for n in alia_notifs if n["event_type"] == "LEAVE_APPROVED"), None)
        assert app_notif is not None
        assert f"Leave Request #{req.id} Approved" in app_notif["title"]
        assert "Maitha Al Mazrouei" in app_notif["message"]
    finally:
        session.close()


def test_manager_rejection_dispatches_notification_to_employee(temporary_database):
    """
    When Maitha rejects a leave request, the applicant must receive a LEAVE_REJECTED notification.
    """
    session = temporary_database()
    try:
        req = LeaveRequest(
            employee_id="EMP001",
            leave_type="Annual Leave",
            start_date="2026-08-03",
            end_date="2026-08-07",
            days_requested=5,
            status="Pending",
            approver_name="Maitha Al Mazrouei",
        )
        session.add(req)
        session.commit()
        session.refresh(req)

        # Clear Alia's notifications
        session.query(Notification).filter(Notification.recipient_id == "EMP001").delete()
        session.commit()

        # Maitha rejects
        res = reject_leave_request(
            manager_id="EMP003",
            request_id=req.id,
            reason="Team critical project delivery deadline",
            session=session,
        )
        assert res["success"] is True

        # Check Alia's notifications
        alia_notifs = list_employee_notifications("EMP001", session=session)
        assert len(alia_notifs) >= 1

        rej_notif = next((n for n in alia_notifs if n["event_type"] == "LEAVE_REJECTED"), None)
        assert rej_notif is not None
        assert f"Leave Request #{req.id} Declined" in rej_notif["title"]
        assert "Team critical project delivery deadline" in rej_notif["message"]
    finally:
        session.close()


def test_mark_all_notifications_as_read(temporary_database):
    session = temporary_database()
    try:
        create_notification("EMP002", "TEST_1", "Title 1", "Msg 1", session=session)
        create_notification("EMP002", "TEST_2", "Title 2", "Msg 2", session=session)

        unread = count_unread_notifications("EMP002", session=session)
        assert unread >= 2

        mark_all_notifications_as_read("EMP002", session=session)
        unread_after = count_unread_notifications("EMP002", session=session)
        assert unread_after == 0
    finally:
        session.close()
