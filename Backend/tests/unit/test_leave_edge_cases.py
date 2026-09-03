"""
Comprehensive Edge Case Tests for Leave Agent and Business Rule Validation.
"""

import pytest
from app.database.tables import Employee, LeaveBalance, LeaveRequest
from app.services.leave_service import (
    approve_leave_request,
    calculate_working_days,
    commit_leave_request,
    normalize_leave_type,
    reject_leave_request,
    validate_leave_policy,
)
from app.workflow.structured_outputs import LeaveApplicationDraft


def test_inverted_dates_rejected(temporary_database):
    """Start date later than end date must fail validation."""
    session = temporary_database()
    try:
        draft = LeaveApplicationDraft(
            leave_type="Annual leave",
            start_date="2026-10-20",
            end_date="2026-10-10",
            days_requested=5,
            is_complete=True,
        )
        res = validate_leave_policy("EMP001", draft, session=session)
        assert res.is_valid is False
        assert any("cannot be earlier than start date" in v for v in res.violations)
    finally:
        session.close()


def test_invalid_date_format_rejected(temporary_database):
    """Malformed date formats must be caught cleanly without raising an unhandled 500 error."""
    session = temporary_database()
    try:
        draft = LeaveApplicationDraft(
            leave_type="Annual leave",
            start_date="2026-99-99",
            end_date="2026-10-16",
            days_requested=5,
            is_complete=True,
        )
        res = validate_leave_policy("EMP001", draft, session=session)
        assert res.is_valid is False
        assert any("Invalid date format" in v for v in res.violations)
    finally:
        session.close()


def test_weekend_only_date_range_rejected(temporary_database):
    """Leave requests on Saturday-Sunday (non-working days) must be flagged with 0 working days."""
    session = temporary_database()
    try:
        draft = LeaveApplicationDraft(
            leave_type="Annual leave",
            start_date="2026-10-17",  # Saturday
            end_date="2026-10-18",    # Sunday
            days_requested=2,
            is_complete=True,
        )
        res = validate_leave_policy("EMP001", draft, session=session)
        assert res.is_valid is False
        assert res.working_days == 0
        assert any("weekend non-working days" in v for v in res.violations)
    finally:
        session.close()


def test_public_holiday_date_range_rejected(temporary_database):
    """Leave requests solely on official UAE Public Holidays (e.g. National Day) must be rejected with policy citation."""
    session = temporary_database()
    try:
        draft = LeaveApplicationDraft(
            leave_type="Annual leave",
            start_date="2026-12-02",  # UAE National Day
            end_date="2026-12-03",    # National Day Holiday
            days_requested=2,
            is_complete=True,
        )
        res = validate_leave_policy("EMP001", draft, session=session)
        assert res.is_valid is False
        assert res.working_days == 0
        assert any("UAE Public Holidays" in v for v in res.violations)
    finally:
        session.close()


def test_public_holiday_in_middle_of_leave_deducts_only_working_days():
    """
    Requested from Monday 2026-11-30 to Friday 2026-12-04.
    Dec 1 (Commemoration Day), Dec 2 (National Day), Dec 3 (Holiday) are public holidays.
    Only Nov 30 (Mon) and Dec 4 (Fri) are working days -> exactly 2 working days.
    """
    days = calculate_working_days("2026-11-30", "2026-12-04")
    assert days == 2


def test_overlapping_leave_request_rejected(temporary_database):
    """An employee cannot book overlapping leave when another request is already active/pending."""
    session = temporary_database()
    try:
        # Create an active pending leave request for Alia
        existing = LeaveRequest(
            employee_id="EMP001",
            leave_type="Annual Leave",
            start_date="2026-10-12",
            end_date="2026-10-16",
            days_requested=5,
            status="Pending",
            approver_name="Maitha Al Mazrouei",
        )
        session.add(existing)
        session.commit()

        # Try to apply for dates overlapping with it (e.g. 2026-10-15 to 2026-10-20)
        draft = LeaveApplicationDraft(
            leave_type="Annual leave",
            start_date="2026-10-15",
            end_date="2026-10-20",
            days_requested=4,
            is_complete=True,
        )
        res = validate_leave_policy("EMP001", draft, session=session)
        assert res.is_valid is False
        assert any("Conflicting leave request" in v for v in res.violations)
    finally:
        session.close()


def test_insufficient_balance_rejected(temporary_database):
    """Requesting more days than the remaining balance must fail."""
    session = temporary_database()
    try:
        # Set balance to 2 days
        bal = session.query(LeaveBalance).filter(LeaveBalance.employee_id == "EMP001", LeaveBalance.leave_type == "Annual leave").first()
        if bal:
            bal.remaining_days = 2
            session.commit()

        draft = LeaveApplicationDraft(
            leave_type="Annual leave",
            start_date="2026-11-09",
            end_date="2026-11-13",
            days_requested=5,
            is_complete=True,
        )
        res = validate_leave_policy("EMP001", draft, session=session)
        assert res.is_valid is False
        assert any("Insufficient leave balance" in v for v in res.violations)
    finally:
        session.close()


