"""
HCS-11 Document Verification Endpoints.

These endpoints proxy document operations to the HCS-11 backend,
allowing employees to upload and manage verification documents
through the chatbot interface.

The HCS-11 backend runs the actual verification pipeline (AI document
reading, matching, rule checks). This layer handles:
- File validation before forwarding
- Error translation to user-friendly messages
- Response formatting for chat display
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.endpoints.document_upload_shared import (
    ALLOWED_CONTENT_TYPES,
    MAX_FILE_SIZE,
    ReadableBytes,
    require_hcs11_enabled,
    sse_event,
    validate_file,
)
from app.core.settings import settings
from app.integrations import (
    CaseDetail,
    CaseSummary,
    DocumentStatus,
    HCS11AlreadyPaidError,
    HCS11CaseNotFoundError,
    HCS11ConnectionError,
    HCS11DocumentError,
    HCS11TimeoutError,
    HCS11ValidationError,
    UploadResult,
    UploadStatus,
    format_case_status_message,
    format_error_message,
    format_upload_result,
    get_hcs11_client,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/hcs11", tags=["HCS-11 Document Verification"])

# The two readings that mean the employee has nothing left to do. Everything else — a
# claim waiting on a person, one sent back for better copies, one rejected outright —
# leaves something to say, and the panel must not show it as finished.
NOTHING_LEFT_TO_DO = {UploadStatus.SUCCESS, UploadStatus.ALREADY_PAID}


# ─── Request/Response Schemas ───────────────────────────────────────────────


class CaseListResponse(BaseModel):
    """List of cases for an employee."""
    cases: list[CaseSummary]
    count: int


class CaseDetailResponse(BaseModel):
    """
    Full case details, with the checklist already worked out.

    `documents` is the same per-file verdict an upload returns. The panel used to be given
    only the raw case and worked the verdicts out itself, from a hand-written list of
    check codes and problem kinds that did not match what HCS-11 actually sends — so a
    problem HCS-11 had recorded was shown as a green tick. Deciding it once, here, is why
    that cannot happen again: there is one answer and the screen displays it.

    `everything_is_settled` is HCS-11's own verdict on the claim as a whole, so the "all
    good" banner has something true to depend on instead of counting files.
    """
    case: CaseDetail
    status_message: str
    documents: list[DocumentStatus] = []
    problems: list[str] = []
    everything_is_settled: bool = False


class UploadResponse(BaseModel):
    """Response after document upload."""
    status: UploadStatus
    title: str
    message: str
    documents: list[DocumentStatus]
    issues: list[str]
    missing_documents: list[str]
    can_reupload: bool
    reupload_message: str | None
    case_id: str | None
    case_status: str | None
    payment_amount: float | None
    payment_status: str | None


class ErrorResponse(BaseModel):
    """User-friendly error response."""
    error: str
    error_type: str
    can_retry: bool


def _as_case_detail(case: CaseDetail) -> CaseDetailResponse:
    """
    One claim, read once, the same way for every route that returns one.

    Two routes returned this shape and only one of them filled it in. Building the
    response in each place is what let them drift, and the half-built one silently said
    every claim was fine.
    """
    verdict = format_upload_result(case)
    return CaseDetailResponse(
        case=case,
        status_message=format_case_status_message(case),
        documents=verdict.documents,
        problems=_problems_belonging_to_no_document(verdict),
        everything_is_settled=verdict.status in NOTHING_LEFT_TO_DO,
    )


def _problems_belonging_to_no_document(verdict: UploadResult) -> list[str]:
    """
    The problems with nowhere else to appear — the eligibility rules, mostly.

    `issues` is the complete list, and every problem is in it whether or not it also sits
    against a file. Sending the whole thing to the panel printed the same finding three
    times: once on the certificate's row, once as HCS-11's plain-English sentence, and
    once more as the rule that produced it. A claim with one thing wrong looked like a
    claim with three.

    What is left is what the rows cannot say, which is exactly what the section under
    them is for.
    """
    already_on_a_row = " ".join(
        document.issue_message or "" for document in verdict.documents
    )
    return [problem for problem in verdict.issues if problem not in already_on_a_row]


# ─── Dependency ─────────────────────────────────────────────────────────────


# `require_hcs11_enabled`, `validate_file`, `sse_event` and `ReadableBytes` now live in
# `document_upload_shared`, so the visa router uses the same ones rather than copies.


# ─── Endpoints ──────────────────────────────────────────────────────────────


@router.get(
    "/health",
    summary="Check HCS-11 backend availability",
    dependencies=[Depends(require_hcs11_enabled)],
)
async def health_check() -> dict:
    """Check if the HCS-11 document verification service is available."""
    try:
        async with get_hcs11_client() as client:
            health = await client.health_check()
            return {
                "status": "ok",
                "hcs11_status": health.status,
                "open_cycle": health.open_cycle,
            }
    except HCS11ConnectionError:
        raise HTTPException(
            status_code=503,
            detail="Document verification service is not available",
        )
    except HCS11TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="Document verification service did not respond in time",
        )


@router.get(
    "/cases",
    response_model=CaseListResponse,
    summary="List verification cases for an employee",
    dependencies=[Depends(require_hcs11_enabled)],
)
async def list_cases(employee_id: str) -> CaseListResponse:
    """
    Get all verification cases for an employee.

    Each case represents one child for one academic year. Most employees
    have one or a few active cases.
    """
    try:
        async with get_hcs11_client() as client:
            cases = await client.get_employee_cases(employee_id)
            return CaseListResponse(cases=cases, count=len(cases))
    except HCS11ConnectionError:
        raise HTTPException(status_code=503, detail="Document verification service unavailable")
    except HCS11TimeoutError:
        raise HTTPException(status_code=504, detail="Request timed out")


@router.get(
    "/cases/{case_id}",
    response_model=CaseDetailResponse,
    summary="Get full details of a verification case",
    dependencies=[Depends(require_hcs11_enabled)],
)
async def get_case(case_id: str) -> CaseDetailResponse:
    """
    Get complete details of a verification case.

    Includes documents uploaded, verification status, issues found,
    and payment information.
    """
    try:
        async with get_hcs11_client() as client:
            case = await client.get_case(case_id)
            # The same reading of the claim an upload gets. The panel opens on this
            # endpoint and polls it, so anything decided only on the upload path was
            # invisible for every view of a claim except the moment it was sent.
            return _as_case_detail(case)
    except HCS11CaseNotFoundError:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    except HCS11ConnectionError:
        raise HTTPException(status_code=503, detail="Document verification service unavailable")
    except HCS11TimeoutError:
        raise HTTPException(status_code=504, detail="Request timed out")


@router.get(
    "/active-case",
    response_model=CaseDetailResponse | None,
    summary="Get employee's current active case",
    dependencies=[Depends(require_hcs11_enabled)],
)
async def get_active_case(employee_id: str) -> CaseDetailResponse | None:
    """
    Get the employee's current open verification case, if any.

    Returns the first case that isn't fully paid. Returns null if
    all cases are complete or the employee has no cases.

    This used to fill two of the response's five fields, so `documents`, `problems` and
    `everything_is_settled` came back empty on every call — the endpoint reported "nothing
    wrong" whatever HCS-11 had decided. It is the same failure the panel had, in the one
    endpoint that was missed when that was fixed, and it was harmless only because nothing
    called it yet. The reading is now the same one `/cases/{case_id}` gives.
    """
    try:
        async with get_hcs11_client() as client:
            case = await client.get_active_case(employee_id)
            if case is None:
                return None
            return _as_case_detail(case)
    except HCS11ConnectionError:
        raise HTTPException(status_code=503, detail="Document verification service unavailable")
    except HCS11TimeoutError:
        raise HTTPException(status_code=504, detail="Request timed out")


@router.post(
    "/cases/{case_id}/documents",
    response_model=UploadResponse,
    summary="Upload documents to a verification case",
    dependencies=[Depends(require_hcs11_enabled)],
)
async def upload_documents(
    case_id: str,
    files: Annotated[list[UploadFile], File(description="Documents to upload (PDF, PNG, JPEG)")],
) -> UploadResponse:
    """
    Upload one or more documents to a verification case.

    The HCS-11 backend runs the full verification pipeline:
    1. AI reads each document
    2. Matches values against HR records
    3. Checks eligibility rules
    4. Routes to approval or review

    This can take 30-60 seconds. The response includes:
    - Which documents were accepted
    - Any issues found (with actionable messages)
    - What documents are still missing
    - Overall verification status
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    # Validate files locally first (fast feedback)
    validated_files = []
    for file in files:
        error = validate_file(file)
        if error:
            raise HTTPException(status_code=422, detail=error)

        content = await file.read()
        await file.seek(0)  # Reset for potential re-read
        validated_files.append((file.filename or "document", content, file.content_type))

    try:
        async with get_hcs11_client() as client:
            # Upload to HCS-11 and run verification
            case = await client.upload_documents(
                case_id=case_id,
                files=[
                    (name, ReadableBytes(content), content_type)
                    for name, content, content_type in validated_files
                ],
            )

            # Format result for chat display
            result = format_upload_result(case)
            return UploadResponse(
                status=result.status,
                title=result.title,
                message=result.message,
                documents=result.documents,
                issues=result.issues,
                missing_documents=result.missing_documents,
                can_reupload=result.can_reupload,
                reupload_message=result.reupload_message,
                case_id=result.case_id,
                case_status=result.case_status,
                payment_amount=result.payment_amount,
                payment_status=result.payment_status,
            )

    except HCS11CaseNotFoundError:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    except HCS11AlreadyPaidError as e:
        raise HTTPException(status_code=409, detail=e.message)

    except HCS11DocumentError as e:
        raise HTTPException(
            status_code=422,
            detail=format_error_message(e.error_type, e.detail, e.filename),
        )

    except HCS11ValidationError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

    except HCS11ConnectionError:
        raise HTTPException(
            status_code=503,
            detail=format_error_message("connection", "Service unavailable"),
        )

    except HCS11TimeoutError as e:
        raise HTTPException(
            status_code=504,
            detail=format_error_message("timeout", e.message),
        )


