"""
Leave and Absence Service: Deterministic business rules, policy validation, and transactions.
"""

from datetime import date, datetime, timedelta
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.database.engine import SessionLocal
from app.database.tables import Employee, LeaveBalance, LeaveRequest
from app.workflow.structured_outputs import LeaveApplicationDraft, LeaveValidationResult

logger = logging.getLogger(__name__)

# Known UAE public holidays for 2026 (YYYY-MM-DD)
UAE_PUBLIC_HOLIDAYS_2026 = {
    "2026-01-01",  # New Year's Day
    "2026-03-20",  # Eid Al Fitr (approx)
    "2026-03-21",
    "2026-03-22",
    "2026-05-27",  # Arafat Day (approx)
    "2026-05-28",  # Eid Al Adha (approx)
    "2026-05-29",
    "2026-06-17",  # Islamic New Year
    "2026-12-01",  # Commemoration Day
    "2026-12-02",  # UAE National Day
    "2026-12-03",
}


def parse_iso_date(date_str: str) -> date:
    """Parse YYYY-MM-DD string to date object."""
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def calculate_working_days(start_date: str, end_date: str) -> int:
    """
    Calculate the number of business working days (Monday - Friday)
    between start_date and end_date inclusive, excluding weekends and public holidays.
    """
    d_start = parse_iso_date(start_date)
    d_end = parse_iso_date(end_date)
    if d_end < d_start:
        return 0

    working_days = 0
    curr = d_start
    while curr <= d_end:
        # 0 = Monday, 4 = Friday, 5 = Saturday, 6 = Sunday
        is_weekend = curr.weekday() in (5, 6)
        iso_str = curr.strftime("%Y-%m-%d")
        is_holiday = iso_str in UAE_PUBLIC_HOLIDAYS_2026

        if not is_weekend and not is_holiday:
            working_days += 1
        curr += timedelta(days=1)

    return working_days


def calculate_notice_days(request_date: str, start_date: str) -> int:
    """Calculate working days between the request date and leave start date."""
    d_req = parse_iso_date(request_date)
    d_start = parse_iso_date(start_date)
    if d_start <= d_req:
        return 0
    return calculate_working_days(
        (d_req + timedelta(days=1)).strftime("%Y-%m-%d"),
        (d_start - timedelta(days=1)).strftime("%Y-%m-%d"),
    )


def get_required_notice_days(working_days: int) -> int:
    """
    Policy clause HC-PC-001 §1.4.1:
    - 1–4 working days of annual leave: 5 working days notice
    - 5–9 working days of annual leave: 10 working days notice
    - 10+ working days of annual leave: 20 working days notice
    """
    if working_days <= 4:
        return 5
    if 5 <= working_days <= 9:
        return 10
    return 20


def normalize_leave_type(raw_type: str) -> str:
    """Map colloquial leave mentions to official DB leave types."""
    lower = (raw_type or "").strip().lower()
    if any(w in lower for w in ["sick", "medical", "ill", "doctor", "hospital"]):
        return "Sick leave"
    if any(w in lower for w in ["emergency", "urgent"]):
        return "Emergency leave"
    if any(w in lower for w in ["unpaid", "without pay"]):
        return "Unpaid leave"
    if any(w in lower for w in ["maternity", "mother", "childbirth"]):
        return "Maternity leave"
    if any(w in lower for w in ["paternity", "parental", "father"]):
        return "Paternity leave"
    if any(w in lower for w in ["bereavement", "compassionate", "mourning", "death", "condolence"]):
        return "Bereavement leave"
    if any(w in lower for w in ["hajj", "pilgrimage"]):
        return "Hajj leave"
    if any(w in lower for w in ["study", "exam"]):
        return "Study leave"
    return "Annual leave"


