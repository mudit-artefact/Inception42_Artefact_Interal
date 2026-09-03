"""
HCS-11 School Verification Endpoints for HCS-01 Concierge.
Provides REST access to proof of schooling status, dependent details, and cases.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from app.services.hcs11_client import hcs11_client

router = APIRouter(prefix="/api/v1/hcs11", tags=["school-verification"])


@router.get("/health")
def get_hcs11_health() -> Dict[str, Any]:
    """Check HCS-11 connectivity and database health."""
    return hcs11_client.check_health()


@router.get("/cases")
def list_school_cases(
    employee_id: Optional[str] = Query(None, description="HCS-11 or HCS-01 employee ID"),
    status: Optional[str] = Query(None, description="Filter by case status"),
) -> List[Dict[str, Any]]:
    """List school verification cases."""
    return hcs11_client.list_cases(employee_id=employee_id, status=status)


@router.get("/cases/{case_id}")
def get_school_case(case_id: str) -> Dict[str, Any]:
    """Get details of a specific schooling verification case."""
    case = hcs11_client.get_case_detail(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return case


@router.get("/dependents")
def list_dependents(
    employee_id: Optional[str] = Query(None, description="Employee ID")
) -> List[Dict[str, Any]]:
    """Get eligible dependents and children for education allowance."""
    return hcs11_client.get_dependents(employee_id=employee_id)
