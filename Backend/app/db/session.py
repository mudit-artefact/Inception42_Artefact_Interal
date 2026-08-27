"""
app/db/session.py — SQLite engine, session factory, and DB seeder for Omni HR Database
"""
import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.db.models import Base, Employee, LeaveBalance, ManagerHistory, LeaveRequest, ExpenseClaim

logger = logging.getLogger(__name__)

# Locate omni_hr.db inside Backend/data/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "omni_hr.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # Required for SQLite multi-threading in FastAPI
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI Dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_and_seed_db(force_reseed: bool = False):
    """
    Initialize SQLite database tables and seed comprehensive HR data.
    """
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()

    try:
        existing_count = session.query(Employee).count()
        if existing_count > 0 and not force_reseed:
            logger.info(f"Omni HR SQL Database already seeded ({existing_count} employees present).")
            return

        if force_reseed:
            logger.info("Force reseeding Omni HR SQL Database...")
            session.query(ExpenseClaim).delete()
            session.query(LeaveRequest).delete()
            session.query(ManagerHistory).delete()
            session.query(LeaveBalance).delete()
            session.query(Employee).delete()
            session.commit()

        logger.info(f"Seeding Omni HR SQL Database at {DB_PATH}...")

        employees_data = [
            {
                "employee": Employee(
                    user_id="EMP001",
                    name="Ahmed Abdullah Al Mansoori",
                    name_ar="أحمد عبد الله المنصوري",
                    role="Senior Consultant",
                    job_title="Senior Consultant",
                    department="Strategy & Transformation",
                    grade="Grade 9",
                    email="ahmed.mansoori@hcservices.ae",
                    phone="+971 50 123 4567",
                    location="Dubai Office, Level 14",
                    start_date="2022-03-15",
                    years_of_service=4,
                    probation_status="Passed",
                    manager_name="Fatima Maryam Al Qubaisi",
                    manager_email="fatima.qubaisi@hcservices.ae",
                    manager_role="VP, People & Culture",
                ),
                "balances": [
                    LeaveBalance(leave_type="Annual leave", entitled_days=30, used_days=12, remaining_days=18, carry_over_days=3, year=2026),
                    LeaveBalance(leave_type="Sick leave", entitled_days=15, used_days=10, remaining_days=5, carry_over_days=0, year=2026),
                    LeaveBalance(leave_type="Carry-over", entitled_days=3, used_days=0, remaining_days=3, carry_over_days=3, year=2026),
                ],
                "manager_history": [
                    ManagerHistory(
                        previous_manager="Khalifa Saeed Al Nahyan",
                        current_manager="Fatima Maryam Al Qubaisi",
                        effective_date="2025-10-01",
                        change_reason="Promotion to Senior Consultant & Strategy alignment",
                    ),
                    ManagerHistory(
                        previous_manager="Initial Onboarding Manager",
                        current_manager="Khalifa Saeed Al Nahyan",
                        effective_date="2022-03-15",
                        change_reason="Initial assignment upon joining Strategy team",
                    ),
                ],
                "leave_requests": [
                    LeaveRequest(
                        leave_type="Annual Leave",
                        start_date="2026-01-12",
                        end_date="2026-01-16",
                        days_requested=5,
                        status="Approved",
                        approver_name="Fatima Maryam Al Qubaisi",
                        notes="Winter holiday with family",
                    ),
                    LeaveRequest(
                        leave_type="Annual Leave",
                        start_date="2026-04-10",
                        end_date="2026-04-18",
                        days_requested=7,
                        status="Approved",
                        approver_name="Fatima Maryam Al Qubaisi",
                        notes="Spring break vacation",
                    ),
                    LeaveRequest(
                        leave_type="Sick Leave",
                        start_date="2026-07-02",
                        end_date="2026-07-04",
                        days_requested=2,
                        status="Approved",
                        approver_name="Fatima Maryam Al Qubaisi",
                        notes="Flu recovery with DHA medical certificate",
                    ),
                ],
                "expense_claims": [
                    ExpenseClaim(
                        category="Client Meals & Entertainment",
                        amount_aed=450.00,
                        claim_date="2026-05-14",
                        status="Approved",
                        approver="Fatima Maryam Al Qubaisi",
                        receipt_reference="REC-2026-0514",
                    ),
                    ExpenseClaim(
                        category="Local Travel & Taxi",
                        amount_aed=180.00,
                        claim_date="2026-06-20",
                        status="Approved",
                        approver="Fatima Maryam Al Qubaisi",
                        receipt_reference="REC-2026-0620",
                    ),
                ],
            },
            {
                "employee": Employee(
                    user_id="EMP002",
                    name="Fatima Maryam Al Qubaisi",
                    name_ar="فاطمة مريم القبيسي",
                    role="VP, People & Culture",
                    job_title="VP, People & Culture",
                    department="People & Culture",
                    grade="Grade 11",
                    email="fatima.qubaisi@hcservices.ae",
                    phone="+971 50 234 5678",
                    location="Abu Dhabi Office, Level 8",
                    start_date="2018-01-20",
                    years_of_service=8,
                    probation_status="Passed",
                    manager_name="Mohammed bin Rashid Al Maktoum",
                    manager_email="mohammed.maktoum@hcservices.ae",
                    manager_role="Executive Director",
                ),
                "balances": [
                    LeaveBalance(leave_type="Annual leave", entitled_days=30, used_days=23, remaining_days=7, carry_over_days=0, year=2026),
                    LeaveBalance(leave_type="Sick leave", entitled_days=15, used_days=3, remaining_days=12, carry_over_days=0, year=2026),
                    LeaveBalance(leave_type="Carry-over", entitled_days=0, used_days=0, remaining_days=0, carry_over_days=0, year=2026),
                ],
                "manager_history": [
                    ManagerHistory(
                        previous_manager="Executive Committee",
                        current_manager="Mohammed bin Rashid Al Maktoum",
                        effective_date="2023-01-01",
                        change_reason="HR Executive Leadership realignment",
                    )
                ],
                "leave_requests": [
                    LeaveRequest(
                        leave_type="Annual Leave",
                        start_date="2026-03-01",
                        end_date="2026-03-15",
                        days_requested=11,
                        status="Approved",
                        approver_name="Mohammed bin Rashid Al Maktoum",
                        notes="Annual personal leave",
                    )
                ],
                "expense_claims": [],
            },
            {
                "employee": Employee(
                    user_id="EMP003",
                    name="Aisha Hessa Al Mazrouei",
                    name_ar="عائشة حصة المزروعي",
                    role="Associate Analyst",
                    job_title="Associate Analyst",
                    department="Digital & Technology",
                    grade="Grade 6",
                    email="aisha.mazrouei@hcservices.ae",
                    phone="+971 50 345 6789",
                    location="Dubai Office, Level 14",
                    start_date="2026-05-01",
                    years_of_service=0,
                    probation_status="Active",
                    manager_name="Ahmed Abdullah Al Mansoori",
                    manager_email="ahmed.mansoori@hcservices.ae",
                    manager_role="Senior Consultant",
                ),
                "balances": [
                    LeaveBalance(leave_type="Annual leave", entitled_days=30, used_days=9, remaining_days=21, carry_over_days=0, year=2026),
                    LeaveBalance(leave_type="Sick leave", entitled_days=15, used_days=0, remaining_days=15, carry_over_days=0, year=2026),
                    LeaveBalance(leave_type="Carry-over", entitled_days=0, used_days=0, remaining_days=0, carry_over_days=0, year=2026),
                ],
                "manager_history": [],
                "leave_requests": [],
                "expense_claims": [],
            },
            {
                "employee": Employee(
                    user_id="EMP004",
                    name="Khalifa Saeed Al Nahyan",
                    name_ar="خليفة سعيد آل نهيان",
                    role="Director, Finance & Treasury",
                    job_title="Director, Finance & Treasury",
                    department="Finance & Accounting",
                    grade="Grade 12",
                    email="khalifa.nahyan@hcservices.ae",
                    phone="+971 50 456 7890",
                    location="Abu Dhabi Office, Level 12",
                    start_date="2014-09-01",
                    years_of_service=12,
                    probation_status="Passed",
                    manager_name="Mohammed bin Rashid Al Maktoum",
                    manager_email="mohammed.maktoum@hcservices.ae",
                    manager_role="Executive Director",
                ),
                "balances": [
                    LeaveBalance(leave_type="Annual leave", entitled_days=30, used_days=6, remaining_days=24, carry_over_days=5, year=2026),
                    LeaveBalance(leave_type="Sick leave", entitled_days=15, used_days=0, remaining_days=15, carry_over_days=0, year=2026),
                    LeaveBalance(leave_type="Carry-over", entitled_days=5, used_days=0, remaining_days=5, carry_over_days=5, year=2026),
                ],
                "manager_history": [],
                "leave_requests": [],
                "expense_claims": [],
            },
            {
                "employee": Employee(
                    user_id="EMP005",
                    name="Mohammed bin Rashid Al Maktoum",
                    name_ar="محمد بن راشد آل مكتوم",
                    role="Executive Director",
                    job_title="Executive Director",
                    department="Executive Leadership",
                    grade="Grade 14",
                    email="mohammed.maktoum@hcservices.ae",
                    phone="+971 50 567 8901",
                    location="Dubai Office, Executive Suite",
                    start_date="2020-02-12",
                    years_of_service=6,
                    probation_status="Passed",
                    manager_name="Board of Directors",
                    manager_email="board@hcservices.ae",
                    manager_role="Board of Directors",
                ),
                "balances": [
                    LeaveBalance(leave_type="Annual leave", entitled_days=30, used_days=15, remaining_days=15, carry_over_days=0, year=2026),
                    LeaveBalance(leave_type="Sick leave", entitled_days=15, used_days=0, remaining_days=15, carry_over_days=0, year=2026),
                    LeaveBalance(leave_type="Carry-over", entitled_days=0, used_days=0, remaining_days=0, carry_over_days=0, year=2026),
                ],
                "manager_history": [],
                "leave_requests": [],
                "expense_claims": [],
            },
        ]

        for item in employees_data:
            emp = item["employee"]
            session.add(emp)
            session.flush()

            for bal in item["balances"]:
                bal.employee_id = emp.user_id
                session.add(bal)

            for hist in item["manager_history"]:
                hist.employee_id = emp.user_id
                session.add(hist)

            for req in item["leave_requests"]:
                req.employee_id = emp.user_id
                session.add(req)

            for exp in item["expense_claims"]:
                exp.employee_id = emp.user_id
                session.add(exp)

        session.commit()
        logger.info(f"✅ Successfully seeded {len(employees_data)} employees into Omni HR SQL Database.")

    except Exception as e:
        session.rollback()
        logger.error(f"Failed to seed Omni HR database: {e}", exc_info=True)
        raise
    finally:
        session.close()
