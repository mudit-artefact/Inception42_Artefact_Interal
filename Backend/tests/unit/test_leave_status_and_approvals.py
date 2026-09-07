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


def test_alia_leave_status_not_hijacked_by_junior_request(temporary_database):
    """
    Alia (EMP001) has an approved request by Maitha.
    Alia is also a manager with pending approvals for direct reports.
    Inquiring about her own leave must return Alia's approval by Maitha,
    and must NEVER approve or display junior requests instead.
    """
    session = temporary_database()
    try:
        latest = session.query(LeaveRequest).filter(LeaveRequest.employee_id == "EMP001").order_by(LeaveRequest.id.desc()).first()
        if latest and latest.status != "Approved":
            latest.status = "Approved"
            latest.approver_name = "Maitha Al Mazrouei"
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

    # Must confirm her leave is approved by Maitha
    assert "Approved" in answer
    assert "Maitha Al Mazrouei" in answer

    # Action payload must be for approved leave notification
    payload = result.get("action_payload", {})
    assert payload.get("action_type") == "LEAVE_APPROVED_NOTIFICATION"
    approved_leave = payload.get("approved_leave", {})
    assert approved_leave.get("approver_name") == "Maitha Al Mazrouei"
    assert approved_leave.get("status") == "Approved"


def test_manager_inquiry_does_not_execute_approval(temporary_database):
    """
    Inquiring about pending approvals must display the approvals card
    and must NEVER execute approve_leave_request.
    """
    session = temporary_database()
    try:
        pending_req = session.query(LeaveRequest).filter(LeaveRequest.status == "Pending").first()
        status_before = pending_req.status if pending_req else None

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
        if pending_req:
            pending_after = session.query(LeaveRequest).filter(LeaveRequest.id == pending_req.id).first()
            assert pending_after.status == status_before
    finally:
        session.close()


def test_manager_inquiry_with_junior_leave_requests(temporary_database):
    """
    When manager has direct reports with pending leave requests,
    the chatbot displays the pending approvals card and clear review instruction.
    """
    state = {
        "employee_id": "EMP001",
        "employee_question": "is there any leave pending for me to approve",
        "requested_language": "en",
        "question_intent": QuestionIntent.APPROVE_LEAVE.value,
    }
    result = handle_manager_approval(state)
    answer = result["final_answer"]
    assert "Approve Leave" in answer
    assert result.get("action_payload", {}).get("action_type") == "MANAGER_PENDING_APPROVALS"


def test_manager_inquiry_without_junior_leave_requests(temporary_database):
    """
    When B has no juniors with pending leave, chatbot should respond:
    'No {B}, you don't have any leave request pending of your juniors.'
    """
    state = {
        "employee_id": "EMP012",  # Mohammed has no direct reports with pending leave
        "employee_question": "any pending leave to approve",
        "requested_language": "en",
        "question_intent": QuestionIntent.APPROVE_LEAVE.value,
    }
    result = handle_manager_approval(state)
    answer = result["final_answer"]
    assert "No Mohammed, you don't have any leave request pending of your juniors." in answer



def test_a_number_in_the_message_is_not_taken_as_a_request_id(temporary_database):
    """
    "approve 3 days of annual leave" must not approve request #3.

    Any integer anywhere in the message used to be read as the request id and checked
    against nothing, so a manager saying how long a leave was could approve a stranger's
    request by accident. A number now only counts when it names one of this manager's own
    pending requests.

    Alia manages Hessa and Khalifa, and is given a pending request from each so that the
    "only one pending, so they must mean that one" shortcut cannot mask the result. The
    request the number names belongs to Alia herself, which is nobody's to approve.

    The session comes from the fixture rather than the module-level `SessionLocal`
    imported at the top of this file. That name was bound at import time and still points
    at the real database, so a test using it writes to the developer's own records while
    the code under test reads the temporary one, and the two never see each other.
    """
    session = temporary_database()
    try:
        session.add(
            LeaveRequest(
                employee_id="EMP010",
                leave_type="Annual leave",
                start_date="2026-11-02",
                end_date="2026-11-04",
                days_requested=3,
                status="Pending",
                approver_name="Alia Al Suwaidi",
            )
        )
        not_hers_to_approve = LeaveRequest(
            employee_id="EMP001",
            leave_type="Annual leave",
            start_date="2026-12-07",
            end_date="2026-12-09",
            days_requested=3,
            status="Pending",
            approver_name="Maitha Al Mazrouei",
        )
        session.add(not_hers_to_approve)
        session.commit()
        stranger_id = not_hers_to_approve.id

        result = handle_manager_approval(
            {
                "employee_id": "EMP001",
                "employee_question": f"approve {stranger_id} days of annual leave",
                "requested_language": "en",
                "question_intent": QuestionIntent.APPROVE_LEAVE.value,
            }
        )

        session.expire_all()
        assert (
            session.query(LeaveRequest).filter(LeaveRequest.id == stranger_id).first().status
            == "Pending"
        ), f"request #{stranger_id} is not this manager's to approve and must be untouched"

        assert (
            session.query(LeaveRequest).filter(LeaveRequest.status == "Pending").count() == 3
        ), "a number that names none of her requests must approve none of them"

        assert result.get("action_payload", {}).get("action_type") == "MANAGER_PENDING_APPROVALS", (
            "with nothing identified, the manager should be shown the list again"
        )
    finally:
        session.close()
