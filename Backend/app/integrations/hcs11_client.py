"""
HTTP client for the HCS-11 document verification backend.

All methods are async because verification can take 30-60 seconds
(AI reads each document), and we don't want to block other requests.
"""

import logging
import re
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
from .hcs11_schemas import (
    CaseDetail,
    CaseSummary,
    HealthResponse,
    VisaCaseOut,
    contract_is_signed,
)

logger = logging.getLogger(__name__)


def _checklist_names(case: dict) -> dict[str, str]:
    """
    A visa case's checklist as `{kind: what HCS-11 calls it}`.

    Tolerant of both shapes on purpose. HCS-11 used to send `required_documents` as bare
    kind strings and now sends `{kind, label}` objects; this is a service boundary we do
    not control, and the reader that feeds the assistant's prose should bend rather than
    put `{'kind': 'passport', ...}` in front of an employee. The strict reading lives in
    `VisaCaseOut`, which fails loudly and is the right place to notice a contract change.
    """
    names: dict[str, str] = {}
    for entry in case.get("required_documents") or ():
        if isinstance(entry, dict):
            kind = entry.get("kind")
            if kind:
                names[kind] = entry.get("label") or kind
        elif isinstance(entry, str):
            names[entry] = entry
    return names


def map_hcs01_to_hcs11_employee_id(employee_id: str) -> str:
    """
    Map HCS-01 employee IDs (EMP001) to HCS-11 format (E0001).

    HCS-01 uses EMP001, EMP002, etc.
    HCS-11 uses E0001, E0002, etc.
    """
    if employee_id.startswith("EMP") and employee_id[3:].isdigit():
        number = int(employee_id[3:])
        return f"E{number:04d}"
    # Already in HCS-11 format or unknown format - return as-is
    return employee_id


def map_hcs11_to_hcs01_employee_id(employee_id: str) -> str:
    """
    Map HCS-11 employee IDs (E0015) back to ours (EMP015).

    The inverse of the map above, needed the moment anything HCS-11 tells us has to be
    written against our own records — a notification is addressed to a row in our employee
    table, and HCS-11 only ever says whose case it is in its own vocabulary.

    It is a convention rather than a proof: the forward map is not injective on width, so
    `EMP15` and `EMP015` both become `E0015` and only one of them can come back. Our seeded
    ids are three digits throughout, so the convention holds.

    Not to be confused with the id fallback in `employee_repository.get_employee_facts`,
    which attempts the same translation and gets it wrong in both directions — `E0015`
    becomes `EMP0015` and `EMP015` becomes `E015`, neither of which is anybody. That branch
    is unreachable today and is left alone deliberately; this is the one to use.
    """
    if employee_id.startswith("E") and employee_id[1:].isdigit():
        return f"EMP{int(employee_id[1:]):03d}"
    # Already in our format, or a shape neither system uses — hand it back untouched, as
    # the forward map does.
    return employee_id


