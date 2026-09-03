"""Every endpoint the application serves, gathered into one router."""

from fastapi import APIRouter

from app.api.endpoints import (
    ask_question,
    employees,
    notifications,
    policies,
    school_verification,
    service_status,
)

api_router = APIRouter()
api_router.include_router(ask_question.router)
api_router.include_router(policies.router)
api_router.include_router(employees.router)
api_router.include_router(service_status.router)
api_router.include_router(school_verification.router)
api_router.include_router(notifications.router)