def validate_leave_policy(
    employee_id: str,
    draft: LeaveApplicationDraft,
    session: Optional[Session] = None,
    as_of_date: Optional[str] = None,
) -> LeaveValidationResult:
    """
    Deterministically validate the leave application draft against
    the employee's database records and company HR policies.
    """
    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        employee = session.query(Employee).filter(Employee.user_id == employee_id).first()
        if not employee:
            return LeaveValidationResult(
                is_valid=False,
                violations=[f"Employee record for ID {employee_id} not found."],
                leave_type=draft.leave_type,
                start_date=draft.start_date or "",
                end_date=draft.end_date or "",
                working_days=0,
                balance_before=0.0,
                balance_after=0.0,
                notice_days_provided=0,
                notice_days_required=0,
                notice_compliant=False,
                approver_name="",
            )

        leave_type = normalize_leave_type(draft.leave_type)
        start_date_str = draft.start_date or date.today().strftime("%Y-%m-%d")
        end_date_str = draft.end_date or start_date_str

        # 0. Date syntax validation
        try:
            d_start = parse_iso_date(start_date_str)
            d_end = parse_iso_date(end_date_str)
        except (ValueError, TypeError):
            return LeaveValidationResult(
                is_valid=False,
                violations=["Invalid date format: Please provide dates in standard YYYY-MM-DD format."],
                leave_type=leave_type,
                start_date=start_date_str,
                end_date=end_date_str,
                working_days=0,
                balance_before=0.0,
                balance_after=0.0,
                notice_days_provided=0,
                notice_days_required=0,
                notice_compliant=False,
                approver_name=employee.manager_name,
            )

        # Inverted date range check
        if d_end < d_start:
            return LeaveValidationResult(
                is_valid=False,
                violations=[f"Invalid date range: End date ({end_date_str}) cannot be earlier than start date ({start_date_str})."],
                leave_type=leave_type,
                start_date=start_date_str,
                end_date=end_date_str,
                working_days=0,
                balance_before=0.0,
                balance_after=0.0,
                notice_days_provided=0,
                notice_days_required=0,
                notice_compliant=False,
                approver_name=employee.manager_name,
            )

        # Retrieve current balance according to leave type
        is_sick = "sick" in leave_type.lower()
        is_emergency = "emergency" in leave_type.lower()
        is_unpaid = "unpaid" in leave_type.lower()
        is_maternity = "maternity" in leave_type.lower()
        is_paternity = "paternity" in leave_type.lower()
        is_bereavement = "bereavement" in leave_type.lower()
        is_study = "study" in leave_type.lower()
        is_hajj = "hajj" in leave_type.lower()
        balance_unit = "days"

        if is_sick:
            # HC-PC-002 §2.2.1: Sick leave is held across three pay tranches (full pay, half pay, unpaid).
            sick_tranches = (
                session.query(LeaveBalance)
                .filter(
                    LeaveBalance.employee_id == employee_id,
                    LeaveBalance.leave_type.like("Sick leave%"),
                )
                .order_by(LeaveBalance.year.desc())
                .all()
            )
            current_year = max((b.year for b in sick_tranches), default=2026)
            active_tranches = [b for b in sick_tranches if b.year == current_year]
            balance_before = float(sum(b.remaining_days for b in active_tranches))
        elif is_emergency:
            # HC-PC-001 §1.4.3: Emergency leave is deducted from the employee's Annual leave balance.
            annual_rows = (
                session.query(LeaveBalance)
                .filter(
                    LeaveBalance.employee_id == employee_id,
                    LeaveBalance.leave_type == "Annual leave",
                )
                .order_by(LeaveBalance.year.desc())
                .all()
            )
            current_year = max((b.year for b in annual_rows), default=2026)
            active_annual = [b for b in annual_rows if b.year == current_year]
            balance_before = float(active_annual[0].remaining_days) if active_annual else 0.0
        elif is_unpaid:
            balance_before = 0.0
        elif is_maternity:
            balance_before = 60.0  # UAE Labour Law Art. 30 (45 full pay + 15 half pay)
        elif is_paternity:
            balance_before = 5.0   # UAE Labour Law Art. 32(1)(b)
        elif is_bereavement:
            balance_before = 5.0   # UAE Labour Law Art. 32(1)(a)
        elif is_study:
            balance_before = 10.0  # UAE Labour Law Art. 32
        elif is_hajj:
            balance_before = 30.0  # UAE Labour Law Art. 32
        else:
            # Annual leave: read from the latest leave year on file
            annual_rows = (
                session.query(LeaveBalance)
                .filter(
                    LeaveBalance.employee_id == employee_id,
                    LeaveBalance.leave_type == "Annual leave",
                )
                .order_by(LeaveBalance.year.desc())
                .all()
            )
            current_year = max((b.year for b in annual_rows), default=2026)
            active_annual = [b for b in annual_rows if b.year == current_year]
            balance_before = float(active_annual[0].remaining_days) if active_annual else 0.0
            if active_annual:
                balance_unit = active_annual[0].unit

        working_days = calculate_working_days(start_date_str, end_date_str)
        if working_days <= 0:
            holidays_in_range = []
            curr = d_start
            while curr <= d_end:
                iso = curr.strftime("%Y-%m-%d")
                if iso in UAE_PUBLIC_HOLIDAYS_2026:
                    holidays_in_range.append(iso)
                curr += timedelta(days=1)

            holiday_names = {
                "2026-01-01": "New Year's Day",
                "2026-03-20": "Eid Al Fitr",
                "2026-03-21": "Eid Al Fitr",
                "2026-03-22": "Eid Al Fitr",
                "2026-05-27": "Arafat Day",
                "2026-05-28": "Eid Al Adha",
                "2026-05-29": "Eid Al Adha",
                "2026-06-17": "Islamic New Year",
                "2026-12-01": "Commemoration Day",
                "2026-12-02": "UAE National Day",
                "2026-12-03": "National Day Holiday",
            }

            if holidays_in_range:
                names = ", ".join(f"{h} ({holiday_names.get(h, 'Public Holiday')})" for h in holidays_in_range)
                msg = (
                    f"The requested dates fall on official UAE Public Holidays: {names}. "
                    "Under UAE Labour Law & HC-PC-001 §1.4.3, official public holidays are paid non-working days and do not require leave deduction. "
                    "You are already off on these dates! Please select dates that include regular working days."
                )
            else:
                msg = "The requested date range contains 0 working days as it falls entirely on weekend non-working days (Saturday/Sunday)."

            return LeaveValidationResult(
                is_valid=False,
                violations=[msg],
                leave_type=leave_type,
                start_date=start_date_str,
                end_date=end_date_str,
                working_days=0,
                balance_before=balance_before,
                balance_after=balance_before,
                notice_days_provided=0,
                notice_days_required=0,
                notice_compliant=True,
                approver_name=employee.manager_name,
            )

        violations = []

        # 1. Overlapping leave request check (Duplicate / Conflict)
        overlapping = (
            session.query(LeaveRequest)
            .filter(
                LeaveRequest.employee_id == employee_id,
                LeaveRequest.status.in_(["Pending", "Approved"]),
                LeaveRequest.start_date <= end_date_str,
                LeaveRequest.end_date >= start_date_str,
            )
            .first()
        )
        if overlapping:
            violations.append(
                f"Conflicting leave request: You already have a {overlapping.status} leave request #{overlapping.id} "
                f"({overlapping.leave_type}) from {overlapping.start_date} to {overlapping.end_date} covering these dates."
            )

        # 2. Balance sufficiency check
        if not is_unpaid and balance_before < working_days:
            if is_sick:
                violations.append(
                    f"Insufficient leave balance: You have {balance_before:.1f} days available across sick leave tranches, "
                    f"but requested {working_days} working days."
                )
            elif is_emergency:
                violations.append(
                    f"Insufficient leave balance: Emergency leave is deducted from annual leave. "
                    f"You have {balance_before:.1f} days of annual leave available, but requested {working_days} working days."
                )
            elif is_maternity:
                violations.append(
                    f"Statutory leave limit exceeded: Maternity leave is capped at 60 calendar days under UAE Labour Law Art. 30, "
                    f"but {working_days} working days were requested."
                )
            elif is_paternity:
                violations.append(
                    f"Statutory leave limit exceeded: Paternity leave is capped at 5.0 working days under UAE Labour Law Art. 32(1)(b), "
                    f"but {working_days} working days were requested."
                )
            elif is_bereavement:
                violations.append(
                    f"Statutory leave limit exceeded: Bereavement leave is capped at 5 days under UAE Labour Law Art. 32(1)(a), "
                    f"but {working_days} working days were requested."
                )
            elif is_study:
                violations.append(
                    f"Statutory leave limit exceeded: Study leave is capped at 10 working days under UAE Labour Law Art. 32(2), "
                    f"but {working_days} working days were requested."
                )
            elif is_hajj:
                violations.append(
                    f"Statutory leave limit exceeded: Hajj pilgrimage leave is capped at 30 days under UAE Labour Law Art. 32(3), "
                    f"but {working_days} working days were requested."
                )
            else:
                violations.append(
                    f"Insufficient leave balance: You have {balance_before:.1f} {balance_unit} "
                    f"available, but requested {working_days} working days."
                )

        # Additional statutory check for Study Leave (UAE Labour Law Art. 32(2): requires at least 2 years continuous service)
        if is_study and employee.years_of_service < 2:
            violations.append(
                "Study leave eligibility requirement not met: UAE Labour Law Art. 32(2) requires at least "
                "2 years of continuous service to be eligible for study leave."
            )

        # 3. Advance notice check (for Annual Leave per HC-PC-001 §1.4)
        # Sick leave, emergency leave, bereavement, etc. are unplanned/exempt
        today_str = as_of_date or date.today().strftime("%Y-%m-%d")
        notice_days_provided = calculate_notice_days(today_str, start_date_str)
        notice_days_required = get_required_notice_days(working_days) if leave_type == "Annual leave" else 0
        notice_compliant = True

        if leave_type == "Annual leave" and notice_days_provided < notice_days_required:
            notice_compliant = False
            violations.append(
                f"Notice period requirement not met: HC-PC-001 §1.4 requires at least {notice_days_required} "
                f"working days advance notice for {working_days} days of annual leave. "
                f"Only {notice_days_provided} working days notice was provided."
            )

        # 4. Active probation restriction check (HC-PC-003 §3.5.1 / §3.2)
        # Annual leave cannot be taken during active probation without special HR approval.
        # Emergency leave is expressly exempt (HC-PC-003 §3.5.1).
        # Sick leave is permitted from day one (HC-PC-002 §2.1 & §2.2.2).
        if leave_type == "Annual leave" and employee.probation_status in ("Active", "Extended"):
            violations.append(
                f"Probation restriction: Your probation status is '{employee.probation_status}'. "
                "Under Probation Policy HC-PC-003 §3.2, annual leave cannot be taken during active probation "
                "without special HR Director authorization."
            )

        # 5. Medical certificate requirement for sick leave (HC-PC-002 §2.3.2)
        # Absences of 1 or 2 consecutive days permit self-certification; >2 working days requires medical certificate.
        requires_medical_certificate = False
        if is_sick and working_days > 2:
            requires_medical_certificate = True

        balance_after = max(0.0, balance_before - working_days) if not is_unpaid else 0.0
        is_valid = len(violations) == 0

        return LeaveValidationResult(
            is_valid=is_valid,
            violations=violations,
            leave_type=leave_type,
            start_date=start_date_str,
            end_date=end_date_str,
            working_days=working_days,
            balance_before=balance_before,
            balance_after=balance_after,
            notice_days_provided=notice_days_provided,
            notice_days_required=notice_days_required,
            notice_compliant=notice_compliant,
            requires_medical_certificate=requires_medical_certificate,
            approver_name=employee.manager_name,
        )

    finally:
        if close_session:
            session.close()


