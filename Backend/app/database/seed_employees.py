"""
The eight employees the system is demonstrated with.

Data only. The code that writes them lives in seed_database.py.

Every number here is reconciled against the People Code rather than invented. That was
not true before: each employee held a flat 30-day annual entitlement, which is the top of
the ten-year service band at HC-PC-001 §1.2.2, so four of five contradicted the policy
they were meant to be read against. Sick leave held 15 days — the full-pay tranche from
HC-PC-002 §2.2.1 — presented as though it were the 90-day entitlement. And the grades
ran about five bands above the scale the policies cite, so the most junior employee sat
at the grade HC-PC-005 §5.3.2 uses to grant business-class travel.

Three invariants hold for every row, and are asserted in tests/unit/test_seed_employees:

    entitled_days   matches the service band, or a documented contractual exception
    used_days       equals the sum of approved requests of that type in that year
    remaining_days  equals entitled_days + carry_over_days - used_days

Each employee exists to make something answerable. EMP001 sits just below the
business-class grade and EMP004 just above it, so the same question has opposite correct
answers. EMP006 has sick absence spanning the date the pay tranches changed. EMP007 is
part-time in a role that cannot be done remotely. EMP008's record deliberately disagrees
with the service ladder, under a contract term the policy allows.
"""

from app.database.tables import Employee, ExpenseClaim, LeaveBalance, LeaveRequest, ManagerHistory

# HC-PC-002 §2.2.1. One entitlement, three pay rates, ninety days in total.
SICK_TRANCHES = (("Sick leave (full pay)", 15, 100), ("Sick leave (half pay)", 45, 50),
                 ("Sick leave (unpaid)", 30, 0))


def sick_leave_rows(days_used: int, year: int = 2026) -> list[LeaveBalance]:
    """
    The three tranche rows for an employee who has used `days_used` sick days.

    Days fill the tranches in order, which is what the policy says happens: the first 15
    are paid in full, the next 45 at half pay, the last 30 unpaid.
    """
    rows, remaining_to_place = [], days_used
    for leave_type, entitled, pay_rate in SICK_TRANCHES:
        used = min(remaining_to_place, entitled)
        remaining_to_place -= used
        rows.append(LeaveBalance(
            leave_type=leave_type, entitled_days=entitled, used_days=used,
            remaining_days=entitled - used, carry_over_days=0, year=year,
            pay_rate_pct=pay_rate, accrued_days=float(entitled),
        ))
    return rows


def annual_leave_row(entitled: int, used: int, carry_over: int = 0,
                     accrued: float | None = None, year: int = 2026) -> LeaveBalance:
    """One annual leave row, with the balance identity applied rather than typed twice."""
    return LeaveBalance(
        leave_type="Annual leave", entitled_days=entitled, used_days=used,
        remaining_days=entitled + carry_over - used, carry_over_days=carry_over,
        year=year, pay_rate_pct=None,
        accrued_days=float(entitled) if accrued is None else accrued,
    )


