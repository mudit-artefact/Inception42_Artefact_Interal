"""
app/db/sql_tool.py — SQL Database Query & Mutation Tools for LLM & API
"""
import logging
from datetime import datetime
from typing import Optional, Any
from sqlalchemy import text
from app.db.session import SessionLocal
from app.db.models import Employee, LeaveBalance, ManagerHistory, LeaveRequest, ExpenseClaim

logger = logging.getLogger(__name__)


def get_employee_full_sql_context(employee_id: str) -> dict[str, Any]:
    """
    Retrieve comprehensive, live relational state for an employee directly from the SQL database.
    Used to supply precise ground-truth employee facts to the LLM prompt.
    """
    session = SessionLocal()
    try:
        emp = session.query(Employee).filter(Employee.user_id == employee_id).first()
        if not emp:
            # Fallback default if not found
            return {
                "user_id": employee_id,
                "name": "Employee",
                "name_ar": "موظف",
                "role": "Staff",
                "department": "General",
                "grade": "Grade 9",
                "manager_name": "Line Manager",
                "manager_email": "",
                "manager_role": "Line Manager",
                "annual_leave_balance": 20,
                "sick_leave_balance": 10,
                "carry_over_days": 0,
                "probation_status": "Passed",
                "years_of_service": 1,
                "start_date": "2024-01-01",
                "balances": [],
                "manager_history": [],
                "recent_leave_requests": [],
                "recent_expense_claims": [],
            }

        # Balances
        balances = []
        annual_left = 20
        sick_left = 10
        carry_over_left = 0

        for b in emp.leave_balances:
            balances.append({
                "type": b.leave_type,
                "entitled": b.entitled_days,
                "used": b.used_days,
                "remaining": b.remaining_days,
                "carry_over": b.carry_over_days,
                "unit": b.unit,
            })
            if "annual" in b.leave_type.lower():
                annual_left = b.remaining_days
                carry_over_left = b.carry_over_days
            elif "sick" in b.leave_type.lower():
                sick_left = b.remaining_days

        # Manager history
        mgr_history = [
            {
                "previous_manager": h.previous_manager,
                "current_manager": h.current_manager,
                "effective_date": h.effective_date,
                "reason": h.change_reason,
            }
            for h in sorted(emp.manager_history, key=lambda x: x.effective_date, reverse=True)
        ]

        # Recent leave requests
        leave_reqs = [
            {
                "leave_type": r.leave_type,
                "start_date": r.start_date,
                "end_date": r.end_date,
                "days": r.days_requested,
                "status": r.status,
                "approver": r.approver_name,
                "notes": r.notes,
            }
            for r in sorted(emp.leave_requests, key=lambda x: x.start_date, reverse=True)
        ]

        # Expense claims
        expenses = [
            {
                "category": e.category,
                "amount_aed": e.amount_aed,
                "date": e.claim_date,
                "status": e.status,
                "approver": e.approver,
            }
            for e in sorted(emp.expense_claims, key=lambda x: x.claim_date, reverse=True)
        ]

        return {
            "user_id": emp.user_id,
            "name": emp.name,
            "name_ar": emp.name_ar,
            "role": emp.role,
            "job_title": emp.job_title or emp.role,
            "department": emp.department,
            "grade": emp.grade,
            "email": emp.email,
            "phone": emp.phone,
            "location": emp.location,
            "start_date": emp.start_date,
            "years_of_service": emp.years_of_service,
            "probation_status": emp.probation_status,
            "manager_name": emp.manager_name,
            "manager_email": emp.manager_email,
            "manager_role": emp.manager_role,
            "annual_leave_balance": annual_left,
            "sick_leave_balance": sick_left,
            "carry_over_days": carry_over_left,
            "balances": balances,
            "manager_history": mgr_history,
            "recent_leave_requests": leave_reqs,
            "recent_expense_claims": expenses,
        }
    finally:
        session.close()