def commit_leave_request(
    employee_id: str,
    validation: LeaveValidationResult,
    reason: Optional[str] = None,
    session: Optional[Session] = None,
) -> dict:
    """
    Atomically insert a new LeaveRequest and update the LeaveBalance in the database.
    """
    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        employee = session.query(Employee).filter(Employee.user_id == employee_id).first()
        if not employee:
            raise ValueError(f"Employee {employee_id} not found")

        # 1. Create LeaveRequest record with status 'Pending'
        new_request = LeaveRequest(
            employee_id=employee_id,
            leave_type=validation.leave_type,
            start_date=validation.start_date,
            end_date=validation.end_date,
            days_requested=validation.working_days,
            status="Pending",
            approver_name=validation.approver_name or employee.manager_name,
            notes=reason or "Submitted via Policy & Leave Concierge agent",
        )
        session.add(new_request)

        # 2. Retrieve balance without deducting until manager approval
        is_sick = "sick" in validation.leave_type.lower()
        is_emergency = "emergency" in validation.leave_type.lower()

        if is_sick:
            sick_tranches = (
                session.query(LeaveBalance)
                .filter(
                    LeaveBalance.employee_id == employee_id,
                    LeaveBalance.leave_type.like("Sick leave%"),
                )
                .order_by(LeaveBalance.year.desc())
                .all()
            )
            current_year = max((b.year for b in sick_tranches), default=2026)
            active_tranches = [b for b in sick_tranches if b.year == current_year]
            current_bal = float(sum(b.remaining_days for b in active_tranches))
        elif is_emergency:
            annual_rows = (
                session.query(LeaveBalance)
                .filter(
                    LeaveBalance.employee_id == employee_id,
                    LeaveBalance.leave_type == "Annual leave",
                )
                .order_by(LeaveBalance.year.desc())
                .all()
            )
            current_year = max((b.year for b in annual_rows), default=2026)
            active_annual = [b for b in annual_rows if b.year == current_year]
            current_bal = float(active_annual[0].remaining_days) if active_annual else 0.0
        else:
            balance_rows = (
                session.query(LeaveBalance)
                .filter(
                    LeaveBalance.employee_id == employee_id,
                    LeaveBalance.leave_type == validation.leave_type,
                )
                .order_by(LeaveBalance.year.desc())
                .all()
            )
            current_bal = float(balance_rows[0].remaining_days) if balance_rows else validation.balance_before

        session.commit()
        session.refresh(new_request)

        # Dispatch Manager Notification
        try:
            from app.services.notification_service import create_notification
            emp = session.query(Employee).filter(Employee.user_id == employee_id).first()
            manager_target_id = emp.manager_id if emp and emp.manager_id else None
            if not manager_target_id and emp and emp.manager_name:
                mgr_record = session.query(Employee).filter(Employee.name == emp.manager_name).first()
                if mgr_record:
                    manager_target_id = mgr_record.user_id

            if manager_target_id:
                create_notification(
                    recipient_id=manager_target_id,
                    sender_id=employee_id,
                    event_type="LEAVE_REQUESTED",
                    title=f"Leave Request: {emp.name if emp else employee_id}",
                    message=(
                        f"{emp.name if emp else employee_id} requested {validation.working_days} working days "
                        f"of {validation.leave_type} ({validation.start_date} to {validation.end_date})."
                    ),
                    action_payload={
                        "request_id": new_request.id,
                        "employee_id": employee_id,
                        "employee_name": emp.name if emp else employee_id,
                        "leave_type": validation.leave_type,
                        "start_date": validation.start_date,
                        "end_date": validation.end_date,
                        "days_requested": validation.working_days,
                    },
                    session=session,
                )
        except Exception as notif_err:
            logger.warning(f"Could not dispatch manager notification for leave request #{new_request.id}: {notif_err}")

        logger.info(
            f"Successfully queued pending leave request ID #{new_request.id} for {employee_id}: "
            f"{validation.working_days} days of {validation.leave_type} awaiting approval by {new_request.approver_name}"
        )

        return {
            "success": True,
            "request_id": new_request.id,
            "status": "Pending",
            "leave_type": new_request.leave_type,
            "start_date": new_request.start_date,
            "end_date": new_request.end_date,
            "days_requested": new_request.days_requested,
            "approver_name": new_request.approver_name,
            "current_balance": current_bal,
            "projected_balance": validation.balance_after,
            "created_at": new_request.created_at.strftime("%Y-%m-%d %H:%M:%S") if new_request.created_at else "",
        }
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to commit leave request: {e}", exc_info=True)
        raise
    finally:
        if close_session:
            session.close()