@router.delete(
    "/cases/{case_id}/documents/{document_id}",
    response_model=UploadResponse,
    summary="Remove a document from a case",
    dependencies=[Depends(require_hcs11_enabled)],
)
async def remove_document(case_id: str, document_id: str) -> UploadResponse:
    """
    Remove a document from a verification case.

    Used when an employee needs to replace a wrongly uploaded file.
    The case is re-evaluated after removal, so missing documents
    will be listed in the response.
    """
    try:
        async with get_hcs11_client() as client:
            case = await client.remove_document(case_id, document_id)
            result = format_upload_result(case)
            return UploadResponse(
                status=result.status,
                title=result.title,
                message=result.message,
                documents=result.documents,
                issues=result.issues,
                missing_documents=result.missing_documents,
                can_reupload=result.can_reupload,
                reupload_message=result.reupload_message,
                case_id=result.case_id,
                case_status=result.case_status,
                payment_amount=result.payment_amount,
                payment_status=result.payment_status,
            )

    except HCS11CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case or document not found")

    except HCS11AlreadyPaidError as e:
        raise HTTPException(status_code=409, detail=e.message)

    except HCS11ConnectionError:
        raise HTTPException(status_code=503, detail="Document verification service unavailable")

    except HCS11TimeoutError:
        raise HTTPException(status_code=504, detail="Request timed out")


