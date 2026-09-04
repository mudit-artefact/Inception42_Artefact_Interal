"""
Comprehensive Verification Test Suite for Leave Agent Capabilities Across All Leave Types and Timeframes.
Cross-checks determinism, policy citations, and Omni DB transactional integrity.
"""

import pytest
from app.database.tables import Employee, LeaveBalance, LeaveRequest
from app.services.leave_service import (
    approve_leave_request,
    calculate_working_days,
    cancel_leave_request,
    commit_leave_request,
    get_required_notice_days,
    normalize_leave_type,
    reject_leave_request,
    validate_leave_policy,
)
from app.workflow.structured_outputs import LeaveApplicationDraft


# ==============================================================================
# 1. SICK LEAVE TESTS (HC-PC-002 & UAE Labour Law)
# ==============================================================================

def test_alia_sick_leave_valid_and_balances(temporary_database):
    """
    Direct user problem reproduction:
    Alia Al Suwaidi (EMP001) has 80 days total sick leave:
      - 5 days full pay (15 entitled - 10 used)
      - 45 days half pay
      - 30 days unpaid
    Requesting 2 working days of sick leave must succeed, report 80.0 available,
    78.0 projected, and self-certification permitted.
    """
    session = temporary_database()
    try:
        draft = LeaveApplicationDraft(
            leave_type="Sick leave",
            start_date="2026-11-02",
            end_date="2026-11-03",
            days_requested=2,
            is_complete=True,
        )
        res = validate_leave_policy("EMP001", draft, session=session)
        assert res.is_valid is True
        assert res.balance_before == 80.0
        assert res.balance_after == 78.0
        assert res.working_days == 2
        assert res.requires_medical_certificate is False  # 1-2 days permits self-certification

        # Test commit
        receipt = commit_leave_request("EMP001", res, reason="Mild migraine", session=session)
        assert receipt["success"] is True
        assert receipt["status"] == "Pending"
        assert receipt["current_balance"] == 80.0
        assert receipt["projected_balance"] == 78.0

        req_id = receipt["request_id"]

        # Test manager approval debits the Full Pay tranche first
        app_res = approve_leave_request(manager_id="EMP003", request_id=req_id, session=session)
        assert app_res["success"] is True

        # Verify DB state
        full_pay_row = (
            session.query(LeaveBalance)
            .filter(LeaveBalance.employee_id == "EMP001", LeaveBalance.leave_type == "Sick leave (full pay)")
            .first()
        )
        assert full_pay_row.remaining_days == 3  # 5 - 2 = 3
        assert full_pay_row.used_days == 12      # 10 + 2 = 12

        # Test cancellation restores the balance
        cancel_res = cancel_leave_request("EMP001", req_id, session=session)
        assert cancel_res["success"] is True
        assert cancel_res["restored_days"] == 2
        session.refresh(full_pay_row)
        assert full_pay_row.remaining_days == 5
        assert full_pay_row.used_days == 10
    finally:
        session.close()


def test_sick_leave_medical_certificate_requirement(temporary_database):
    """Absence > 2 consecutive working days triggers medical cert requirement per HC-PC-002 §2.3.2."""
    session = temporary_database()
    try:
        draft = LeaveApplicationDraft(
            leave_type="Sick leave",
            start_date="2026-11-02",
            end_date="2026-11-05",  # 4 working days
            days_requested=4,
            is_complete=True,
        )
        res = validate_leave_policy("EMP001", draft, session=session)
        assert res.is_valid is True
        assert res.working_days == 4
        assert res.requires_medical_certificate is True
    finally:
        session.close()