def approve_leave_request(
    manager_id: str,
    request_id: int,
    session: Optional[Session] = None,
) -> dict:
    """
    Manager approves a pending leave request:
    1. Validates request is Pending.
    2. Officially debits the LeaveBalance.
    3. Marks LeaveRequest as Approved.
    4. Dispatches employee approval notification.
    """
    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        req = session.query(LeaveRequest).filter(LeaveRequest.id == request_id).first()
        if not req:
            return {"success": False, "message": f"Leave request #{request_id} not found."}
        if req.status != "Pending":
            return {"success": False, "message": f"Leave request #{request_id} is already {req.status}."}

        applicant = session.query(Employee).filter(Employee.user_id == req.employee_id).first()
        manager = session.query(Employee).filter(Employee.user_id == manager_id).first()

        # Debit balance upon formal manager approval
        is_sick = "sick" in req.leave_type.lower()
        is_emergency = "emergency" in req.leave_type.lower()
        new_balance = 0.0

        if is_sick:
            # HC-PC-002 §2.2.1: Deduct from active year tranches in sequential order: full pay -> half pay -> unpaid
            all_sick = (
                session.query(LeaveBalance)
                .filter(
                    LeaveBalance.employee_id == req.employee_id,
                    LeaveBalance.leave_type.like("Sick leave%"),
                )
                .order_by(LeaveBalance.year.desc())
                .all()
            )
            current_year = max((b.year for b in all_sick), default=2026)
            active_tranches = [b for b in all_sick if b.year == current_year]
            active_tranches.sort(key=lambda b: (b.pay_rate_pct if b.pay_rate_pct is not None else 0), reverse=True)

            remaining_to_deduct = req.days_requested
            for tranche in active_tranches:
                if remaining_to_deduct <= 0:
                    break
                deduct = min(tranche.remaining_days, remaining_to_deduct)
                tranche.used_days += deduct
                tranche.remaining_days = max(0, tranche.remaining_days - deduct)
                remaining_to_deduct -= deduct
            new_balance = float(sum(b.remaining_days for b in active_tranches))
        elif is_emergency:
            # HC-PC-001 §1.4.3: Emergency leave is debited from Annual leave
            annual_rows = (
                session.query(LeaveBalance)
                .filter(
                    LeaveBalance.employee_id == req.employee_id,
                    LeaveBalance.leave_type == "Annual leave",
                )
                .order_by(LeaveBalance.year.desc())
                .all()
            )
            current_year = max((b.year for b in annual_rows), default=2026)
            active_annual = [b for b in annual_rows if b.year == current_year]
            if active_annual:
                annual_bal = active_annual[0]
                annual_bal.used_days += req.days_requested
                annual_bal.remaining_days = max(0, annual_bal.remaining_days - req.days_requested)
                new_balance = float(annual_bal.remaining_days)
        else:
            annual_rows = (
                session.query(LeaveBalance)
                .filter(
                    LeaveBalance.employee_id == req.employee_id,
                    LeaveBalance.leave_type == req.leave_type,
                )
                .order_by(LeaveBalance.year.desc())
                .all()
            )
            if annual_rows:
                current_year = max((b.year for b in annual_rows), default=2026)
                active_rows = [b for b in annual_rows if b.year == current_year]
                target_bal = active_rows[0] if active_rows else annual_rows[0]
                target_bal.used_days += req.days_requested
                target_bal.remaining_days = max(0, target_bal.remaining_days - req.days_requested)
                new_balance = float(target_bal.remaining_days)

        req.status = "Approved"
        session.commit()

        # Dispatch Employee Notification
        try:
            from app.services.notification_service import create_notification
            approver_display = manager.name if manager else req.approver_name
            create_notification(
                recipient_id=req.employee_id,
                sender_id=manager_id,
                event_type="LEAVE_APPROVED",
                title=f"Leave Request #{req.id} Approved 🎉",
                message=(
                    f"Your request for {req.days_requested} working days of {req.leave_type} "
                    f"({req.start_date} to {req.end_date}) has been approved by {approver_display}."
                ),
                action_payload={
                    "request_id": req.id,
                    "status": "Approved",
                    "approver_name": approver_display,
                    "leave_type": req.leave_type,
                    "start_date": req.start_date,
                    "end_date": req.end_date,
                    "days_requested": req.days_requested,
                },
                session=session,
            )
        except Exception as notif_err:
            logger.warning(f"Could not dispatch approval notification for request #{req.id}: {notif_err}")

        logger.info(f"Manager {manager_id} approved leave request #{req.id} for {req.employee_id}")

        return {
            "success": True,
            "request_id": req.id,
            "employee_id": req.employee_id,
            "employee_name": applicant.name if applicant else req.employee_id,
            "employee_email": applicant.email if applicant else "",
            "leave_type": req.leave_type,
            "start_date": req.start_date,
            "end_date": req.end_date,
            "days_requested": req.days_requested,
            "status": "Approved",
            "approver_name": manager.name if manager else req.approver_name,
            "manager_email": manager.email if manager else (applicant.manager_email if applicant else ""),
            "new_balance": new_balance,
        }
    except Exception as e:
        session.rollback()
        logger.error(f"Error approving leave request #{request_id}: {e}", exc_info=True)
        return {"success": False, "message": str(e)}
    finally:
        if close_session:
            session.close()