def _filename_from(disposition: str) -> str:
    """
    The name HCS-11 gave the file, or a sensible one if it gave none.

    The header reads `inline; filename="employment-contract-ahmed-al-rashid.pdf"`, and it
    is worth honouring: HCS-11 names the signed copy differently from the unsigned draft,
    so the name is the one place a saved file says which it was.
    """
    match = re.search(r'filename="?([^"\r\n;]+)"?', disposition)
    return match.group(1).strip() if match else "employment-contract.pdf"


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
            employee_id: Filter to one employee's cases (HCS-01 format like EMP001)
            status: Filter by case status (e.g., "Under Review", "Approved")

        Returns:
            List of case summaries
        """
        client = self._ensure_client()
        params = {}
        if employee_id:
            # Map HCS-01 format (EMP001) to HCS-11 format (E0001)
            params["employee_id"] = map_hcs01_to_hcs11_employee_id(employee_id)
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

    async def list_visa_cases(self, employee_id: str) -> list[VisaCaseOut]:
        """
        Every employment visa case HCS-11 holds for this new joiner.

        HCS-11's visa listing takes an employee and nothing else — there is no status
        filter, because a visa case has only two states and no payment leg to close it.
        """
        client = self._ensure_client()
        try:
            response = await client.get(
                "/api/visa/cases",
                params={"employee_id": map_hcs01_to_hcs11_employee_id(employee_id)},
            )
            response.raise_for_status()
            return [VisaCaseOut(**case) for case in response.json()]
        except httpx.ConnectError as e:
            raise HCS11ConnectionError() from e
        except httpx.TimeoutException as e:
            raise HCS11TimeoutError() from e

    async def get_visa_case(self, case_id: str) -> VisaCaseOut:
        """One visa case in full, with its documents and the checks run against them."""
        client = self._ensure_client()
        try:
            response = await client.get(f"/api/visa/cases/{case_id}")
            if response.status_code == 404:
                raise HCS11CaseNotFoundError(
                    employee_id="unknown",
                    message=f"Visa case {case_id} not found",
                )
            response.raise_for_status()
            return VisaCaseOut(**response.json())
        except httpx.ConnectError as e:
            raise HCS11ConnectionError() from e
        except httpx.TimeoutException as e:
            raise HCS11TimeoutError() from e

    # ─── The employment contract ────────────────────────────────────────────
    #
    # The one document on a visa case that travels towards the new joiner rather than away
    # from them, so it needs a reader and a writer of its own rather than riding on the
    # upload path. Both live here beside the visa case they belong to; there is no separate
    # contract case in HCS-11 and inventing one on this side would be a third vocabulary
    # for something that is a field.

    async def read_contract_pdf(self, case_id: str) -> tuple[bytes, str, str]:
        """
        The contract as a file, with its content type and the name HCS-11 gives it.

        Returned rather than parsed: this endpoint answers with a PDF, not JSON. It serves
        the signed copy once one is filed and draws a fresh unsigned one before that, so
        there is no "no contract yet" case to handle — a visa case always has one.
        """
        client = self._ensure_client()
        try:
            response = await client.get(f"/api/visa/cases/{case_id}/contract")
            if response.status_code == 404:
                raise HCS11CaseNotFoundError(
                    employee_id="unknown",
                    message=f"Visa case {case_id} not found",
                )
            response.raise_for_status()
            return (
                response.content,
                response.headers.get("content-type", "application/pdf"),
                _filename_from(response.headers.get("content-disposition", "")),
            )
        except httpx.ConnectError as e:
            raise HCS11ConnectionError() from e
        except httpx.TimeoutException as e:
            raise HCS11TimeoutError() from e

    async def sign_contract(self, case_id: str) -> VisaCaseOut:
        """
        Accept the contract on the employee's behalf, and read the case back.

        **HCS-11 answers 409 for two different reasons, and they are opposites.** One is
        that the contract is already signed. The other is that it is too early — the
        documents have not been checked, so there is nothing to sign yet. Both are answers
        rather than failures, which is why neither is raised as an error, and HCS-11 writes
        a sentence for each. That sentence is passed through: deciding here that every 409
        means "already signed" told a joiner who had signed nothing the exact opposite of
        the truth.

        Signing no longer moves the checklist. It once filed the signed copy as the
        job-offer document and re-ran every check; the two are now separate documents, and
        the offer letter is one the joiner sends. So the case that comes back carries a
        signed contract and the same checklist it had before.
        """
        client = self._ensure_client()
        try:
            response = await client.post(f"/api/visa/cases/{case_id}/contract/sign")
            if response.status_code == 404:
                raise HCS11CaseNotFoundError(
                    employee_id="unknown",
                    message=f"Visa case {case_id} not found",
                )
            if response.status_code == 409:
                raise HCS11ValidationError(409, _why_it_was_refused(response))
            response.raise_for_status()
            return VisaCaseOut(**response.json())
        except httpx.ConnectError as e:
            raise HCS11ConnectionError() from e
        except httpx.TimeoutException as e:
            raise HCS11TimeoutError() from e

    async def get_employee_cases(self, employee_id: str) -> list[CaseSummary]:
        """Get all cases for an employee (one per child per academic year).

        Args:
            employee_id: HCS-01 format like EMP001 (automatically mapped to HCS-11 format)
        """
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
        process: str = "school",
    ) -> CaseDetail | VisaCaseOut:
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
            HCS11AlreadyPaidError: Case was sent to payroll — school only, HCS-11's visa
                upload never returns 409
            HCS11DocumentError: File rejected (wrong type, too large)
            HCS11ValidationError: Other validation error

        Sending a school document and sending a visa document differ in three lines: the
        path, the model the answer is parsed into, and nothing else. Every status-code
        branch below, and both connection handlers, are the same for either.
        """
        client = self._ensure_client()
        sending_a_visa_document = process == "visa"

        form_files = [
            ("files", (filename, file_obj, content_type))
            for filename, file_obj, content_type in files
        ]

        try:
            logger.info(f"Uploading {len(files)} document(s) to case {case_id}")
            response = await client.post(
                f"/api/visa/cases/{case_id}/documents"
                if sending_a_visa_document
                else f"/api/hcs11/cases/{case_id}/documents",
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
            parse = VisaCaseOut if sending_a_visa_document else CaseDetail
            result = parse(**response.json())
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


# ── Reading a claim's progress, from inside a workflow step ──────────────────────
#
# The client above is async, because uploading a document is. Reading where a claim has
# got to happens inside a LangGraph step, which is synchronous and may already be running
# inside an event loop — so it cannot await, and it cannot start a loop of its own.
#
# This is the same request the upload window already makes. It is read-only: HCS-11 is
# asked, never told.

# Short on purpose. This runs while an employee waits for a reply, and a claim status is
# worth a couple of seconds, not a minute. Nothing found beats nothing shown.
CLAIM_READ_TIMEOUT_SECONDS = 8


def read_school_claims(employee_id: str) -> list[dict] | None:
    """
    Every school verification claim HCS-11 holds for this employee.

    `None` means HCS-11 could not be asked — which is not the same as an employee having
    no claims, and the two must not be told to the employee as though they were.
    """
    from app.core.settings import settings

    hcs11_employee_id = map_hcs01_to_hcs11_employee_id(employee_id)
    try:
        response = httpx.get(
            f"{settings.hcs11_backend_url.rstrip('/')}/api/hcs11/cases",
            params={"employee_id": hcs11_employee_id},
            timeout=CLAIM_READ_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        cases = response.json()
    except Exception as unreachable:
        logger.warning(f"Could not read school claims for {employee_id}: {unreachable}")
        return None

    if not isinstance(cases, list):
        logger.warning(f"HCS-11 returned {type(cases).__name__} for {employee_id}, not a list")
        return None

    base = settings.hcs11_backend_url.rstrip("/")
    cases = [_the_whole_case(base, "/api/hcs11/cases", case)
             for case in cases if isinstance(case, dict)]

    # Only what an employee is owed about their own claim. The reviewer, the internal
    # routing verdict and the rule codes are HCS-11's working, not theirs.
    return [
        {
            "case_id": case.get("case_id", ""),
            "child_name": case.get("dependent_name", ""),
            "academic_year": case.get("academic_year", ""),
            "status": case.get("case_status", ""),
            "recommendation": case.get("recommendation", ""),
            "submitted_on": case.get("submitted_on") or "",
            "submission_deadline": case.get("submission_deadline") or "",
            "approved_on": case.get("approved_on") or "",
            "payment_status": case.get("payment_status", ""),
            "awaiting_review": bool(case.get("awaiting_review")),
            # What the claim needs and what is wrong with it. These come only from the
            # per-case reading; the listing leaves them out, which is why the assistant
            # could report a status and nothing else about a claim HCS-11 had rejected.
            "required_documents": tuple(
                row.get("label") or row.get("kind", "")
                for row in case.get("required_documents") or ()
                if isinstance(row, dict)
            ),
            "missing_documents": tuple(
                _school_document_names(case).get(kind, kind)
                for kind in case.get("missing_documents") or ()
            ),
            "problems": tuple(
                f"{issue.get('title', '')}. {issue.get('what_to_do', '')}".strip(" .")
                for issue in case.get("employee_issues") or ()
                if issue.get("title")
            ),
        }
        for case in cases
        if isinstance(case, dict)
    ]


def _school_document_names(case: dict) -> dict[str, str]:
    """A school case's checklist as `{kind: what HCS-11 calls it}`."""
    return {
        row["kind"]: row.get("label") or row["kind"]
        for row in case.get("required_documents") or ()
        if isinstance(row, dict) and row.get("kind")
    }


def _the_whole_case(base_url: str, path: str, summary: dict) -> dict:
    """
    The full case, or the summary if it cannot be had.

    HCS-11's list endpoints are summaries: they carry the status and the dates, and they
    return `problems` as an empty list whatever the case says. Only the per-case endpoint
    fills it in.

    Reading the list was enough until it wasn't. Somebody whose documents belonged to
    another person asked what the status of their application was and was told every
    document had been received and nothing was outstanding — true of the summary, and the
    opposite of what HCS-11 had decided. The assistant was not wrong; it was told nothing
    was wrong.

    One extra request per case, and only on a turn that asks about a case at all.
    """
    case_id = summary.get("case_id")
    if not case_id:
        return summary
    try:
        response = httpx.get(
            f"{base_url}{path}/{case_id}", timeout=CLAIM_READ_TIMEOUT_SECONDS
        )
        response.raise_for_status()
        full = response.json()
    except Exception as unreachable:
        # The summary is thin, not wrong. Better a partial answer than none — and the
        # fields it does carry are the ones it is authoritative about.
        logger.warning(f"Could not read the detail of {case_id}: {unreachable}")
        return summary
    return full if isinstance(full, dict) else summary


def _why_it_was_refused(response: httpx.Response) -> str:
    """
    HCS-11's own sentence for a 409, or ours if it did not send one.

    Its two refusals — already signed, and not yet checked — are told apart only by this
    text, so writing our own here loses the distinction. The fallback names neither, since
    guessing which one it was is how the wrong sentence got shown in the first place.
    """
    try:
        detail = response.json().get("detail")
    except ValueError:
        detail = None
    return detail if isinstance(detail, str) and detail.strip() else (
        "This contract cannot be signed at the moment."
    )


def _contract_facts(case: dict) -> dict:
    """
    The employment contract on a visa case, flattened onto the fields `VisaCase` declares.

    Flat rather than nested because the record is frozen and round-trips through a JSON
    checkpoint: `from_dictionary` turns lists back into tuples, but it does not rebuild a
    nested dataclass, so a nested contract would come back a plain dict and compare
    unequal to the one that was stored.

    `contract_is_signed` is the field to read, and it is deliberately not `signed_on`.
    HCS-11 once set `signed_on` whenever a job-offer document existed at all — including one
    the joiner uploaded that was not signed, where it fell back to the day the file arrived.
    It now sets the date only when the contract is actually signed, so the OFFER_SIGNED
    guard is a backstop rather than the whole answer. It is kept: it costs nothing, and an
    HCS-11 that has not been updated still gets read honestly.

    `contract_available` is HCS-11 saying whether it is this employee's turn. It refuses the
    signature with a 409 until the documents have been checked, so offering the panel before
    then offers a button that cannot work. Absent means `False` — an older HCS-11 does not
    send it, and "not yet" is the safe reading of silence.
    """
    contract = case.get("contract")
    if not isinstance(contract, dict):
        return {}

    signed_on = contract.get("signed_on") or ""
    verdicts = [
        (check.get("code"), check.get("result"))
        for check in case.get("checks") or ()
        if isinstance(check, dict)
    ]
    salary = contract.get("annual_salary_aed")

    return {
        "contract_prepared_on": contract.get("prepared_on") or "",
        "contract_signed_on": signed_on,
        "contract_is_signed": contract_is_signed(signed_on, verdicts),
        "contract_job_title": contract.get("job_title") or "",
        "contract_start_date": contract.get("start_date") or "",
        "contract_salary_aed": salary if isinstance(salary, int) else None,
        "contract_available": bool(contract.get("available")),
    }


def read_visa_case(employee_id: str) -> list[dict] | None:
    """
    The employment visa case HCS-11 holds for this new joiner, if there is one.

    The same request the visa document window makes, and read-only: HCS-11 is asked, never
    told. `None` means it could not be asked, which is not the same as a person having no
    case, and the two must never be told to somebody as though they were.
    """
    from app.core.settings import settings

    hcs11_employee_id = map_hcs01_to_hcs11_employee_id(employee_id)
    try:
        response = httpx.get(
            f"{settings.hcs11_backend_url.rstrip('/')}/api/visa/cases",
            params={"employee_id": hcs11_employee_id},
            timeout=CLAIM_READ_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        cases = response.json()
    except Exception as unreachable:
        logger.warning(f"Could not read the visa case for {employee_id}: {unreachable}")
        return None

    if not isinstance(cases, list):
        logger.warning(f"HCS-11 returned {type(cases).__name__} for {employee_id}, not a list")
        return None

    base = settings.hcs11_backend_url.rstrip("/")
    cases = [_the_whole_case(base, "/api/visa/cases", case)
             for case in cases if isinstance(case, dict)]

    # Only what the new joiner is owed about their own case. The routing verdict, the check
    # codes, the legal entity and the nationality read off their passport are HCS-11's own
    # working, not theirs.
    return [
        {
            "case_id": case.get("case_id", ""),
            "plan_name": case.get("plan_name", ""),
            "status": case.get("case_status", ""),
            "submission_deadline": case.get("submission_deadline") or "",
            "submitted_on": case.get("submitted_on") or "",
            "required_documents": tuple(_checklist_names(case).values()),
            "missing_documents": tuple(
                _checklist_names(case).get(kind, kind)
                for kind in case.get("missing_documents") or ()
            ),
            "problems": tuple(case.get("problems") or ()),
            **_contract_facts(case),
        }
        for case in cases
    ]
