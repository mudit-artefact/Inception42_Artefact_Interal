"""
Integration test for Leave and Absence Agent.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.database.engine import SessionLocal


from app.database.tables import Employee, LeaveBalance, LeaveRequest
from app.services.leave_service import calculate_working_days, validate_leave_policy, commit_leave_request, cancel_leave_request
from app.workflow.conversation_checkpointer import create_conversation_checkpointer
from app.workflow.conversation_workflow import compile_conversation_workflow
from app.services.answer_question_service import answer_question

def test_leave_agent_e2e():
    print("1. Initializing database and workflow...")
    session = SessionLocal()
    checkpointer = create_conversation_checkpointer(checkpoint_file=None)
    workflow = compile_conversation_workflow(checkpointer)


    # Check EMP001 current balance
    emp = session.query(Employee).filter(Employee.user_id == "EMP001").first()
    bal = session.query(LeaveBalance).filter(LeaveBalance.employee_id == "EMP001", LeaveBalance.leave_type == "Annual leave").first()
    print(f"Employee {emp.name} has {bal.remaining_days} days annual leave.")
    initial_remaining = bal.remaining_days

    # Turn 1: Apply for leave with valid advance dates (e.g. 2026-10-12 to 2026-10-14 -> 3 working days)
    print("\n2. Sending Leave Request Turn 1...")
    conv_id = "test-leave-agent-001"
    res1 = answer_question(
        workflow=workflow,
        employee_question="I want to apply for 3 days of annual leave from 2026-10-12 to 2026-10-14",
        employee_id="EMP001",
        conversation_id=conv_id,
        requested_language="en",
    )

    print(f"Turn 1 Response:")
    print(f"  Answer: {res1.answer}")
    print(f"  Awaiting Clarification/Pause: {res1.is_awaiting_clarification}")
    print(f"  Action Payload: {res1.action_payload}")
    print(f"  Is Action Required: {res1.is_action_required}")

    assert res1.is_awaiting_clarification is True or res1.is_action_required is True
    assert res1.action_payload is not None
    assert res1.action_payload.get("action_type") == "CONFIRM_LEAVE_APPLICATION"

    # Turn 2: Confirm the application
    print("\n3. Sending Confirmation Turn 2 ('Confirm')...")
    res2 = answer_question(
        workflow=workflow,
        employee_question="Confirm",
        employee_id="EMP001",
        conversation_id=conv_id,
        requested_language="en",
    )

    print(f"Turn 2 Response:")
    print(f"  Answer:\n{res2.answer}")
    print(f"  Action Payload: {res2.action_payload}")
    print(f"  Intent: {res2.intent}")

    assert "Leave Request Submitted Successfully" in res2.answer or "Request ID" in res2.answer

    # Verify DB changes
    session.refresh(bal)
    print(f"\n4. Verifying DB state: New remaining balance = {bal.remaining_days} (expected {initial_remaining - 3})")
    assert bal.remaining_days == initial_remaining - 3

    # Clean up test leave request
    if res2.action_payload and "receipt" in res2.action_payload:
        req_id = res2.action_payload["receipt"]["request_id"]
        print(f"Cancelling test request #{req_id} to restore balance...")
        cancel_res = cancel_leave_request("EMP001", req_id, session)
        session.refresh(bal)
        print(f"Restored balance = {bal.remaining_days}")
        assert bal.remaining_days == initial_remaining

    # Test Policy Rejection 1: Insufficient Balance
    print("\n5. Testing Policy Rejection: Insufficient Balance...")
    res_reject = answer_question(
        workflow=workflow,
        employee_question="I want to take 50 days of annual leave next month from 2026-10-01 to 2026-12-15",
        employee_id="EMP001",
        conversation_id="test-leave-reject-balance",
        requested_language="en",
    )
    print(f"  Answer: {res_reject.answer[:120]}...")
    assert "Insufficient leave balance" in res_reject.answer or "Unable to submit" in res_reject.answer
    print("  ✅ Insufficient balance rejected as expected.")

    # Test Status Inquiry
    print("\n6. Testing Check Leave Status...")
    res_status = answer_question(
        workflow=workflow,
        employee_question="What is the status of my pending leave requests?",
        employee_id="EMP001",
        conversation_id="test-leave-status-check",
        requested_language="en",
    )
    print(f"  Answer:\n{res_status.answer}")
    assert "Pending Leave Requests" in res_status.answer or "no pending leave" in res_status.answer
    print("  ✅ Status check answered as expected.")

    print("\n🎉 ALL LEAVE AGENT E2E & POLICY GUARDRAIL TESTS PASSED!")
    session.close()

if __name__ == "__main__":
    test_leave_agent_e2e()