def reject_leave_request(
    manager_id: str,
    request_id: int,
    reason: str = "",
    session: Optional[Session] = None,
) -> dict:
    """Manager rejects a pending leave request and notifies employee."""
    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        req = session.query(LeaveRequest).filter(LeaveRequest.id == request_id).first()
        if not req:
            return {"success": False, "message": f"Leave request #{request_id} not found."}
        if req.status != "Pending":
            return {"success": False, "message": f"Leave request #{request_id} is already {req.status}."}

        applicant = session.query(Employee).filter(Employee.user_id == req.employee_id).first()
        manager = session.query(Employee).filter(Employee.user_id == manager_id).first()

        req.status = "Rejected"
        if reason:
            req.notes = f"{req.notes} | Rejected: {reason}".strip(" |")
        session.commit()

        # Dispatch Employee Rejection Notification
        try:
            from app.services.notification_service import create_notification
            approver_display = manager.name if manager else req.approver_name
            reason_text = f" Reason: {reason}" if reason else ""
            create_notification(
                recipient_id=req.employee_id,
                sender_id=manager_id,
                event_type="LEAVE_REJECTED",
                title=f"Leave Request #{req.id} Declined",
                message=(
                    f"Your request for {req.days_requested} days of {req.leave_type} "
                    f"was declined by {approver_display}.{reason_text}"
                ),
                action_payload={
                    "request_id": req.id,
                    "status": "Rejected",
                    "rejection_reason": reason,
                    "approver_name": approver_display,
                    "leave_type": req.leave_type,
                    "start_date": req.start_date,
                    "end_date": req.end_date,
                },
                session=session,
            )
        except Exception as notif_err:
            logger.warning(f"Could not dispatch rejection notification for request #{req.id}: {notif_err}")

        logger.info(f"Manager {manager_id} rejected leave request #{req.id} for {req.employee_id}")

        return {
            "success": True,
            "request_id": req.id,
            "employee_id": req.employee_id,
            "employee_name": applicant.name if applicant else req.employee_id,
            "leave_type": req.leave_type,
            "start_date": req.start_date,
            "end_date": req.end_date,
            "days_requested": req.days_requested,
            "status": "Rejected",
            "rejection_reason": reason,
            "approver_name": manager.name if manager else req.approver_name,
        }
    except Exception as e:
        session.rollback()
        logger.error(f"Error rejecting leave request #{request_id}: {e}", exc_info=True)
        return {"success": False, "message": str(e)}
    finally:
        if close_session:
            session.close()