def test_sick_leave_multi_tranche_rollover_debit(temporary_database):
    """
    Requesting 10 days sick leave when full pay has 5 days remaining:
    5 days are debited from Full Pay tranche (becoming 0 remaining),
    5 days are debited from Half Pay tranche (becoming 40 remaining).
    """
    session = temporary_database()
    try:
        draft = LeaveApplicationDraft(
            leave_type="Sick leave",
            start_date="2026-11-02",
            end_date="2026-11-13",  # 10 working days
            days_requested=10,
            is_complete=True,
        )
        res = validate_leave_policy("EMP001", draft, session=session)
        assert res.is_valid is True
        assert res.balance_before == 80.0
        assert res.balance_after == 70.0

        receipt = commit_leave_request("EMP001", res, reason="Surgery recovery", session=session)
        req_id = receipt["request_id"]

        app_res = approve_leave_request(manager_id="EMP003", request_id=req_id, session=session)
        assert app_res["success"] is True

        full_pay_row = session.query(LeaveBalance).filter(
            LeaveBalance.employee_id == "EMP001", LeaveBalance.leave_type == "Sick leave (full pay)"
        ).first()
        half_pay_row = session.query(LeaveBalance).filter(
            LeaveBalance.employee_id == "EMP001", LeaveBalance.leave_type == "Sick leave (half pay)"
        ).first()
        unpaid_row = session.query(LeaveBalance).filter(
            LeaveBalance.employee_id == "EMP001", LeaveBalance.leave_type == "Sick leave (unpaid)"
        ).first()

        assert full_pay_row.remaining_days == 0
        assert full_pay_row.used_days == 15
        assert half_pay_row.remaining_days == 40
        assert half_pay_row.used_days == 5
        assert unpaid_row.remaining_days == 30

        # Cancel and verify reverse-order restoration
        cancel_res = cancel_leave_request("EMP001", req_id, session=session)
        assert cancel_res["success"] is True
        session.refresh(full_pay_row)
        session.refresh(half_pay_row)
        assert full_pay_row.remaining_days == 5
        assert full_pay_row.used_days == 10
        assert half_pay_row.remaining_days == 45
        assert half_pay_row.used_days == 0
    finally:
        session.close()


def test_sick_leave_exceeding_total_balance_rejected(temporary_database):
    """Requesting 85 days when 80 days total remain fails balance sufficiency."""
    session = temporary_database()
    try:
        draft = LeaveApplicationDraft(
            leave_type="Sick leave",
            start_date="2026-06-01",
            end_date="2026-09-28",  # 85 working days
            days_requested=85,
            is_complete=True,
        )
        res = validate_leave_policy("EMP001", draft, session=session)
        assert res.is_valid is False
        assert any("Insufficient leave balance" in v and "80.0 days available" in v for v in res.violations)
    finally:
        session.close()


def test_sick_leave_during_probation_permitted(temporary_database):
    """Sick leave is permitted from day 1 including probation per HC-PC-002 §2.1 & §2.2.2."""
    session = temporary_database()
    try:
        emp = session.query(Employee).filter(Employee.user_id == "EMP001").first()
        emp.probation_status = "Active"
        session.commit()

        draft = LeaveApplicationDraft(
            leave_type="Sick leave",
            start_date="2026-11-02",
            end_date="2026-11-03",
            days_requested=2,
            is_complete=True,
        )
        res = validate_leave_policy("EMP001", draft, session=session)
        assert res.is_valid is True
        assert not any("Probation restriction" in v for v in res.violations)
    finally:
        session.close()


# ==============================================================================
# 2. EMERGENCY LEAVE TESTS (HC-PC-001 §1.4.3 & HC-PC-003 §3.5.1)
# ==============================================================================

def test_emergency_leave_deducted_from_annual_leave(temporary_database):
    """
    Emergency leave is deducted from Annual leave balance.
    It is unplanned / same-day, so advance notice is not required.
    """
    session = temporary_database()
    try:
        annual_row = session.query(LeaveBalance).filter(
            LeaveBalance.employee_id == "EMP001", LeaveBalance.leave_type == "Annual leave"
        ).order_by(LeaveBalance.year.desc()).first()
        init_remaining = annual_row.remaining_days  # 15

        draft = LeaveApplicationDraft(
            leave_type="Emergency leave",
            start_date="2026-11-02",
            end_date="2026-11-03",
            days_requested=2,
            is_complete=True,
        )
        res = validate_leave_policy("EMP001", draft, as_of_date="2026-11-01", session=session)
        assert res.is_valid is True
        assert res.notice_compliant is True  # Exempt from notice
        assert res.balance_before == float(init_remaining)
        assert res.balance_after == float(init_remaining - 2)

        receipt = commit_leave_request("EMP001", res, reason="Family emergency", session=session)
        assert receipt["success"] is True

        app_res = approve_leave_request(manager_id="EMP003", request_id=receipt["request_id"], session=session)
        assert app_res["success"] is True

        session.refresh(annual_row)
        assert annual_row.remaining_days == init_remaining - 2

        # Cancel and restore
        cancel_leave_request("EMP001", receipt["request_id"], session=session)
        session.refresh(annual_row)
        assert annual_row.remaining_days == init_remaining
    finally:
        session.close()


