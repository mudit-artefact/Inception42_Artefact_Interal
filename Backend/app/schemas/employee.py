"""The employee profile the web interface shows in its sidebar."""

from typing import Optional

from pydantic import BaseModel, Field


class LeaveBalanceItem(BaseModel):
    type: str
    used: int
    entitled: int
    unit: str = "days"


class PolicyLink(BaseModel):
    id: str
    title: str
    section: Optional[str] = None
    url: Optional[str] = "#"


class EmployeeProfile(BaseModel):
    """
    Note: `jobTitle` and `policyLinks` are camelCase because the web interface reads
    those exact key names. Every other field is snake_case.
    """

    user_id: str
    id: str = ""
    name: str
    name_ar: str
    role: str
    jobTitle: str = ""
    department: str
    grade: str = "Grade 9"
    annual_leave_balance: int
    sick_leave_balance: int
    carry_over_days: int
    probation_status: str  # "Active" | "Passed" | "Extended"
    years_of_service: int
    manager: str
    email: str
    start_date: str
    balances: list[LeaveBalanceItem] = Field(default_factory=list)
    policyLinks: list[PolicyLink] = Field(default_factory=list)


class UpdateManagerRequest(BaseModel):
    manager_name: str
    manager_email: Optional[str] = None
    manager_role: Optional[str] = "Line Manager"
    reason: Optional[str] = "Department restructuring & reassignment"


class UpdateLeaveBalanceRequest(BaseModel):
    leave_type: str = "Annual leave"
    remaining_days: int
    used_days: Optional[int] = None
    carry_over_days: Optional[int] = None
