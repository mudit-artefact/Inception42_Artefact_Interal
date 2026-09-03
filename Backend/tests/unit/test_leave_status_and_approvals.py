"""
Unit tests for leave status inquiries vs manager leave approval queues.
"""

from app.database.engine import SessionLocal
from app.database.tables import LeaveRequest
from app.domain.enums import QuestionIntent
from app.workflow.nodes.handle_leave_action import handle_leave_status, handle_manager_approval
from app.workflow.nodes.understand_query import understand_query


def test_intent_understanding_own_leave_status():
    test_queries = [
        "Has my leave request been approved?",
        "Is my leave request approved?",
        "Requested leaves?",
        "Requested leaves?( Does my leaves approved by my manager)",
        "Requested leaves? (Does my leaves approved by my manager)",
        "Does my leaves approved by my manager",
        "Is my leave approved?",
        "Did my manager approve my leave?",
        "Status of my leave",
        "My leave status",
    ]
    for q in test_queries:
        state = {
            "employee_id": "EMP001",
            "employee_question": q,
            "requested_language": "en",
        }
        result = understand_query(state)
        assert result["question_intent"] == QuestionIntent.CHECK_LEAVE_STATUS.value, (
            f"Query '{q}' expected {QuestionIntent.CHECK_LEAVE_STATUS} but got {result['question_intent']}"
        )


def test_intent_understanding_manager_approvals():
    test_queries = [
        "What leave requests do I need to approve?",
        "Leave request(What leave requests do I need to approve?)",
        "Leave request (What leave requests do I need to approve?)",
        "Leave requests to approve",
        "Pending approvals from my team",
        "What do I need to approve",
    ]
    for q in test_queries:
        state = {
            "employee_id": "EMP001",
            "employee_question": q,
            "requested_language": "en",
        }
        result = understand_query(state)
        assert result["question_intent"] == QuestionIntent.APPROVE_LEAVE.value, (
            f"Query '{q}' expected {QuestionIntent.APPROVE_LEAVE} but got {result['question_intent']}"
        )


def test_ahmed_leave_status_not_hijacked_by_junior_request():
    """
    Ahmed (EMP001) has an approved request by Fatima.
    Ahmed is also a manager with pending approvals for direct reports.
    Inquiring about his own leave must return Ahmed's approval by Fatima,
    and must NEVER approve or display junior requests instead.
    """
    session = SessionLocal()
    try:
        latest = session.query(LeaveRequest).filter(LeaveRequest.employee_id == "EMP001").order_by(LeaveRequest.id.desc()).first()
        if latest and latest.status != "Approved":
            latest.status = "Approved"
            latest.approver_name = "Fatima Maryam Al Qubaisi"
            session.commit()
    finally:
        session.close()

    state = {
        "employee_id": "EMP001",
        "employee_question": "Does my leaves approved by my manager",
        "requested_language": "en",
        "question_intent": QuestionIntent.CHECK_LEAVE_STATUS.value,
    }
    result = handle_leave_status(state)
    answer = result["final_answer"]

    # Must confirm his leave is approved by Fatima
    assert "Approved" in answer
    assert "Fatima Maryam Al Qubaisi" in answer

    # Action payload must be for approved leave notification
    payload = result.get("action_payload", {})
    assert payload.get("action_type") == "LEAVE_APPROVED_NOTIFICATION"
    approved_leave = payload.get("approved_leave", {})
    assert approved_leave.get("approver_name") == "Fatima Maryam Al Qubaisi"
    assert approved_leave.get("status") == "Approved"


def test_manager_inquiry_does_not_execute_approval():
    """
    Inquiring about pending approvals must display the approvals card
    and must NEVER execute approve_leave_request.
    """
    session = SessionLocal()
    try:
        req_18_before = session.query(LeaveRequest).filter(LeaveRequest.id == 18).first()
        status_before = req_18_before.status if req_18_before else None

        state = {
            "employee_id": "EMP001",
            "employee_question": "Leave request (What leave requests do I need to approve?)",
            "requested_language": "en",
            "question_intent": QuestionIntent.APPROVE_LEAVE.value,
        }
        result = handle_manager_approval(state)

        # Must display pending approvals
        payload = result.get("action_payload", {})
        assert payload.get("action_type") == "MANAGER_PENDING_APPROVALS"

        # Request status in DB must not have changed
        req_18_after = session.query(LeaveRequest).filter(LeaveRequest.id == 18).first()
        status_after = req_18_after.status if req_18_after else None
        assert status_before == status_after
    finally:
        session.close()


def test_manager_inquiry_with_junior_leave_requests():
    """
    When B has juniors who requested leave, chatbot should respond:
    'Yes, {junior} asked for a leave request: ...'
    """
    state = {
        "employee_id": "EMP001",
        "employee_question": "is there any leave pending for me to approve",
        "requested_language": "en",
        "question_intent": QuestionIntent.APPROVE_LEAVE.value,
    }
    result = handle_manager_approval(state)
    answer = result["final_answer"]
    assert "Yes" in answer
    assert "asked for a leave request" in answer
    assert result.get("action_payload", {}).get("action_type") == "MANAGER_PENDING_APPROVALS"


def test_manager_inquiry_without_junior_leave_requests():
    """
    When B has no juniors with pending leave, chatbot should respond:
    'No {B}, you don't have any leave request pending of your juniors.'
    """
    state = {
        "employee_id": "EMP003",  # Aisha has no direct reports with pending leave
        "employee_question": "any pending leave to approve",
        "requested_language": "en",
        "question_intent": QuestionIntent.APPROVE_LEAVE.value,
    }
    result = handle_manager_approval(state)
    answer = result["final_answer"]
    assert "No Aisha, you don't have any leave request pending of your juniors." in answer

