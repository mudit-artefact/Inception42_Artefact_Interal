"""The employee profile the web interface shows in its sidebar."""

from typing import Optional

from pydantic import BaseModel, Field


class LeaveBalanceItem(BaseModel):
    """
    One leave balance, as the sidebar shows it.

    `remaining` is sent rather than left to the caller to work out. It used to carry only
    `used` and `entitled`, so the web interface derived the figure itself as
    entitled - used — which ignores carried-over days and quietly disagreed with the
    assistant's answer on screen. The database holds the figure and asserts the identity
    behind it, so sending it is both shorter and the only version that can be right.
    """

    type: str
    used: int
    entitled: int
    remaining: int
    carry_over: int = 0
    year: int
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
    # The city they work in — "Abu Dhabi", not "Abu Dhabi Office, Level 7". Both are on the
    # record; this is the one a person says when asked where they work, and the other is a
    # desk. Added for the joining screens, which name the place alongside the job title and
    # the start date, all three read off the record rather than guessed from the entity.
    work_location: str = ""
    balances: list[LeaveBalanceItem] = Field(default_factory=list)
    policyLinks: list[PolicyLink] = Field(default_factory=list)

    # Who this person is, for a screen that shows different things to different people.
    #
    # Both facts existed in the database and neither reached the browser, so the web
    # interface had no way to tell a new joiner from a current employee, or to know that
    # somebody has people reporting to them. Both were being inferred from the wording of
    # a question instead, which is a poor way to decide what to put on a page.
    employment_status: str = "Active"  # "Active" | "On Leave" | "Onboarding" | "Terminated"
    # How many people report to this person. There is no "is a manager" flag anywhere in
    # the system; managing is having reports, and this is that, counted.
    direct_reports: int = 0


class LeaveRequestItem(BaseModel):
    """One leave request as a list shows it."""

    id: int
    leave_type: str
    start_date: str
    end_date: str
    days_requested: int
    status: str  # "Approved" | "Pending" | "Rejected" | "Cancelled"
    approver_name: str = ""
    notes: str = ""
    # When the row was written. Requests seeded with the database all carry the moment of
    # seeding rather than a real submission date; the figure is passed through as it
    # stands rather than dressed up.
    created_at: str = ""


class PendingApprovalItem(BaseModel):
    """One request waiting on this manager, with enough about the asker to decide."""

    request_id: int
    employee_id: str
    employee_name: str
    employee_role: str = ""
    leave_type: str
    start_date: str
    end_date: str
    days_requested: int
    notes: str = ""
    created_at: str = ""
    status: str = "Pending"


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