def build_seed_employees() -> list[dict]:
    """Fresh, unattached records for the eight demonstration employees."""
    return [
        {
            # Grade 5 — one band BELOW the business-class threshold at HC-PC-005 §5.3.2.
            # 4 years' service puts him in the 3–5 band: 24 days, not 30.
            "employee": Employee(
                user_id="EMP001", name="Ahmed Abdullah Al Mansoori",
                name_ar="أحمد عبد الله المنصوري", role="Senior Consultant",
                job_title="Senior Consultant", department="Strategy & Transformation",
                grade="Grade 5", email="ahmed.mansoori@hcservices.ae",
                phone="+971 50 123 4567", location="Dubai Office, Level 14",
                start_date="2022-03-15", years_of_service=4, probation_status="Passed",
                manager_name="Fatima Maryam Al Qubaisi", manager_id="EMP002",
                manager_email="fatima.qubaisi@hcservices.ae",
                manager_role="VP, People & Culture",
            ),
            "balances": [
                annual_leave_row(entitled=24, used=12, carry_over=3),
                *sick_leave_rows(days_used=10),
                # Last year, so "how does this year compare?" has something to compare to.
                annual_leave_row(entitled=24, used=21, carry_over=0, year=2025),
            ],
            "manager_history": [
                ManagerHistory(previous_manager="Khalifa Saeed Al Nahyan",
                               current_manager="Fatima Maryam Al Qubaisi",
                               effective_date="2025-10-01",
                               change_reason="Promotion to Senior Consultant & Strategy alignment"),
                ManagerHistory(previous_manager="Initial Onboarding Manager",
                               current_manager="Khalifa Saeed Al Nahyan",
                               effective_date="2022-03-15",
                               change_reason="Initial assignment upon joining Strategy team"),
            ],
            "leave_requests": [
                LeaveRequest(leave_type="Annual Leave", start_date="2026-01-12",
                             end_date="2026-01-16", days_requested=5, status="Approved",
                             approver_name="Fatima Maryam Al Qubaisi",
                             notes="Winter holiday with family"),
                LeaveRequest(leave_type="Annual Leave", start_date="2026-04-10",
                             end_date="2026-04-20", days_requested=7, status="Approved",
                             approver_name="Fatima Maryam Al Qubaisi",
                             notes="Spring break vacation"),
                LeaveRequest(leave_type="Sick Leave", start_date="2026-07-02",
                             end_date="2026-07-13", days_requested=10, status="Approved",
                             approver_name="Fatima Maryam Al Qubaisi",
                             notes="Flu recovery with DHA medical certificate"),
            ],
            "expense_claims": [
                # Incurred under Version 2.4, when AED 1,200 needed Finance as well as the
                # line manager. The same amount today needs only the line manager.
                ExpenseClaim(category="Travel & Accommodation", amount_aed=1200.00,
                             claim_date="2025-11-20", status="Approved",
                             approver="Khalifa Saeed Al Nahyan", receipt_reference="REC-2025-1120",
                             description="Two nights, Abu Dhabi client engagement, AED 600 per night",
                             policy_reference="HC-PC-005 §5.3.3"),
                ExpenseClaim(category="Client Meals & Entertainment", amount_aed=450.00,
                             claim_date="2026-05-14", status="Approved",
                             approver="Fatima Maryam Al Qubaisi", receipt_reference="REC-2026-0514",
                             description="Client dinner, 2 attendees including the employee, AED 225 per head",
                             policy_reference="HC-PC-005 §5.5.1"),
                ExpenseClaim(category="Local Travel & Taxi", amount_aed=180.00,
                             claim_date="2026-06-20", status="Approved",
                             approver="Fatima Maryam Al Qubaisi", receipt_reference="REC-2026-0620",
                             description="Taxi fares, Dubai client site visits",
                             policy_reference="HC-PC-005 §5.3.4"),
            ],
        },
        {
            # Grade 8. Approves EMP001 and EMP006, so "who approved my claim, and are
            # they still my manager?" is answerable from the record.
            "employee": Employee(
                user_id="EMP002", name="Fatima Maryam Al Qubaisi",
                name_ar="فاطمة مريم القبيسي", role="VP, People & Culture",
                job_title="VP, People & Culture", department="People & Culture",
                grade="Grade 8", email="fatima.qubaisi@hcservices.ae",
                phone="+971 50 234 5678", location="Abu Dhabi Office, Level 8",
                start_date="2018-01-20", years_of_service=8, probation_status="Passed",
                manager_name="Mohammed bin Rashid Al Maktoum", manager_id="EMP005",
                manager_email="mohammed.maktoum@hcservices.ae",
                manager_role="Executive Director",
            ),
            # 23 of 26 used, so "can I take another week off?" is a reasoned no.
            "balances": [
                annual_leave_row(entitled=26, used=23, carry_over=0),
                *sick_leave_rows(days_used=3),
                annual_leave_row(entitled=26, used=18, carry_over=0, year=2025),
            ],
            "manager_history": [
                ManagerHistory(previous_manager="External Appointment",
                               current_manager="Mohammed bin Rashid Al Maktoum",
                               effective_date="2018-01-20",
                               change_reason="Appointment as VP, People & Culture"),
            ],
            "leave_requests": [
                LeaveRequest(leave_type="Annual Leave", start_date="2026-02-02",
                             end_date="2026-02-13", days_requested=11, status="Approved",
                             approver_name="Mohammed bin Rashid Al Maktoum",
                             notes="Family travel"),
                LeaveRequest(leave_type="Annual Leave", start_date="2026-06-01",
                             end_date="2026-06-18", days_requested=12, status="Approved",
                             approver_name="Mohammed bin Rashid Al Maktoum",
                             notes="Summer leave"),
                LeaveRequest(leave_type="Sick Leave", start_date="2026-03-09",
                             end_date="2026-03-11", days_requested=3, status="Approved",
                             approver_name="Mohammed bin Rashid Al Maktoum",
                             notes="Certified absence, DHA certificate on file"),
            ],
            "expense_claims": [],
        },
        {
            # On probation, mid-year joiner, junior grade. Accrued 14 of 21 (HC-PC-001
            # §1.3.1), cannot take leave in her first three months (HC-PC-003 §3.5.1),
            # sick leave at half pay from day one (HC-PC-002 §2.2.2), and her role class
            # makes her remote-ineligible until confirmation.
            "employee": Employee(
                user_id="EMP003", name="Aisha Hessa Al Mazrouei",
                name_ar="عائشة حصة المزروعي", role="Associate Analyst",
                job_title="Associate Analyst", department="Digital & Technology",
                grade="Grade 3", email="aisha.mazrouei@hcservices.ae",
                phone="+971 50 345 6789", location="Dubai Office, Level 12",
                start_date="2026-05-01", years_of_service=0, probation_status="Active",
                manager_name="Ahmed Abdullah Al Mansoori", manager_id="EMP001",
                manager_email="ahmed.mansoori@hcservices.ae", manager_role="Senior Consultant",
            ),
            "balances": [annual_leave_row(entitled=21, used=0, carry_over=0, accrued=14.0),
                         *sick_leave_rows(days_used=0)],
            "manager_history": [
                ManagerHistory(previous_manager="External Appointment",
                               current_manager="Ahmed Abdullah Al Mansoori",
                               effective_date="2026-05-01",
                               change_reason="Initial assignment on joining Digital & Technology"),
            ],
            "leave_requests": [],
            "expense_claims": [],
        },
        {
            # Grade 7 — ON the business-class line and ON the extended-probation line, so
            # the same two questions that EMP001 answers "no" he answers "yes".
            # Start date moved off 2014-09-01, which flips from 11 to 12 years mid-demo.
            "employee": Employee(
                user_id="EMP004", name="Khalifa Saeed Al Nahyan",
                name_ar="خليفة سعيد آل نهيان", role="Director, Finance & Treasury",
                job_title="Director, Finance & Treasury", department="Finance & Accounting",
                grade="Grade 7", email="khalifa.nahyan@hcservices.ae",
                phone="+971 50 456 7890", location="Abu Dhabi Office, Level 10",
                start_date="2014-06-01", years_of_service=12, probation_status="Passed",
                manager_name="Mohammed bin Rashid Al Maktoum", manager_id="EMP005",
                manager_email="mohammed.maktoum@hcservices.ae", manager_role="Executive Director",
            ),
            # Carry-over sits exactly on the 10-day cap at HC-PC-001 §1.5.1.
            "balances": [annual_leave_row(entitled=30, used=6, carry_over=10),
                         *sick_leave_rows(days_used=0),
                         annual_leave_row(entitled=30, used=25, carry_over=0, year=2025)],
            "manager_history": [
                ManagerHistory(previous_manager="External Appointment",
                               current_manager="Mohammed bin Rashid Al Maktoum",
                               effective_date="2014-06-01",
                               change_reason="Appointment as Director, Finance & Treasury"),
            ],
            "leave_requests": [
                LeaveRequest(leave_type="Annual Leave", start_date="2026-03-16",
                             end_date="2026-03-23", days_requested=6, status="Approved",
                             approver_name="Mohammed bin Rashid Al Maktoum", notes="Spring break"),
            ],
            "expense_claims": [
                # Three London nights at AED 950 — over the AED 900 Europe cap at
                # HC-PC-005 §5.3.3, so "was this within policy?" has a determinate answer.
                ExpenseClaim(category="Travel & Accommodation", amount_aed=2850.00,
                             claim_date="2026-02-15", status="Approved",
                             approver="Mohammed bin Rashid Al Maktoum",
                             receipt_reference="REC-2026-0215",
                             description="London, 3 nights at AED 950 per night, client engagement",
                             policy_reference="HC-PC-005 §5.3.3"),
                ExpenseClaim(category="Per Diem", amount_aed=1050.00,
                             claim_date="2026-02-15", status="Approved",
                             approver="Mohammed bin Rashid Al Maktoum",
                             receipt_reference="REC-2026-0216",
                             description="London, 3 payable days at AED 350; return day not claimed",
                             policy_reference="HC-PC-005 §5.4"),
            ],
        },
        {
            # Top of the reporting chain, and a comparative trap: the most senior person
            # here does NOT have the most leave, because the ladder is service-based.
            "employee": Employee(
                user_id="EMP005", name="Mohammed bin Rashid Al Maktoum",
                name_ar="محمد بن راشد آل مكتوم", role="Executive Director",
                job_title="Executive Director", department="Executive Leadership",
                grade="Grade 9", email="mohammed.maktoum@hcservices.ae",
                phone="+971 50 567 8901", location="Dubai Office, Level 20",
                start_date="2020-02-12", years_of_service=6, probation_status="Passed",
                manager_name="Board of Directors", manager_id=None,
                manager_email="board@hcservices.ae", manager_role="Board of Directors",
            ),
            "balances": [annual_leave_row(entitled=26, used=15, carry_over=0),
                         *sick_leave_rows(days_used=0)],
            "manager_history": [],
            "leave_requests": [
                LeaveRequest(leave_type="Annual Leave", start_date="2026-07-06",
                             end_date="2026-07-24", days_requested=15, status="Approved",
                             approver_name="Board of Directors", notes="Annual summer leave"),
            ],
            "expense_claims": [],
        },
        {
            # Grade 6 — exactly ON the business-class threshold, with the SAME service
            # band as EMP001, which separates the effect of grade from the effect of
            # service. 34 sick days across five spells spanning 1 April 2026, the date
            # the pay tranches changed: the flagship temporal and numerical case.
            # Bradford: 5² × 34 = 850, well past the referral band.
            "employee": Employee(
                user_id="EMP006", name="Layla Al Suwaidi", name_ar="ليلى السويدي",
                role="Manager, Client Delivery", job_title="Manager, Client Delivery",
                department="Client Delivery", grade="Grade 6",
                email="layla.suwaidi@hcservices.ae", phone="+971 50 678 9012",
                location="Dubai Office, Level 15", start_date="2023-02-01",
                years_of_service=3, probation_status="Passed",
                manager_name="Fatima Maryam Al Qubaisi", manager_id="EMP002",
                manager_email="fatima.qubaisi@hcservices.ae", manager_role="VP, People & Culture",
            ),
            "balances": [annual_leave_row(entitled=24, used=8, carry_over=0),
                         *sick_leave_rows(days_used=34),
                         annual_leave_row(entitled=24, used=20, carry_over=0, year=2025)],
            "manager_history": [
                ManagerHistory(previous_manager="External Appointment",
                               current_manager="Fatima Maryam Al Qubaisi",
                               effective_date="2023-02-01",
                               change_reason="Appointment as Manager, Client Delivery"),
            ],
            "leave_requests": [
                LeaveRequest(leave_type="Annual Leave", start_date="2026-05-04",
                             end_date="2026-05-13", days_requested=8, status="Approved",
                             approver_name="Fatima Maryam Al Qubaisi", notes="Family leave"),
                # Two spells before the tranche change, three after.
                LeaveRequest(leave_type="Sick Leave", start_date="2026-02-02",
                             end_date="2026-02-13", days_requested=10, status="Approved",
                             approver_name="Fatima Maryam Al Qubaisi",
                             notes="Certified absence, paid under Version 2.8 tranches"),
                LeaveRequest(leave_type="Sick Leave", start_date="2026-03-02",
                             end_date="2026-03-06", days_requested=5, status="Approved",
                             approver_name="Fatima Maryam Al Qubaisi", notes="Certified absence"),
                LeaveRequest(leave_type="Sick Leave", start_date="2026-04-13",
                             end_date="2026-04-24", days_requested=10, status="Approved",
                             approver_name="Fatima Maryam Al Qubaisi",
                             notes="Certified absence, paid under Version 3.0 tranches"),
                LeaveRequest(leave_type="Sick Leave", start_date="2026-06-08",
                             end_date="2026-06-12", days_requested=5, status="Approved",
                             approver_name="Fatima Maryam Al Qubaisi", notes="Certified absence"),
                LeaveRequest(leave_type="Sick Leave", start_date="2026-07-20",
                             end_date="2026-07-23", days_requested=4, status="Approved",
                             approver_name="Fatima Maryam Al Qubaisi", notes="Certified absence"),
            ],
            "expense_claims": [
                # AED 7,600 sits just over the 7,500 boundary, so it needs the CFO today.
                ExpenseClaim(category="Travel & Accommodation", amount_aed=7600.00,
                             claim_date="2026-06-30", status="Approved",
                             approver="Fatima Maryam Al Qubaisi", receipt_reference="REC-2026-0630",
                             description="Riyadh, 7 nights at AED 600 plus flights, client programme",
                             policy_reference="HC-PC-005 §5.7.2"),
            ],
        },
        {
            # Part-time in a Class C role. A remote-work request is refused for a reason
            # the policy gives — role classification, not performance — and his leave is
            # a non-integer, which the pro-rata rule at HC-PC-001 §1.2.3 produces.
            "employee": Employee(
                user_id="EMP007", name="Omar Haddad", name_ar="عمر حداد",
                role="Facilities Supervisor", job_title="Facilities Supervisor",
                department="Workplace & Facilities", grade="Grade 2",
                email="omar.haddad@hcservices.ae", phone="+971 50 789 0123",
                location="Dubai Office, Ground Floor", start_date="2021-09-01",
                years_of_service=4, probation_status="Extended",
                manager_name="Khalifa Saeed Al Nahyan", manager_id="EMP004",
                manager_email="khalifa.nahyan@hcservices.ae",
                manager_role="Director, Finance & Treasury",
                employment_fraction=0.6,
            ),
            # 24-day band at 0.6 FTE = 14.4 days.
            "balances": [annual_leave_row(entitled=14, used=4, carry_over=0, accrued=14.4),
                         *sick_leave_rows(days_used=2)],
            "manager_history": [
                ManagerHistory(previous_manager="External Appointment",
                               current_manager="Khalifa Saeed Al Nahyan",
                               effective_date="2021-09-01",
                               change_reason="Appointment to Workplace & Facilities"),
            ],
            "leave_requests": [
                LeaveRequest(leave_type="Annual Leave", start_date="2026-04-06",
                             end_date="2026-04-09", days_requested=4, status="Approved",
                             approver_name="Khalifa Saeed Al Nahyan", notes="Personal leave"),
                LeaveRequest(leave_type="Sick Leave", start_date="2026-05-18",
                             end_date="2026-05-19", days_requested=2, status="Approved",
                             approver_name="Khalifa Saeed Al Nahyan",
                             notes="Self-certified, under three consecutive days"),
            ],
            "expense_claims": [],
        },
        {
            # Two years' service, so the ladder says 21 — but her contract grants 24,
            # which HC-PC-001 §1.1 permits and HC-PC-007 §7.1 ranks above the policy.
            # A correct answer prefers the record AND explains why it differs.
            "employee": Employee(
                user_id="EMP008", name="Sara Nasser", name_ar="سارة ناصر",
                role="Consultant, Strategy", job_title="Consultant, Strategy",
                department="Strategy & Transformation", grade="Grade 4",
                email="sara.nasser@hcservices.ae", phone="+971 50 890 1234",
                location="Dubai Office, Level 14", start_date="2024-06-01",
                years_of_service=2, probation_status="Passed",
                manager_name="Ahmed Abdullah Al Mansoori", manager_id="EMP001",
                manager_email="ahmed.mansoori@hcservices.ae", manager_role="Senior Consultant",
            ),
            "balances": [annual_leave_row(entitled=24, used=5, carry_over=0),
                         *sick_leave_rows(days_used=0)],
            "manager_history": [
                ManagerHistory(previous_manager="External Appointment",
                               current_manager="Ahmed Abdullah Al Mansoori",
                               effective_date="2024-06-01",
                               change_reason="Appointment on joining Strategy & Transformation"),
            ],
            "leave_requests": [
                LeaveRequest(leave_type="Annual Leave", start_date="2026-03-02",
                             end_date="2026-03-06", days_requested=5, status="Approved",
                             approver_name="Ahmed Abdullah Al Mansoori", notes="Short break"),
                # Still pending, so "what is the status of my request?" has an answer.
                LeaveRequest(leave_type="Annual Leave", start_date="2026-10-05",
                             end_date="2026-10-16", days_requested=10, status="Pending",
                             approver_name="Ahmed Abdullah Al Mansoori",
                             notes="Awaiting line manager decision"),
            ],
            "expense_claims": [
                # Rejected against a named clause, so the reason is in the record.
                ExpenseClaim(category="Health & Wellbeing", amount_aed=320.00,
                             claim_date="2026-07-11", status="Rejected",
                             approver="Ahmed Abdullah Al Mansoori", receipt_reference="REC-2026-0711",
                             description="Annual gym membership contribution",
                             policy_reference="HC-PC-005 §5.6"),
            ],
        },
    ]
