"""
The tables the HR database is made of.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Employee(Base):
    __tablename__ = "employees"

    user_id = Column(String(32), primary_key=True, index=True)  # e.g. EMP001
    name = Column(String(128), nullable=False)
    name_ar = Column(String(128), nullable=False)
    role = Column(String(128), nullable=False)
    job_title = Column(String(128), nullable=False, default="")
    department = Column(String(128), nullable=False)
    # Grade 3 is the Professional band. The default used to be Grade 9, which under the
    # band table at HC-PC-007 §7.6 is Executive — so any employee created without an
    # explicit grade silently received business-class travel and unlimited expense
    # authority.
    grade = Column(String(32), nullable=False, default="Grade 3")
    # 1.0 is full time. Annual leave is pro-rated against this (HC-PC-001 §1.2.3).
    employment_fraction = Column(Float, nullable=False, default=1.0)
    payroll_id = Column(String(32), nullable=True, default="")
    legal_entity = Column(String(128), nullable=False, default="Demo Entity UAE")
    work_location = Column(String(128), nullable=False, default="Dubai Office")
    benefit_plan_code = Column(String(64), nullable=False, default="EDU_STANDARD")
    preferred_language = Column(String(32), nullable=False, default="Arabic")
    employment_status = Column(String(32), nullable=False, default="Active")
    exit_date = Column(String(32), nullable=True)
    email = Column(String(128), nullable=False)
    phone = Column(String(64), nullable=False, default="+971 50 123 4567")
    location = Column(String(128), nullable=False, default="Dubai Office, Level 14")
    start_date = Column(String(32), nullable=False)
    years_of_service = Column(Integer, nullable=False, default=0)
    probation_status = Column(String(32), nullable=False, default="Passed")  # Active, Passed, Extended
    manager_name = Column(String(128), nullable=False)
    # The manager as a record rather than a name, so a reporting line can be walked.
    manager_id = Column(String(32), ForeignKey("employees.user_id"), nullable=True, index=True)
    manager_email = Column(String(128), nullable=False, default="")
    manager_role = Column(String(128), nullable=False, default="Line Manager")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    leave_balances = relationship("LeaveBalance", back_populates="employee", cascade="all, delete-orphan")
    manager_history = relationship("ManagerHistory", back_populates="employee", cascade="all, delete-orphan")
    leave_requests = relationship("LeaveRequest", back_populates="employee", cascade="all, delete-orphan")
    expense_claims = relationship("ExpenseClaim", back_populates="employee", cascade="all, delete-orphan")
    dependents = relationship("Dependent", back_populates="employee", cascade="all, delete-orphan")
    school_cases = relationship("SchoolVerificationCase", back_populates="employee", cascade="all, delete-orphan")


class LeaveBalance(Base):
    __tablename__ = "leave_balances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String(32), ForeignKey("employees.user_id"), nullable=False, index=True)
    leave_type = Column(String(64), nullable=False)  # Annual leave, Sick leave, Carry-over
    # 21 days is the standard entitlement at HC-PC-001 §1.2.1, before the service ladder
    # adds to it. The default used to be 30, the top of the ladder, so every employee
    # created without explicit balances was seeded with a ten-year veteran's allowance.
    entitled_days = Column(Integer, nullable=False, default=21)
    used_days = Column(Integer, nullable=False, default=0)
    remaining_days = Column(Integer, nullable=False, default=21)
    # Accrued so far this year, which is less than entitled for anyone mid-year or
    # part-way through their first year (HC-PC-001 §1.3.1).
    accrued_days = Column(Float, nullable=False, default=0.0)
    # Sick leave is one entitlement paid at three rates (HC-PC-002 §2.2.1), so it is held
    # as one row per tranche. NULL where pay rate does not apply, as for annual leave.
    pay_rate_pct = Column(Integer, nullable=True)
    carry_over_days = Column(Integer, nullable=False, default=0)
    year = Column(Integer, nullable=False, default=2026)
    unit = Column(String(16), nullable=False, default="days")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    employee = relationship("Employee", back_populates="leave_balances")


class ManagerHistory(Base):
    __tablename__ = "manager_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String(32), ForeignKey("employees.user_id"), nullable=False, index=True)
    previous_manager = Column(String(128), nullable=False)
    current_manager = Column(String(128), nullable=False)
    effective_date = Column(String(32), nullable=False)
    change_reason = Column(Text, nullable=False, default="Department realignment / Manager transition")
    created_at = Column(DateTime, default=datetime.utcnow)

    employee = relationship("Employee", back_populates="manager_history")


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String(32), ForeignKey("employees.user_id"), nullable=False, index=True)
    leave_type = Column(String(64), nullable=False)  # Annual Leave, Sick Leave, Unpaid Leave
    start_date = Column(String(32), nullable=False)
    end_date = Column(String(32), nullable=False)
    days_requested = Column(Integer, nullable=False)
    status = Column(String(32), nullable=False, default="Approved")  # Approved, Pending, Rejected
    approver_name = Column(String(128), nullable=False)
    notes = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    employee = relationship("Employee", back_populates="leave_requests")


class ExpenseClaim(Base):
    __tablename__ = "expense_claims"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String(32), ForeignKey("employees.user_id"), nullable=False, index=True)
    category = Column(String(64), nullable=False)  # Travel, Client Meals, Software
    amount_aed = Column(Float, nullable=False)
    claim_date = Column(String(32), nullable=False)
    status = Column(String(32), nullable=False, default="Approved")
    approver = Column(String(128), nullable=False)
    receipt_reference = Column(String(64), nullable=False, default="")
    # What was actually bought — the city, the nights, the head count — without which
    # the hotel caps, per diem and per-head limits cannot be checked against a claim.
    description = Column(Text, nullable=False, default="")
    # The clause the claim was assessed under, so "why was this rejected?" has an answer
    # in the record rather than an inference.
    policy_reference = Column(String(32), nullable=False, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    employee = relationship("Employee", back_populates="expense_claims")


class Dependent(Base):
    __tablename__ = "dependents"

    dependent_id = Column(String(32), primary_key=True, index=True)  # e.g. D0001
    employee_id = Column(String(32), ForeignKey("employees.user_id"), nullable=False, index=True)
    first_name = Column(String(64), nullable=False)
    last_name = Column(String(64), nullable=False)
    relationship_type = Column(String(32), nullable=False, default="Child")  # Child, Spouse
    date_of_birth = Column(String(32), nullable=False)
    dependent_status = Column(String(32), nullable=False, default="Active")
    school_enrolment_status = Column(String(32), nullable=False, default="Enrolled")
    preferred_language = Column(String(32), nullable=False, default="Arabic")
    created_at = Column(DateTime, default=datetime.utcnow)

    employee = relationship("Employee", back_populates="dependents")
    school_cases = relationship("SchoolVerificationCase", back_populates="dependent", cascade="all, delete-orphan")


class BenefitPlanRule(Base):
    __tablename__ = "benefit_plan_rules"

    plan_code = Column(String(64), primary_key=True, index=True)  # EDU_STANDARD, EDU_ENHANCED, NONE
    plan_name = Column(String(128), nullable=False)
    annual_limit_aed = Column(Integer, nullable=False, default=0)
    eligible_employee_statuses = Column(String(128), nullable=False, default="Active | On Leave")
    eligible_relationship = Column(String(64), nullable=False, default="Child")
    dependent_status_required = Column(String(64), nullable=False, default="Active")
    school_enrolment_required = Column(String(64), nullable=False, default="Enrolled")
    required_document_type = Column(String(128), nullable=False, default="Proof of schooling")
    manual_review_conditions = Column(Text, nullable=False, default="Low extraction confidence | record mismatch | missing mandatory field")
    required_documents = Column(Text, nullable=True)
    claimable_charges = Column(Text, nullable=True)
    effective_start = Column(String(32), nullable=False, default="2026-08-01")
    effective_end = Column(String(32), nullable=False, default="2027-07-31")
    active_flag = Column(String(16), nullable=False, default="Yes")


class AcademicCycle(Base):
    __tablename__ = "academic_cycles"

    cycle_id = Column(String(32), primary_key=True, index=True)  # AC2026-27
    academic_year = Column(String(32), nullable=False)
    cycle_status = Column(String(32), nullable=False, default="Open")
    submission_open_date = Column(String(32), nullable=False)
    submission_deadline = Column(String(32), nullable=False)
    review_deadline = Column(String(32), nullable=False)
    payroll_cutoff = Column(String(32), nullable=False)
    accepted_issue_start = Column(String(32), nullable=False)
    accepted_issue_end = Column(String(32), nullable=False)

    school_cases = relationship("SchoolVerificationCase", back_populates="academic_cycle", cascade="all, delete-orphan")


class SchoolVerificationCase(Base):
    __tablename__ = "school_verification_cases"

    case_id = Column(String(32), primary_key=True, index=True)  # CASE0001
    employee_id = Column(String(32), ForeignKey("employees.user_id"), nullable=False, index=True)
    dependent_id = Column(String(32), ForeignKey("dependents.dependent_id"), nullable=False, index=True)
    cycle_id = Column(String(32), ForeignKey("academic_cycles.cycle_id"), nullable=False, index=True)
    case_status = Column(String(64), nullable=False, default="Submitted")
    submission_deadline = Column(String(32), nullable=False)
    reminder_count = Column(Integer, nullable=False, default=0)
    document_reference = Column(String(256), nullable=True)
    extraction_status = Column(String(64), nullable=False, default="Pending")
    matching_status = Column(String(64), nullable=False, default="Not Started")
    rules_check_status = Column(String(64), nullable=False, default="Not Started")
    human_review_status = Column(String(64), nullable=False, default="Not Required")
    final_outcome = Column(String(64), nullable=False, default="Not Evaluated")
    approved_amount_aed = Column(Integer, nullable=True)
    payment_status = Column(String(64), nullable=False, default="Not Ready")
    assigned_reviewer = Column(String(128), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    employee = relationship("Employee", back_populates="school_cases")
    dependent = relationship("Dependent", back_populates="school_cases")
    academic_cycle = relationship("AcademicCycle", back_populates="school_cases")