# ─── Streaming Upload (for progress updates) ────────────────────────────────


@router.post(
    "/cases/{case_id}/documents/stream",
    summary="Upload documents with progress updates",
    dependencies=[Depends(require_hcs11_enabled)],
)
async def upload_documents_streaming(
    case_id: str,
    files: Annotated[list[UploadFile], File(description="Documents to upload")],
):
    """
    Upload documents with server-sent events for progress.

    Same as the regular upload, but sends progress events:
    - "validating" - Checking files locally
    - "uploading" - Sending to verification service
    - "verifying" - AI is reading documents
    - "complete" - Done, with full result
    - "error" - Something went wrong

    This helps the UI show meaningful progress during the 30-60 second
    verification process.
    """
    import json

    async def event_stream():
        try:
            # Validate files
            yield sse_event("stage", {"text": "Validating files..."})

            validated_files = []
            for file in files:
                error = validate_file(file)
                if error:
                    yield sse_event("error", {"detail": error})
                    return

                content = await file.read()
                validated_files.append((file.filename or "document", content, file.content_type))

            yield sse_event("stage", {"text": f"Uploading {len(validated_files)} document(s)..."})

            async with get_hcs11_client() as client:
                yield sse_event("stage", {"text": "Reading and verifying documents..."})

                case = await client.upload_documents(
                    case_id=case_id,
                    files=[
                        (name, ReadableBytes(content), content_type)
                        for name, content, content_type in validated_files
                    ],
                )

                result = format_upload_result(case)
                # `documents` carries the per-file verdicts, and hand-building this event
                # without them meant the streaming upload — the only one the panel uses —
                # delivered a claim HCS-11 had failed with nothing to say which file was
                # wrong. The visa stream sends the whole result; so does this one now.
                yield sse_event("complete", {
                    "status": result.status.value,
                    "title": result.title,
                    "message": result.message,
                    "case_id": result.case_id,
                    "case_status": result.case_status,
                    "documents": [vars(document) for document in result.documents],
                    "issues": result.issues,
                    "missing_documents": result.missing_documents,
                    "can_reupload": result.can_reupload,
                    "reupload_message": result.reupload_message,
                })

        except HCS11CaseNotFoundError:
            yield sse_event("error", {"detail": f"Case {case_id} not found"})

        except HCS11AlreadyPaidError as e:
            yield sse_event("error", {"detail": e.message})

        except HCS11DocumentError as e:
            yield sse_event("error", {
                "detail": format_error_message(e.error_type, e.detail, e.filename)
            })

        except HCS11ConnectionError:
            yield sse_event("error", {
                "detail": "Document verification service is not available. Please try again later."
            })

        except HCS11TimeoutError:
            yield sse_event("error", {
                "detail": "Verification is taking longer than expected. Please try again."
            })

        except Exception as e:
            logger.exception(f"Unexpected error during document upload: {e}")
            yield sse_event("error", {"detail": "An unexpected error occurred"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ─── Helpers ────────────────────────────────────────────────────────────────



