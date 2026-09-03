"""
Contract tests for Notifications API endpoints.
"""

import pytest
from starlette.testclient import TestClient
from app.database.engine import SessionLocal
from app.services.notification_service import create_notification


def test_get_and_read_notifications_contract(api_client, temporary_database):
    session = temporary_database()
    try:
        # Create a test notification for EMP001
        notif = create_notification(
            recipient_id="EMP001",
            sender_id="EMP003",
            event_type="LEAVE_APPROVED",
            title="Leave Approved",
            message="Your leave request has been approved by Maitha.",
            action_payload={"request_id": 99, "status": "Approved"},
            session=session,
        )
    finally:
        session.close()

    # 1. Fetch notifications for EMP001
    resp = api_client.get("/api/notifications/EMP001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["employee_id"] == "EMP001"
    assert data["unread_count"] >= 1
    assert len(data["notifications"]) >= 1

    first = next((n for n in data["notifications"] if n["id"] == notif["id"]), None)
    assert first is not None
    assert first["title"] == "Leave Approved"
    assert first["is_read"] is False
    assert first["action_payload"]["request_id"] == 99

    # 2. Mark notification as read
    read_resp = api_client.post(f"/api/notifications/{notif['id']}/read")
    assert read_resp.status_code == 200
    assert read_resp.json()["is_read"] is True

    # 3. Verify unread count decreased
    resp2 = api_client.get("/api/notifications/EMP001")
    assert resp2.status_code == 200
    first_after = next((n for n in resp2.json()["notifications"] if n["id"] == notif["id"]), None)
    assert first_after is not None
    assert first_after["is_read"] is True