def test_short_notice_period_annual_leave_rejected(temporary_database):
    """Applying for 10 days of annual leave with only 1 day notice must fail notice compliance."""
    session = temporary_database()
    try:
        # 10 working days requires 10 working days notice per HC-PC-001 §1.4
        draft = LeaveApplicationDraft(
            leave_type="Annual leave",
            start_date="2026-09-07",
            end_date="2026-09-18",
            days_requested=10,
            is_complete=True,
        )
        # As of 2026-09-04 (Friday), starting 2026-09-07 (Monday) gives only 0 notice days
        res = validate_leave_policy("EMP001", draft, as_of_date="2026-09-04", session=session)
        assert res.is_valid is False
        assert res.notice_compliant is False
        assert any("Notice period requirement not met" in v for v in res.violations)
    finally:
        session.close()


def test_probationary_employee_annual_leave_restricted(temporary_database):
    """An employee on active probation cannot apply for annual leave."""
    session = temporary_database()
    try:
        emp = session.query(Employee).filter(Employee.user_id == "EMP001").first()
        emp.probation_status = "Active"
        session.commit()

        draft = LeaveApplicationDraft(
            leave_type="Annual leave",
            start_date="2026-10-12",
            end_date="2026-10-16",
            days_requested=5,
            is_complete=True,
        )
        res = validate_leave_policy("EMP001", draft, session=session)
        assert res.is_valid is False
        assert any("Probation restriction" in v for v in res.violations)
    finally:
        session.close()


def test_sick_leave_requires_medical_certificate(temporary_database):
    """Sick leave for more than 2 consecutive working days flags medical certificate requirement."""
    session = temporary_database()
    try:
        draft = LeaveApplicationDraft(
            leave_type="Sick leave",
            start_date="2026-10-12",
            end_date="2026-10-15",
            days_requested=4,
            is_complete=True,
        )
        res = validate_leave_policy("EMP001", draft, session=session)
        assert res.requires_medical_certificate is True
    finally:
        session.close()


def test_colloquial_leave_normalization():
    """Colloquial words should normalize to their standard policy leave types."""
    assert normalize_leave_type("doctor appointment illness") == "Sick leave"
    assert normalize_leave_type("maternity leave for new baby") == "Maternity leave"
    assert normalize_leave_type("paternity leave") == "Paternity leave"
    assert normalize_leave_type("compassionate bereavement leave") == "Bereavement leave"
    assert normalize_leave_type("hajj pilgrimage") == "Hajj leave"
    assert normalize_leave_type("exam study leave") == "Study leave"
    assert normalize_leave_type("unpaid leave without pay") == "Unpaid leave"
    assert normalize_leave_type("urgent emergency leave") == "Emergency leave"
    assert normalize_leave_type("annual holidays") == "Annual leave"


def test_non_existent_employee_handled_safely(temporary_database):
    session = temporary_database()
    try:
        draft = LeaveApplicationDraft(
            leave_type="Annual leave",
            start_date="2026-10-12",
            end_date="2026-10-16",
            days_requested=5,
            is_complete=True,
        )
        res = validate_leave_policy("EMP_GHOST", draft, session=session)
        assert res.is_valid is False
        assert any("not found" in v for v in res.violations)
    finally:
        session.close()


def test_approve_already_approved_or_missing_request(temporary_database):
    session = temporary_database()
    try:
        # Non-existent request ID
        res_missing = approve_leave_request(manager_id="EMP003", request_id=99999, session=session)
        assert res_missing["success"] is False
        assert "not found" in res_missing["message"]

        # Create approved request
        req = LeaveRequest(
            employee_id="EMP001",
            leave_type="Annual Leave",
            start_date="2026-10-12",
            end_date="2026-10-16",
            days_requested=5,
            status="Approved",
            approver_name="Maitha Al Mazrouei",
        )
        session.add(req)
        session.commit()
        session.refresh(req)

        # Try to approve again
        res_dup = approve_leave_request(manager_id="EMP003", request_id=req.id, session=session)
        assert res_dup["success"] is False
        assert "already Approved" in res_dup["message"]
    finally:
        session.close()


def test_reject_already_rejected_request(temporary_database):
    session = temporary_database()
    try:
        req = LeaveRequest(
            employee_id="EMP001",
            leave_type="Annual Leave",
            start_date="2026-10-12",
            end_date="2026-10-16",
            days_requested=5,
            status="Rejected",
            approver_name="Maitha Al Mazrouei",
        )
        session.add(req)
        session.commit()
        session.refresh(req)

        res = reject_leave_request(manager_id="EMP003", request_id=req.id, reason="Testing", session=session)
        assert res["success"] is False
        assert "already Rejected" in res["message"]
    finally:
        session.close()
