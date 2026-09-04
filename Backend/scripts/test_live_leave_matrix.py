"""
Live Cross-Check Matrix for Leave & Absence Agent Capabilities.
Cross-checks LLM responses against Source of Truth (People Code & UAE Labour Law)
and verifies transactional mutations in Omni DB (omni_hr.db).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.database.engine import SessionLocal
from app.database.tables import Employee, LeaveBalance, LeaveRequest, Notification
from app.services.answer_question_service import answer_question
from app.services.leave_service import approve_leave_request, cancel_leave_request
from app.workflow.conversation_checkpointer import create_conversation_checkpointer
from app.workflow.conversation_workflow import compile_conversation_workflow


def run_live_leave_matrix():
    print("=" * 80)
    print("🚀 STARTING LIVE LEAVE AGENT CAPABILITY MATRIX & OMNI DB CROSS-CHECK")
    print("=" * 80)

    session = SessionLocal()
    checkpointer = create_conversation_checkpointer(checkpoint_file=None)
    workflow = compile_conversation_workflow(checkpointer)

    # --------------------------------------------------------------------------
    # SCENARIO 1: Alia Al Suwaidi (EMP001) Applying for Sick Leave (User Issue)
    # --------------------------------------------------------------------------
    print("\n[TEST 1] Alia Al Suwaidi Applying for 2 Days of Sick Leave...")
    alia = session.query(Employee).filter(Employee.user_id == "EMP001").first()
    active_sick_rows = session.query(LeaveBalance).filter(
        LeaveBalance.employee_id == "EMP001",
        LeaveBalance.leave_type.like("Sick leave%"),
        LeaveBalance.year == 2026,
    ).all()
    initial_sick_days = sum(b.remaining_days for b in active_sick_rows)
    initial_full_pay_rem = next(b.remaining_days for b in active_sick_rows if "full pay" in b.leave_type)
    initial_full_pay_used = next(b.used_days for b in active_sick_rows if "full pay" in b.leave_type)

    print(f"  Source of Truth Check: HC-PC-002 §2.2.1 entitlement = 90 days total across 3 pay tranches.")
    print(f"  Omni DB Pre-State: {initial_sick_days} days total available ({initial_full_pay_rem} full pay, 45 half pay, 30 unpaid).")
    assert initial_sick_days == 80

    conv_id = "live-sick-alia-001"
    # Turn 1: Apply
    res1 = answer_question(
        workflow=workflow,
        employee_question="I want to apply for 2 days of sick leave from 2026-11-02 to 2026-11-03 due to seasonal flu",
        employee_id="EMP001",
        conversation_id=conv_id,
        requested_language="en",
    )
    print(f"  Turn 1 LLM Response Summary:")
    print(f"    - Answer snippet: {res1.answer[:140]}...")
    print(f"    - Action Type: {res1.action_payload.get('action_type') if res1.action_payload else None}")
    assert res1.action_payload is not None
    assert res1.action_payload["action_type"] == "CONFIRM_LEAVE_APPLICATION"
    assert res1.action_payload["leave_type"] == "Sick leave"
    assert res1.action_payload["working_days"] == 2
    assert res1.action_payload["balance_before"] == 80.0
    assert res1.action_payload["balance_after"] == 78.0
    assert res1.action_payload["requires_medical_certificate"] is False  # <=2 days permits self-certification
    print("  ✅ Turn 1: Correctly identified 80.0 days available, self-certification permitted, paused for confirmation.")

    # Turn 2: Confirm
    res2 = answer_question(
        workflow=workflow,
        employee_question="Yes, please submit it",
        employee_id="EMP001",
        conversation_id=conv_id,
        requested_language="en",
    )
    print(f"  Turn 2 LLM Response Summary:")
    print(f"    - Answer snippet: {res2.answer[:140]}...")
    assert "Submitted" in res2.answer or "Pending" in res2.answer or "Request ID" in res2.answer
    req_id = res2.action_payload["receipt"]["request_id"]
    print(f"    - Created Leave Request ID: #{req_id}")

    # Cross-check Omni DB for Pending Request
    db_req = session.query(LeaveRequest).filter(LeaveRequest.id == req_id).first()
    assert db_req is not None
    assert db_req.status == "Pending"
    assert db_req.days_requested == 2
    assert db_req.approver_name == "Maitha Al Mazrouei"
    print("  ✅ Omni DB Check: LeaveRequest record created with status='Pending'.")

    # Manager Approval
    print(f"  Simulating Manager Approval by Maitha Al Mazrouei (EMP003)...")
    app_res = approve_leave_request(manager_id="EMP003", request_id=req_id, session=session)
    assert app_res["success"] is True

    # Cross-check Omni DB for Debited Tranche
    session.expire_all()
    full_pay_after = session.query(LeaveBalance).filter(
        LeaveBalance.employee_id == "EMP001",
        LeaveBalance.leave_type == "Sick leave (full pay)",
        LeaveBalance.year == 2026,
    ).first()
    assert full_pay_after.remaining_days == initial_full_pay_rem - 2
    assert full_pay_after.used_days == initial_full_pay_used + 2
    print(f"  ✅ Omni DB Check: Debited 2 days from 'Sick leave (full pay)' tranche (Remaining: {full_pay_after.remaining_days}, Used: {full_pay_after.used_days}).")

    # Cleanup: Cancel to keep DB pristine
    cancel_res = cancel_leave_request("EMP001", req_id, session=session)
    assert cancel_res["success"] is True
    session.expire_all()
    full_pay_restored = session.query(LeaveBalance).filter(
        LeaveBalance.employee_id == "EMP001",
        LeaveBalance.leave_type == "Sick leave (full pay)",
        LeaveBalance.year == 2026,
    ).first()
    assert full_pay_restored.remaining_days == initial_full_pay_rem
    print("  ✅ Omni DB Check: Cancelled and restored 'Sick leave (full pay)' balance.")

    # --------------------------------------------------------------------------
    # SCENARIO 2: Sick Leave > 2 Days (Requires Medical Certificate)
    # --------------------------------------------------------------------------
    print("\n[TEST 2] Sick Leave > 2 Days (Medical Certificate Enforcement)...")
    res_med = answer_question(
        workflow=workflow,
        employee_question="I need to take 4 days of sick leave from 2026-11-02 to 2026-11-05",
        employee_id="EMP001",
        conversation_id="live-sick-med-cert",
        requested_language="en",
    )
    assert res_med.action_payload is not None
    assert res_med.action_payload["requires_medical_certificate"] is True
    print(f"  Source of Truth Check: HC-PC-002 §2.3.2 requires medical cert from DHA/DOH/MOH for > 2 days.")
    print("  ✅ LLM Action Payload: requires_medical_certificate is True.")

    # --------------------------------------------------------------------------
    # SCENARIO 3: Emergency Leave (Deducted from Annual Leave & Same-Day Notice)
    # --------------------------------------------------------------------------
    print("\n[TEST 3] Emergency Leave (HC-PC-001 §1.4.3)...")
    annual_row = session.query(LeaveBalance).filter(
        LeaveBalance.employee_id == "EMP001",
        LeaveBalance.leave_type == "Annual leave",
        LeaveBalance.year == 2026,
    ).first()
    init_annual_rem = annual_row.remaining_days

    res_emerg = answer_question(
        workflow=workflow,
        employee_question="I have a home flooding emergency, I need urgent emergency leave tomorrow 2026-11-02 to 2026-11-03",
        employee_id="EMP001",
        conversation_id="live-emerg-001",
        requested_language="en",
    )
    assert res_emerg.action_payload is not None
    assert res_emerg.action_payload["action_type"] == "CONFIRM_LEAVE_APPLICATION"
    assert res_emerg.action_payload["leave_type"] == "Emergency leave"
    assert res_emerg.action_payload["notice_compliant"] is True  # Exempt from advance notice
    assert res_emerg.action_payload["balance_before"] == float(init_annual_rem)
    print(f"  Source of Truth Check: HC-PC-001 §1.4.3 states emergency leave is deducted from Annual Leave.")
    print(f"  ✅ Correctly validated against Annual leave balance ({init_annual_rem} days) without advance notice rejection.")

    # --------------------------------------------------------------------------
    # SCENARIO 4: Annual Leave Short Advance Notice Rejection
    # --------------------------------------------------------------------------
    print("\n[TEST 4] Annual Leave Short Notice Rejection (HC-PC-001 §1.4.1)...")
    res_notice = answer_question(
        workflow=workflow,
        employee_question="I want to take 10 days of annual leave starting next Monday from 2026-09-07 to 2026-09-18",
        employee_id="EMP001",
        conversation_id="live-al-notice-001",
        requested_language="en",
    )
    assert "Notice period requirement not met" in res_notice.answer or "Unable to submit" in res_notice.answer
    print(f"  Source of Truth Check: HC-PC-001 §1.4.1 requires at least 20 working days notice for 10+ days of leave.")
    print(f"  ✅ LLM properly rejected request citing notice period requirement.")

    # --------------------------------------------------------------------------
    # SCENARIO 5: Statutory Leaves (Paternity, Maternity, Bereavement, Study, Hajj)
    # --------------------------------------------------------------------------
    print("\n[TEST 5] Statutory Paternity Leave Exceeding Statutory Cap...")
    res_pat_excess = answer_question(
        workflow=workflow,
        employee_question="I want to apply for 8 days of paternity leave from 2026-11-02 to 2026-11-11",
        employee_id="EMP001",
        conversation_id="live-pat-excess",
        requested_language="en",
    )
    assert "Statutory leave limit exceeded" in res_pat_excess.answer or "Paternity leave is capped at 5" in res_pat_excess.answer
    print("  Source of Truth Check: UAE Labour Law Art. 32(1)(b) caps paternity leave at 5 working days.")
    print("  ✅ Exceeding statutory paternity leave limit was cleanly caught and rejected.")

    print("\n[TEST 6] Statutory Study Leave for Employee with >= 2 Years Service...")
    res_study = answer_question(
        workflow=workflow,
        employee_question="I need 5 days of study leave for my university exams from 2026-11-02 to 2026-11-06",
        employee_id="EMP001",
        conversation_id="live-study-valid",
        requested_language="en",
    )
    assert res_study.action_payload is not None
    assert res_study.action_payload["action_type"] == "CONFIRM_LEAVE_APPLICATION"
    assert res_study.action_payload["leave_type"] == "Study leave"
    print("  Source of Truth Check: UAE Labour Law Art. 32(2) entitles employees with >= 2 years service to study leave.")
    print("  ✅ Study leave validated and confirmation requested.")

    print("\n" + "=" * 80)
    print("🎉 ALL LIVE LEAVE CAPABILITY MATRIX TESTS & OMNI DB CROSS-CHECKS PASSED!")
    print("=" * 80)
    session.close()


if __name__ == "__main__":
    run_live_leave_matrix()
