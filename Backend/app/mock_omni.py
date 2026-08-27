"""
app/mock_omni.py — Omni HR System API backed by SQL Database (omni_hr.db)
Serves dynamic employee profiles, leave balances, manager histories, and update endpoints.
"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.db.session import SessionLocal, init_and_seed_db
from app.db.models import Employee
from app.db.sql_tool import (
    get_employee_full_sql_context,
    update_employee_manager_sql,
    update_leave_balance_sql,
    execute_employee_sql,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/omni", tags=["Omni HR SQL Database"])


# ── Data Models ──────────────────────────────────────────────────

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


class SQLExecuteRequest(BaseModel):
    query: str


# ── Relevant Policy Links by Topic ───────────────────────────────

POLICIES = {
    "annual": PolicyLink(id="pol-annual", title="Annual Leave Policy", section="HC-PC-001 §3", url="#"),
    "sick": PolicyLink(id="pol-sick", title="Sick Leave & Medical Certificates", section="HC-PC-002 §2.4", url="#"),
    "probation": PolicyLink(id="pol-probation", title="Probation & Onboarding Policy", section="HC-PC-003 §4", url="#"),
    "remote": PolicyLink(id="pol-remote", title="Flexible & Remote Work Policy", section="HC-PC-004 §1", url="#"),
    "expenses": PolicyLink(id="pol-expenses", title="Expense Claims & Reimbursement", section="HC-PC-005 §5", url="#"),
}


def _context_to_profile(ctx: dict) -> EmployeeProfile:
    """Map SQL context dictionary to standard EmployeeProfile model for API/Frontend."""
    probation = ctx.get("probation_status", "Passed")
    if probation == "Active":
        policy_links = [POLICIES["probation"], POLICIES["annual"], POLICIES["sick"], POLICIES["remote"]]
    else:
        policy_links = [POLICIES["annual"], POLICIES["sick"], POLICIES["remote"], POLICIES["expenses"]]

    balances = [
        LeaveBalanceItem(
            type=b["type"],
            used=b["used"],
            entitled=b["entitled"],
            unit=b.get("unit", "days"),
        )
        for b in ctx.get("balances", [])
    ]

    return EmployeeProfile(
        user_id=ctx["user_id"],
        id=ctx["user_id"],
        name=ctx["name"],
        name_ar=ctx["name_ar"],
        role=ctx["role"],
        jobTitle=ctx.get("job_title", ctx["role"]),
        department=ctx["department"],
        grade=ctx.get("grade", "Grade 9"),
        annual_leave_balance=ctx.get("annual_leave_balance", 20),
        sick_leave_balance=ctx.get("sick_leave_balance", 10),
        carry_over_days=ctx.get("carry_over_days", 0),
        probation_status=probation,
        years_of_service=ctx.get("years_of_service", 0),
        manager=ctx.get("manager_name", "Line Manager"),
        email=ctx.get("email", ""),
        start_date=ctx.get("start_date", ""),
        balances=balances,
        policyLinks=policy_links,
    )


# ── Endpoints ────────────────────────────────────────────────────

@router.get(
    "/employee/{user_id}",
    response_model=EmployeeProfile,
    summary="Get employee profile directly from SQL Database",
)
async def get_employee(user_id: str) -> EmployeeProfile:
    """Return live employee profile from SQL database."""
    ctx = get_employee_full_sql_context(user_id.upper())
    if not ctx:
        raise HTTPException(status_code=404, detail=f"Employee {user_id} not found in SQL database.")
    return _context_to_profile(ctx)


@router.get(
    "/employees",
    response_model=list[EmployeeProfile],
    summary="List all employees from SQL Database",
)
async def list_employees() -> list[EmployeeProfile]:
    """Return list of all employees queried directly from the SQLite database."""
    session = SessionLocal()
    try:
        emps = session.query(Employee).order_by(Employee.user_id).all()
        profiles = []
        for emp in emps:
            ctx = get_employee_full_sql_context(emp.user_id)
            profiles.append(_context_to_profile(ctx))
        return profiles
    finally:
        session.close()


@router.patch(
    "/employees/{user_id}/manager",
    summary="Update employee line manager in SQL Database and record transition in manager_history",
)
async def update_manager(user_id: str, req: UpdateManagerRequest):
    """
    Live update employee's line manager in SQLite database.
    Subsequent LLM questions will immediately reflect this new manager.
    """
    try:
        res = update_employee_manager_sql(
            employee_id=user_id.upper(),
            new_manager_name=req.manager_name,
            new_manager_email=req.manager_email,
            new_manager_role=req.manager_role,
            change_reason=req.reason or "Line manager update via Omni HR API",
        )
        return {"status": "success", "data": res}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch(
    "/employees/{user_id}/leave-balance",
    summary="Update employee leave balance in SQL Database",
)
async def update_leave_balance(user_id: str, req: UpdateLeaveBalanceRequest):
    """
    Live update employee's remaining leave balance in SQLite database.
    """
    try:
        res = update_leave_balance_sql(
            employee_id=user_id.upper(),
            leave_type=req.leave_type,
            remaining_days=req.remaining_days,
            used_days=req.used_days,
            carry_over_days=req.carry_over_days,
        )
        return {"status": "success", "data": res}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/sql/query",
    summary="Execute read-only SQL query against Omni HR database",
)
async def run_sql_query(req: SQLExecuteRequest):
    """
    Execute read-only SELECT queries for inspection or LLM tool use.
    """
    try:
        rows = execute_employee_sql(req.query)
        return {"rows": rows, "count": len(rows)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Helper used by RAG engine (direct SQL context) ────────────────

def get_employee_sync(user_id: str) -> EmployeeProfile:
    """Direct in-process lookup from SQL database — avoids HTTP overhead."""
    ctx = get_employee_full_sql_context(user_id.upper())
    return _context_to_profile(ctx)
