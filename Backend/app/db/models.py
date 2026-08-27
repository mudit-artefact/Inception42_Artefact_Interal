"""
app/db/models.py — SQLAlchemy ORM models for Omni HR Database
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
    grade = Column(String(32), nullable=False, default="Grade 9")
    email = Column(String(128), nullable=False)
    phone = Column(String(64), nullable=False, default="+971 50 123 4567")
    location = Column(String(128), nullable=False, default="Dubai Office, Level 14")
    start_date = Column(String(32), nullable=False)
    years_of_service = Column(Integer, nullable=False, default=0)
    probation_status = Column(String(32), nullable=False, default="Passed")  # Active, Passed, Extended
    manager_name = Column(String(128), nullable=False)
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
    entitled_days = Column(Integer, nullable=False, default=30)
    used_days = Column(Integer, nullable=False, default=0)
    remaining_days = Column(Integer, nullable=False, default=30)
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
    created_at = Column(DateTime, default=datetime.utcnow)

    employee = relationship("Employee", back_populates="expense_claims")
