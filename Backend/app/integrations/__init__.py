"""
HCS-11 Document Verification Integration.

This module provides the chatbot's connection to the HCS-11 backend
for employee document uploads and verification status.

Usage:
    from app.integrations import get_hcs11_client, format_upload_result

    async with get_hcs11_client() as client:
        # Get employee's active case
        case = await client.get_active_case(employee_id="EMP001")

        # Upload documents
        result = await client.upload_documents(
            case_id=case.case_id,
            files=[("letter.pdf", file_obj, "application/pdf")],
        )

        # Format for chat display
        upload_result = format_upload_result(result)
"""

from .hcs11_client import HCS11Client, get_hcs11_client
from .hcs11_errors import (
    HCS11AlreadyPaidError,
    HCS11CaseNotFoundError,
    HCS11ConnectionError,
    HCS11DocumentError,
    HCS11Error,
    HCS11TimeoutError,
    HCS11ValidationError,
)
from .hcs11_response_formatter import (
    DocumentStatus,
    UploadResult,
    UploadStatus,
    format_case_status_message,
    format_error_message,
    format_upload_result,
)
from .hcs11_schemas import (
    CaseDetail,
    CaseSummary,
    DocumentOut,
    EmployeeIssueOut,
    HealthResponse,
    RequiredDocumentOut,
)

__all__ = [
    # Client
    "HCS11Client",
    "get_hcs11_client",
    # Errors
    "HCS11Error",
    "HCS11ConnectionError",
    "HCS11TimeoutError",
    "HCS11ValidationError",
    "HCS11CaseNotFoundError",
    "HCS11DocumentError",
    "HCS11AlreadyPaidError",
    # Schemas
    "CaseSummary",
    "CaseDetail",
    "DocumentOut",
    "RequiredDocumentOut",
    "EmployeeIssueOut",
    "HealthResponse",
    # Response formatting
    "UploadStatus",
    "UploadResult",
    "DocumentStatus",
    "format_upload_result",
    "format_case_status_message",
    "format_error_message",
]
