"""
Turns the application's own errors into HTTP responses.

Keeping this in one place means nothing below the API layer has to know about status
codes, and the web interface always receives the `detail` key it reads error text from.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.errors import (
    EmployeeNotFoundError,
    LanguageModelUnavailableError,
    PolicyIndexEmptyError,
)

NOT_FOUND = 404
SERVICE_UNAVAILABLE = 503


def register_error_handlers(application: FastAPI) -> None:
    """Attach a handler for each error the application raises on purpose."""

    @application.exception_handler(EmployeeNotFoundError)
    async def handle_employee_not_found(request: Request, error: EmployeeNotFoundError):
        return JSONResponse(status_code=NOT_FOUND, content={"detail": str(error)})

    @application.exception_handler(PolicyIndexEmptyError)
    async def handle_policy_index_empty(request: Request, error: PolicyIndexEmptyError):
        return JSONResponse(status_code=SERVICE_UNAVAILABLE, content={"detail": str(error)})

    @application.exception_handler(LanguageModelUnavailableError)
    async def handle_language_model_unavailable(
        request: Request, error: LanguageModelUnavailableError
    ):
        return JSONResponse(status_code=SERVICE_UNAVAILABLE, content={"detail": str(error)})