def get_manager_pending_approvals(manager_id: str, session: Optional[Session] = None) -> list[dict]:
    """Retrieve all pending leave requests submitted to this manager by direct reports."""
    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        manager = session.query(Employee).filter(Employee.user_id == manager_id).first()
        if not manager:
            return []

        # Find direct reports
        direct_reports = (
            session.query(Employee)
            .filter((Employee.manager_id == manager_id) | (Employee.manager_name == manager.name))
            .all()
        )
        report_ids = [r.user_id for r in direct_reports]
        report_map = {r.user_id: r for r in direct_reports}

        pending_requests = (
            session.query(LeaveRequest)
            .filter(
                LeaveRequest.employee_id != manager_id,
                (LeaveRequest.employee_id.in_(report_ids)) | (LeaveRequest.approver_name == manager.name),
                LeaveRequest.status == "Pending",
            )
            .order_by(LeaveRequest.created_at.desc())
            .all()
        )

        results = []
        for req in pending_requests:
            emp = report_map.get(req.employee_id) or session.query(Employee).filter(Employee.user_id == req.employee_id).first()
            results.append({
                "request_id": req.id,
                "employee_id": req.employee_id,
                "employee_name": emp.name if emp else req.employee_id,
                "employee_role": emp.job_title or emp.role if emp else "",
                "leave_type": req.leave_type,
                "start_date": req.start_date,
                "end_date": req.end_date,
                "days_requested": req.days_requested,
                "notes": req.notes,
                "created_at": req.created_at.strftime("%Y-%m-%d") if req.created_at else "",
                "status": req.status,
            })
        return results
    finally:
        if close_session:
            session.close()