def test_emergency_leave_exempt_from_probation_restriction(temporary_database):
    """Emergency leave is expressly permitted during probation per HC-PC-003 §3.5.1."""
    session = temporary_database()
    try:
        emp = session.query(Employee).filter(Employee.user_id == "EMP001").first()
        emp.probation_status = "Active"
        session.commit()

        draft = LeaveApplicationDraft(
            leave_type="Emergency leave",
            start_date="2026-11-02",
            end_date="2026-11-03",
            days_requested=2,
            is_complete=True,
        )
        res = validate_leave_policy("EMP001", draft, session=session)
        assert res.is_valid is True
        assert not any("Probation restriction" in v for v in res.violations)
    finally:
        session.close()


def test_emergency_leave_exceeding_annual_balance_rejected(temporary_database):
    """Emergency leave exceeding annual leave balance is rejected with clear message."""
    session = temporary_database()
    try:
        draft = LeaveApplicationDraft(
            leave_type="Emergency leave",
            start_date="2026-11-02",
            end_date="2026-11-27",  # 20 working days > 15 annual leave
            days_requested=20,
            is_complete=True,
        )
        res = validate_leave_policy("EMP001", draft, session=session)
        assert res.is_valid is False
        assert any("Emergency leave is deducted from annual leave" in v for v in res.violations)
    finally:
        session.close()


# ==============================================================================
# 3. ANNUAL LEAVE TESTS (HC-PC-001)
# ==============================================================================

def test_annual_leave_advance_notice_table_enforced(temporary_database):
    """
    HC-PC-001 §1.4.1 table:
    - 1-4 working days -> 5 working days notice
    - 5-9 working days -> 10 working days notice
    - 10+ working days -> 20 working days notice
    """
    assert get_required_notice_days(2) == 5
    assert get_required_notice_days(4) == 5
    assert get_required_notice_days(5) == 10
    assert get_required_notice_days(9) == 10
    assert get_required_notice_days(10) == 20
    assert get_required_notice_days(15) == 20

    session = temporary_database()
    try:
        # Request 10 working days starting with only 8 days notice -> Fails
        draft = LeaveApplicationDraft(
            leave_type="Annual leave",
            start_date="2026-11-16",
            end_date="2026-11-27",
            days_requested=10,
            is_complete=True,
        )
        res = validate_leave_policy("EMP001", draft, as_of_date="2026-11-04", session=session)
        assert res.is_valid is False
        assert res.notice_compliant is False
        assert any("requires at least 20 working days advance notice" in v for v in res.violations)
    finally:
        session.close()


# ==============================================================================
# 4. STATUTORY LEAVE CATEGORIES (UAE Labour Law)
# ==============================================================================

def test_maternity_leave_valid_and_cap(temporary_database):
    """Maternity leave up to 60 days is valid (Art. 30); exceeding 60 days fails."""
    session = temporary_database()
    try:
        draft_valid = LeaveApplicationDraft(
            leave_type="Maternity leave",
            start_date="2026-11-02",
            end_date="2026-12-11",  # 30 working days
            days_requested=30,
            is_complete=True,
        )
        res = validate_leave_policy("EMP001", draft_valid, session=session)
        assert res.is_valid is True

        draft_excess = LeaveApplicationDraft(
            leave_type="Maternity leave",
            start_date="2026-11-02",
            end_date="2027-02-15",  # > 60 working days
            days_requested=70,
            is_complete=True,
        )
        res_excess = validate_leave_policy("EMP001", draft_excess, session=session)
        assert res_excess.is_valid is False
        assert any("Maternity leave is capped at 60" in v for v in res_excess.violations)
    finally:
        session.close()


def test_paternity_leave_valid_and_cap(temporary_database):
    """Paternity leave up to 5 working days is valid (Art. 32(1)(b)); > 5 days fails."""
    session = temporary_database()
    try:
        draft_valid = LeaveApplicationDraft(
            leave_type="Paternity leave",
            start_date="2026-11-02",
            end_date="2026-11-06",  # 5 working days
            days_requested=5,
            is_complete=True,
        )
        res = validate_leave_policy("EMP001", draft_valid, session=session)
        assert res.is_valid is True

        draft_excess = LeaveApplicationDraft(
            leave_type="Paternity leave",
            start_date="2026-11-02",
            end_date="2026-11-10",  # 7 working days
            days_requested=7,
            is_complete=True,
        )
        res_excess = validate_leave_policy("EMP001", draft_excess, session=session)
        assert res_excess.is_valid is False
        assert any("Paternity leave is capped at 5.0 working days" in v for v in res_excess.violations)
    finally:
        session.close()


