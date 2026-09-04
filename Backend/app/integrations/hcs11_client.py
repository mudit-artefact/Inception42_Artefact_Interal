"""
HTTP client for the HCS-11 document verification backend.

All methods are async because verification can take 30-60 seconds
(AI reads each document), and we don't want to block other requests.
"""

import logging
from typing import BinaryIO

import httpx

from .hcs11_errors import (
    HCS11AlreadyPaidError,
    HCS11CaseNotFoundError,
    HCS11ConnectionError,
    HCS11DocumentError,
    HCS11TimeoutError,
    HCS11ValidationError,
)
from .hcs11_schemas import CaseDetail, CaseSummary, HealthResponse

logger = logging.getLogger(__name__)


class HCS11Client:
    """
    Async HTTP client for the HCS-11 document verification API.

    Usage:
        async with HCS11Client("http://localhost:8001") as client:
            cases = await client.list_cases(employee_id="EMP001")
            result = await client.upload_documents(case_id, files)
    """

    def __init__(self, base_url: str, timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "HCS11Client":
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout, connect=10.0),
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()
            self._client = None

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("HCS11Client must be used as async context manager")
        return self._client

    # ─── Health Check ───────────────────────────────────────────────────────

    async def health_check(self) -> HealthResponse:
        """Check if HCS-11 backend is available and get its status."""
        client = self._ensure_client()
        try:
            response = await client.get("/api/hcs11/health")
            response.raise_for_status()
            return HealthResponse(**response.json())
        except httpx.ConnectError as e:
            logger.error(f"Cannot connect to HCS-11: {e}")
            raise HCS11ConnectionError() from e
        except httpx.TimeoutException as e:
            logger.error(f"HCS-11 health check timed out: {e}")
            raise HCS11TimeoutError() from e

    # ─── Case Management ────────────────────────────────────────────────────

    async def list_cases(
        self,
        employee_id: str | None = None,
        status: str | None = None,
    ) -> list[CaseSummary]:
        """
        Get all cases, optionally filtered.

        Args:
            employee_id: Filter to one employee's cases
            status: Filter by case status (e.g., "Under Review", "Approved")

        Returns:
            List of case summaries
        """
        client = self._ensure_client()
        params = {}
        if employee_id:
            params["employee_id"] = employee_id
        if status:
            params["status"] = status

        try:
            response = await client.get("/api/hcs11/cases", params=params)
            response.raise_for_status()
            return [CaseSummary(**c) for c in response.json()]
        except httpx.ConnectError as e:
            raise HCS11ConnectionError() from e
        except httpx.TimeoutException as e:
            raise HCS11TimeoutError() from e

    async def get_case(self, case_id: str) -> CaseDetail:
        """
        Get full details of one case.

        Args:
            case_id: The case identifier

        Returns:
            Complete case details including documents and issues

        Raises:
            HCS11CaseNotFoundError: If the case doesn't exist
        """
        client = self._ensure_client()
        try:
            response = await client.get(f"/api/hcs11/cases/{case_id}")
            if response.status_code == 404:
                raise HCS11CaseNotFoundError(
                    employee_id="unknown",
                    message=f"Case {case_id} not found",
                )
            response.raise_for_status()
            return CaseDetail(**response.json())
        except httpx.ConnectError as e:
            raise HCS11ConnectionError() from e
        except httpx.TimeoutException as e:
            raise HCS11TimeoutError() from e

    async def get_employee_cases(self, employee_id: str) -> list[CaseSummary]:
        """Get all cases for an employee (one per child per academic year)."""
        return await self.list_cases(employee_id=employee_id)

    async def get_active_case(self, employee_id: str) -> CaseDetail | None:
        """
        Get the employee's current open case, if any.

        Returns the first case that isn't fully paid. Most employees
        have one active case per child.
        """
        cases = await self.list_cases(employee_id=employee_id)
        for case in cases:
            if case.payment_status not in ("Sent", "Paid"):
                return await self.get_case(case.case_id)
        return None

    # ─── Document Upload ────────────────────────────────────────────────────

    async def upload_documents(
        self,
        case_id: str,
        files: list[tuple[str, BinaryIO, str]],
    ) -> CaseDetail:
        """
        Upload documents to a case and run verification.

        This is the main integration point. HCS-11 runs the full
        verification pipeline (AI document reading, matching, rule checks)
        before responding, so this call can take 30-60 seconds.

        Args:
            case_id: The case to upload to
            files: List of (filename, file_object, content_type) tuples

        Returns:
            Updated case with verification results

        Raises:
            HCS11CaseNotFoundError: Case doesn't exist
            HCS11AlreadyPaidError: Case was sent to payroll
            HCS11DocumentError: File rejected (wrong type, too large)
            HCS11ValidationError: Other validation error
        """
        client = self._ensure_client()

        if not files:
            raise ValueError("No files provided for upload")

        filename, file_obj, content_type = files[0]
        form_files = {"file": (filename, file_obj, content_type)}

        try:
            logger.info(f"Uploading document '{filename}' to case {case_id}")
            response = await client.post(
                f"/api/hcs11/cases/{case_id}/documents",
                files=form_files,
            )

            if response.status_code == 404:
                raise HCS11CaseNotFoundError(
                    employee_id="unknown",
                    message=f"Case {case_id} not found",
                )

            if response.status_code == 409:
                detail = response.json().get("detail", "")
                if "payroll" in detail.lower():
                    raise HCS11AlreadyPaidError(case_id)
                raise HCS11ValidationError(409, detail)

            if response.status_code == 413:
                detail = response.json().get("detail", "File too large")
                filename = self._extract_filename_from_error(detail)
                raise HCS11DocumentError(
                    filename=filename,
                    error_type="too_large",
                    detail="File exceeds the 10MB limit",
                )

            if response.status_code == 415:
                detail = response.json().get("detail", "Unsupported file type")
                filename = self._extract_filename_from_error(detail)
                raise HCS11DocumentError(
                    filename=filename,
                    error_type="unsupported_type",
                    detail=detail,
                )

            if response.status_code == 400:
                detail = response.json().get("detail", "Invalid file")
                filename = self._extract_filename_from_error(detail)
                raise HCS11DocumentError(
                    filename=filename,
                    error_type="invalid",
                    detail=detail,
                )

            response.raise_for_status()
            result = CaseDetail(**response.json())
            logger.info(
                f"Upload complete for case {case_id}: "
                f"status={result.case_status}, route={result.route}"
            )
            return result

        except httpx.ConnectError as e:
            raise HCS11ConnectionError() from e
        except httpx.TimeoutException as e:
            raise HCS11TimeoutError(
                "Document verification is taking longer than expected. "
                "Please try again in a few minutes."
            ) from e

    async def remove_document(
        self,
        case_id: str,
        document_id: str,
    ) -> CaseDetail:
        """
        Remove a document from a case.

        Used when an employee needs to replace a wrongly uploaded file.
        The case is re-evaluated after removal.

        Args:
            case_id: The case containing the document
            document_id: The document to remove

        Returns:
            Updated case after removal
        """
        client = self._ensure_client()

        try:
            response = await client.delete(
                f"/api/hcs11/cases/{case_id}/documents/{document_id}"
            )

            if response.status_code == 404:
                raise HCS11CaseNotFoundError(
                    employee_id="unknown",
                    message="Case or document not found",
                )

            if response.status_code == 409:
                detail = response.json().get("detail", "")
                if "payroll" in detail.lower():
                    raise HCS11AlreadyPaidError(case_id)
                raise HCS11ValidationError(409, detail)

            response.raise_for_status()
            return CaseDetail(**response.json())

        except httpx.ConnectError as e:
            raise HCS11ConnectionError() from e
        except httpx.TimeoutException as e:
            raise HCS11TimeoutError() from e

    # ─── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_filename_from_error(detail: str) -> str:
        """Extract filename from error messages like 'invoice.docx: unsupported type'."""
        if ":" in detail:
            return detail.split(":")[0].strip()
        return "unknown file"


def get_hcs11_client() -> HCS11Client:
    """
    Create an HCS-11 client from application settings.

    Returns a client that must be used as an async context manager:

        async with get_hcs11_client() as client:
            cases = await client.list_cases(employee_id="EMP001")
    """
    from app.core.settings import settings

    return HCS11Client(
        base_url=settings.hcs11_backend_url,
        timeout=settings.hcs11_timeout_seconds,
    )