def execute_employee_sql(query_str: str) -> list[dict[str, Any]]:
    """
    Safely executes a read-only SQL query against the Omni HR database.
    """
    session = SessionLocal()
    try:
        # Prevent non-SELECT destructive commands
        forbidden = ["drop", "delete", "truncate", "update", "insert", "alter"]
        first_word = query_str.strip().split()[0].lower() if query_str.strip() else ""
        if first_word in forbidden or ";" in query_str.rstrip(";"):
            raise ValueError(f"Only single read-only SELECT queries are allowed. Got: {query_str}")

        result = session.execute(text(query_str))
        columns = result.keys()
        rows = [dict(zip(columns, row)) for row in result.fetchall()]
        return rows
    except Exception as e:
        logger.error(f"SQL execution error: {e}")
        return [{"error": str(e)}]
    finally:
        session.close()


def update_employee_manager_sql(
    employee_id: str,
    new_manager_name: str,
    new_manager_email: Optional[str] = None,
    new_manager_role: Optional[str] = "Line Manager",
    change_reason: str = "Manager reassignment / promotion",
    effective_date: Optional[str] = None,
) -> dict[str, Any]:
    """
    Update an employee's line manager in the SQL database and record the transition in manager_history.
    """
    session = SessionLocal()
    try:
        emp = session.query(Employee).filter(Employee.user_id == employee_id).first()
        if not emp:
            raise ValueError(f"Employee {employee_id} not found in SQL database.")

        old_manager = emp.manager_name
        eff_date = effective_date or datetime.utcnow().strftime("%Y-%m-%d")

        # 1. Update employee record
        emp.manager_name = new_manager_name
        if new_manager_email:
            emp.manager_email = new_manager_email
        if new_manager_role:
            emp.manager_role = new_manager_role
        emp.updated_at = datetime.utcnow()

        # 2. Record in ManagerHistory
        history = ManagerHistory(
            employee_id=emp.user_id,
            previous_manager=old_manager,
            current_manager=new_manager_name,
            effective_date=eff_date,
            change_reason=change_reason,
        )
        session.add(history)
        session.commit()

        logger.info(f"✅ SQL DB: Changed manager for {emp.name} ({employee_id}) from '{old_manager}' to '{new_manager_name}'.")

        return {
            "employee_id": emp.user_id,
            "name": emp.name,
            "previous_manager": old_manager,
            "current_manager": new_manager_name,
            "effective_date": eff_date,
            "change_reason": change_reason,
        }
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to update manager in SQL DB: {e}")
        raise
    finally:
        session.close()


def update_leave_balance_sql(
    employee_id: str,
    leave_type: str = "Annual leave",
    remaining_days: int = 18,
    used_days: Optional[int] = None,
    carry_over_days: Optional[int] = None,
) -> dict[str, Any]:
    """
    Update leave balance in the SQL database.
    """
    session = SessionLocal()
    try:
        bal = session.query(LeaveBalance).filter(
            LeaveBalance.employee_id == employee_id,
            LeaveBalance.leave_type.ilike(f"%{leave_type}%"),
        ).first()

        if not bal:
            bal = LeaveBalance(
                employee_id=employee_id,
                leave_type=leave_type,
                entitled_days=30,
                used_days=max(0, 30 - remaining_days) if used_days is None else used_days,
                remaining_days=remaining_days,
                carry_over_days=carry_over_days or 0,
            )
            session.add(bal)
        else:
            bal.remaining_days = remaining_days
            if used_days is not None:
                bal.used_days = used_days
            else:
                bal.used_days = max(0, bal.entitled_days - remaining_days)
            if carry_over_days is not None:
                bal.carry_over_days = carry_over_days
            bal.updated_at = datetime.utcnow()

        session.commit()
        logger.info(f"✅ SQL DB: Updated {leave_type} balance for {employee_id} to {remaining_days} days remaining.")

        return {
            "employee_id": employee_id,
            "leave_type": bal.leave_type,
            "remaining_days": bal.remaining_days,
            "used_days": bal.used_days,
            "entitled_days": bal.entitled_days,
            "carry_over_days": bal.carry_over_days,
        }
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to update leave balance in SQL DB: {e}")
        raise
    finally:
        session.close()