def test_bereavement_leave_valid_and_cap(temporary_database):
    """Bereavement leave up to 5 days is valid (Art. 32(1)(a)); > 5 days fails."""
    session = temporary_database()
    try:
        draft_valid = LeaveApplicationDraft(
            leave_type="Bereavement leave",
            start_date="2026-11-02",
            end_date="2026-11-06",
            days_requested=5,
            is_complete=True,
        )
        res = validate_leave_policy("EMP001", draft_valid, session=session)
        assert res.is_valid is True

        draft_excess = LeaveApplicationDraft(
            leave_type="Bereavement leave",
            start_date="2026-11-02",
            end_date="2026-11-10",
            days_requested=7,
            is_complete=True,
        )
        res_excess = validate_leave_policy("EMP001", draft_excess, session=session)
        assert res_excess.is_valid is False
        assert any("Bereavement leave is capped at 5 days" in v for v in res_excess.violations)
    finally:
        session.close()


def test_study_leave_eligibility_and_cap(temporary_database):
    """
    Study leave is capped at 10 working days/year and requires continuous service >= 2 years
    under UAE Labour Law Art. 32(2).
    """
    session = temporary_database()
    try:
        # Alia has 5 years service -> Eligible
        draft_valid = LeaveApplicationDraft(
            leave_type="Study leave",
            start_date="2026-11-02",
            end_date="2026-11-13",  # 10 working days
            days_requested=10,
            is_complete=True,
        )
        res = validate_leave_policy("EMP001", draft_valid, session=session)
        assert res.is_valid is True

        # Exceeding 10 days fails
        draft_excess = LeaveApplicationDraft(
            leave_type="Study leave",
            start_date="2026-11-02",
            end_date="2026-11-17",  # 12 working days
            days_requested=12,
            is_complete=True,
        )
        res_excess = validate_leave_policy("EMP001", draft_excess, session=session)
        assert res_excess.is_valid is False
        assert any("Study leave is capped at 10 working days" in v for v in res_excess.violations)

        # Employee with < 2 years service fails eligibility
        emp = session.query(Employee).filter(Employee.user_id == "EMP001").first()
        emp.years_of_service = 1
        session.commit()

        res_ineligible = validate_leave_policy("EMP001", draft_valid, session=session)
        assert res_ineligible.is_valid is False
        assert any("requires at least 2 years of continuous service" in v for v in res_ineligible.violations)
    finally:
        session.close()


def test_hajj_leave_valid_and_cap(temporary_database):
    """Hajj leave up to 30 days unpaid is valid (Art. 32(3)); > 30 days fails."""
    session = temporary_database()
    try:
        draft_valid = LeaveApplicationDraft(
            leave_type="Hajj leave",
            start_date="2026-11-02",
            end_date="2026-12-11",  # 30 working days
            days_requested=30,
            is_complete=True,
        )
        res = validate_leave_policy("EMP001", draft_valid, session=session)
        assert res.is_valid is True

        draft_excess = LeaveApplicationDraft(
            leave_type="Hajj leave",
            start_date="2026-11-02",
            end_date="2026-12-25",  # 40 working days
            days_requested=40,
            is_complete=True,
        )
        res_excess = validate_leave_policy("EMP001", draft_excess, session=session)
        assert res_excess.is_valid is False
        assert any("Hajj pilgrimage leave is capped at 30 days" in v for v in res_excess.violations)
    finally:
        session.close()


def test_unpaid_leave_valid(temporary_database):
    """Unpaid leave has no paid balance requirement and validates successfully."""
    session = temporary_database()
    try:
        draft = LeaveApplicationDraft(
            leave_type="Unpaid leave",
            start_date="2026-11-02",
            end_date="2026-11-06",
            days_requested=5,
            is_complete=True,
        )
        res = validate_leave_policy("EMP001", draft, session=session)
        assert res.is_valid is True
        assert res.balance_before == 0.0
        assert res.balance_after == 0.0
    finally:
        session.close()
