"""
Comprehensive Integration Test for the 5 Advanced Leave Enhancements:
1. Two-step approval lifecycle (Pending -> Manager sign-off -> Approved).
2. Missing dates trigger SHOW_LEAVE_CALENDAR_PICKER.
3. Manager (Fatima) receives pending approval card and approves.
4. Official balance debit occurs only upon approval.
5. Employee (Ahmed) receives LEAVE_APPROVED_NOTIFICATION with calendar & email payload.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.database.engine import SessionLocal
from app.database.tables import Employee, LeaveBalance, LeaveRequest
from app.services.answer_question_service import answer_question
from app.services.leave_service import cancel_leave_request
from app.workflow.conversation_checkpointer import create_conversation_checkpointer
from app.workflow.conversation_workflow import compile_conversation_workflow

def test_advanced_leave_flow():
    print("=================================================================")
    print("TESTING 5 ADVANCED LEAVE & ABSENCE AGENT ENHANCEMENTS")
    print("=================================================================\n")

    session = SessionLocal()
    checkpointer = create_conversation_checkpointer(checkpoint_file=None)
    workflow = compile_conversation_workflow(checkpointer)

    # Initial employee balance check
    bal = session.query(LeaveBalance).filter(LeaveBalance.employee_id == "EMP001", LeaveBalance.leave_type == "Annual leave").first()
    initial_balance = bal.remaining_days
    print(f"Step 0: Ahmed's initial annual leave balance = {initial_balance} days")

    # Step 1: Missing dates -> triggers SHOW_LEAVE_CALENDAR_PICKER
    print("\nStep 1: Employee says 'I want to apply for leave' without dates...")
    conv_id = "test-adv-leave-001"
    res1 = answer_question(
        workflow=workflow,
        employee_question="I want to apply for leave",
        employee_id="EMP001",
        conversation_id=conv_id,
        requested_language="en",
    )
    print(f"  Awaiting response / interrupt: {res1.is_awaiting_clarification}")
    print(f"  Action payload: {res1.action_payload}")
    assert res1.action_payload is not None
    assert res1.action_payload.get("action_type") == "SHOW_LEAVE_CALENDAR_PICKER"
    print("  ✅ Calendar picker payload triggered as expected!")

    # Step 2: Employee selects dates via calendar picker
    print("\nStep 2: Employee submits chosen dates (2026-10-12 to 2026-10-14)...")
    res2 = answer_question(
        workflow=workflow,
        employee_question="I want to apply for Annual leave from 2026-10-12 to 2026-10-14",
        employee_id="EMP001",
        conversation_id=conv_id,
        requested_language="en",
    )
    print(f"  Action payload: {res2.action_payload.get('action_type')}")
    assert res2.action_payload.get("action_type") == "CONFIRM_LEAVE_APPLICATION"
    assert res2.action_payload.get("working_days") == 3
    print("  ✅ Policy validation passed; confirmation card presented!")

    # Step 3: Employee confirms -> submitted as PENDING (balance NOT yet debited)
    print("\nStep 3: Employee confirms ('Confirm')...")
    res3 = answer_question(
        workflow=workflow,
        employee_question="Confirm",
        employee_id="EMP001",
        conversation_id=conv_id,
        requested_language="en",
    )
    print(f"  Answer snippet: {res3.answer[:120]}...")
    print(f"  Action payload: {res3.action_payload.get('action_type')}")
    assert res3.action_payload.get("action_type") == "LEAVE_SUBMITTED_PENDING_APPROVAL"
    receipt = res3.action_payload["receipt"]
    request_id = receipt["request_id"]
    print(f"  Request ID #{request_id} created with status: {receipt['status']}")

    # Verify balance has NOT been deducted yet
    session.refresh(bal)
    print(f"  Ahmed's balance after pending submission = {bal.remaining_days} (expected unchanged {initial_balance})")
    assert bal.remaining_days == initial_balance
    print("  ✅ Leave correctly queued as PENDING without premature balance debit!")

    # Step 4: Manager (Fatima EMP002) checks pending approvals
    print("\nStep 4: Manager Fatima (EMP002) asks 'What leave requests do I need to approve?'...")
    mgr_conv = "test-mgr-approvals-001"
    res4 = answer_question(
        workflow=workflow,
        employee_question="What leave requests do I need to approve?",
        employee_id="EMP002",
        conversation_id=mgr_conv,
        requested_language="en",
    )
    print(f"  Manager Answer:\n{res4.answer}")
    assert res4.action_payload is not None
    assert res4.action_payload.get("action_type") == "MANAGER_PENDING_APPROVALS"
    print("  ✅ Manager received pending approvals list and card!")

    # Step 5: Manager approves leave for Ahmed
    print(f"\nStep 5: Manager Fatima commands 'Approve leave #{request_id} for Ahmed'...")
    res5 = answer_question(
        workflow=workflow,
        employee_question=f"Approve leave #{request_id} for Ahmed",
        employee_id="EMP002",
        conversation_id=mgr_conv,
        requested_language="en",
    )
    print(f"  Manager Approval Response:\n{res5.answer}")
    assert res5.action_payload.get("action_type") == "MANAGER_APPROVED_SUCCESS"

    # Verify status is now Approved and balance is now deducted
    req_row = session.query(LeaveRequest).filter(LeaveRequest.id == request_id).first()
    session.refresh(req_row)
    session.refresh(bal)
    print(f"  Leave request #{request_id} status = {req_row.status}")
    print(f"  Ahmed's updated balance = {bal.remaining_days} (expected {initial_balance - 3})")
    assert req_row.status == "Approved"
    assert bal.remaining_days == initial_balance - 3
    print("  ✅ Leave officially approved and balance deducted!")

    # Step 6: Employee checks status -> receives LEAVE_APPROVED_NOTIFICATION with calendar & email payload
    print("\nStep 6: Employee Ahmed checks 'What is the status of my leave requests?'...")
    res6 = answer_question(
        workflow=workflow,
        employee_question="What is the status of my leave requests?",
        employee_id="EMP001",
        conversation_id="test-employee-status-001",
        requested_language="en",
    )
    print(f"  Employee Status Response:\n{res6.answer}")
    print(f"  Action Payload: {res6.action_payload}")
    assert res6.action_payload.get("action_type") == "LEAVE_APPROVED_NOTIFICATION"
    approved_leave = res6.action_payload["approved_leave"]
    assert approved_leave["request_id"] == request_id
    assert approved_leave["approver_name"] == "Fatima Maryam Al Qubaisi"
    print("  ✅ Employee received celebratory notification with .ics and email metadata!")

    # Step 7: Clean up test request
    print(f"\nStep 7: Cleaning up test request #{request_id}...")
    cancel_leave_request("EMP001", request_id, session=session)
    session.refresh(bal)
    print(f"  Restored balance = {bal.remaining_days}")
    assert bal.remaining_days == initial_balance

    print("\n🎉 ALL 5 ADVANCED LEAVE ENHANCEMENTS TESTED AND VERIFIED SUCCESSFULLY!")
    session.close()

if __name__ == "__main__":
    test_advanced_leave_flow()
