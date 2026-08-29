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