def get_pending_leave_requests(employee_id: str, session: Optional[Session] = None) -> list[dict]:
    """Retrieve all pending leave requests for the given employee."""
    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        requests = (
            session.query(LeaveRequest)
            .filter(
                LeaveRequest.employee_id == employee_id,
                LeaveRequest.status == "Pending",
            )
            .order_by(LeaveRequest.created_at.desc())
            .all()
        )
        return [
            {
                "id": req.id,
                "leave_type": req.leave_type,
                "start_date": req.start_date,
                "end_date": req.end_date,
                "days_requested": req.days_requested,
                "status": req.status,
                "approver_name": req.approver_name,
                "notes": req.notes,
                "created_at": req.created_at.strftime("%Y-%m-%d") if req.created_at else "",
            }
            for req in requests
        ]
    finally:
        if close_session:
            session.close()


def cancel_leave_request(employee_id: str, request_id: int, session: Optional[Session] = None) -> dict:
    """Cancel a pending leave request and restore the deducted balance."""
    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        req = (
            session.query(LeaveRequest)
            .filter(
                LeaveRequest.id == request_id,
                LeaveRequest.employee_id == employee_id,
            )
            .first()
        )
        if not req:
            return {"success": False, "message": f"Leave request #{request_id} not found for employee {employee_id}."}

        if req.status == "Cancelled":
            return {"success": False, "message": f"Leave request #{request_id} is already cancelled."}

        # Restore balance if it was previously approved and deducted
        is_sick = "sick" in req.leave_type.lower()
        is_emergency = "emergency" in req.leave_type.lower()
        restored_balance = None

        was_approved = (req.status == "Approved")
        if was_approved:
            if is_sick:
                all_sick = (
                    session.query(LeaveBalance)
                    .filter(
                        LeaveBalance.employee_id == employee_id,
                        LeaveBalance.leave_type.like("Sick leave%"),
                    )
                    .order_by(LeaveBalance.year.desc())
                    .all()
                )
                current_year = max((b.year for b in all_sick), default=2026)
                # Reverse order: unpaid (0%), half pay (50%), full pay (100%)
                active_tranches = [b for b in all_sick if b.year == current_year]
                active_tranches.sort(key=lambda b: (b.pay_rate_pct if b.pay_rate_pct is not None else 0), reverse=False)

                remaining_to_restore = req.days_requested
                for tranche in active_tranches:
                    if remaining_to_restore <= 0:
                        break
                    restore_amount = min(tranche.used_days, remaining_to_restore)
                    tranche.used_days = max(0, tranche.used_days - restore_amount)
                    tranche.remaining_days += restore_amount
                    remaining_to_restore -= restore_amount
                restored_balance = float(sum(b.remaining_days for b in active_tranches))
            elif is_emergency:
                annual_rows = (
                    session.query(LeaveBalance)
                    .filter(
                        LeaveBalance.employee_id == employee_id,
                        LeaveBalance.leave_type == "Annual leave",
                    )
                    .order_by(LeaveBalance.year.desc())
                    .all()
                )
                current_year = max((b.year for b in annual_rows), default=2026)
                active_annual = [b for b in annual_rows if b.year == current_year]
                if active_annual:
                    annual_bal = active_annual[0]
                    annual_bal.used_days = max(0, annual_bal.used_days - req.days_requested)
                    annual_bal.remaining_days += req.days_requested
                    restored_balance = float(annual_bal.remaining_days)
            else:
                balance_rows = (
                    session.query(LeaveBalance)
                    .filter(
                        LeaveBalance.employee_id == employee_id,
                        LeaveBalance.leave_type == req.leave_type,
                    )
                    .order_by(LeaveBalance.year.desc())
                    .all()
                )
                if balance_rows:
                    current_year = max((b.year for b in balance_rows), default=2026)
                    active_rows = [b for b in balance_rows if b.year == current_year]
                    target_bal = active_rows[0] if active_rows else balance_rows[0]
                    target_bal.used_days = max(0, target_bal.used_days - req.days_requested)
                    target_bal.remaining_days += req.days_requested
                    restored_balance = float(target_bal.remaining_days)

        req.status = "Cancelled"
        session.commit()

        return {
            "success": True,
            "request_id": req.id,
            "status": "Cancelled",
            "restored_days": req.days_requested if was_approved else 0,
            "current_balance": restored_balance,
            "message": f"Leave request #{request_id} ({req.days_requested} days of {req.leave_type}) has been cancelled.",
        }
    except Exception as e:
        session.rollback()
        logger.error(f"Error cancelling leave request #{request_id}: {e}", exc_info=True)
        return {"success": False, "message": str(e)}
    finally:
        if close_session:
            session.close()

