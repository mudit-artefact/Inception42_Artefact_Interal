"""
Sending employment visa documents in, for somebody who has not started yet.

A twin of the school router rather than an extension of it. The two share what a file is
and how failure is reported — those live in `document_upload_shared` — and share nothing
else, because a visa case has no dependant, no academic year and no payroll leg.

Three things HCS-11 does not offer on the visa side, and so neither does this:

- **No delete.** HCS-11 keeps only the newest document of each kind on a visa case and
  hides what it replaced, so a wrong document is corrected by sending the right one. There
  is nothing to call, and the interface must say "replace", never "remove".
- **No active-case lookup.** "Active" means "not yet paid" on a school claim; a visa case
  is never paid.
- **No health endpoint.** HCS-11 reports its health once, at `/api/hcs11/health`.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi import Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.endpoints.document_upload_shared import (
    ReadableBytes,
    require_hcs11_enabled,
    sse_event,
    validate_file,
)
from app.integrations import (
    DocumentStatus,
    HCS11CaseNotFoundError,
    HCS11ConnectionError,
    HCS11DocumentError,
    HCS11TimeoutError,
    HCS11ValidationError,
    UploadStatus,
    format_error_message,
    get_hcs11_client,
)
from app.integrations.hcs11_response_formatter import UploadResult
from app.integrations.hcs11_schemas import VisaCaseOut
from app.services.document_notifications import (
    VISA_DOCUMENTS_CHECKED,
    tell_them_the_contract_is_signed,
    tell_them_what_came_back,
)
from app.integrations.visa_response_formatter import (
    build_visa_document_statuses,
    format_visa_upload_result,
    settle_the_contract,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/visa", tags=["Employment Visa Documents"])

# What the notification's button says to the assistant. The same imperative sentence
# the home page's action card uses, so both open the same window.
UPLOAD_VISA_DOCUMENTS = "I want to upload my visa documents"


class VisaCaseListResponse(BaseModel):
    cases: list[VisaCaseOut]
    count: int


class VisaCaseDetailResponse(BaseModel):
    """A case, with its checklist already worked out."""
    case: VisaCaseOut
    documents: list[DocumentStatus]


class VisaUploadResponse(BaseModel):
    """
    What to show after documents have been read.

    The same shape as the school upload's answer minus the two payment fields, so a
    browser can render either with one component.
    """
    status: UploadStatus
    title: str
    message: str
    documents: list[DocumentStatus]
    issues: list[str] = []
    missing_documents: list[str] = []
    can_reupload: bool = False
    reupload_message: str | None = None
    case_id: str | None = None
    case_status: str | None = None


@router.get(
    "/cases",
    response_model=VisaCaseListResponse,
    summary="The visa cases open for one new joiner",
    dependencies=[Depends(require_hcs11_enabled)],
)
async def list_cases(employee_id: Annotated[str, Query()]) -> VisaCaseListResponse:
    try:
        async with get_hcs11_client() as client:
            # Each case read in full, not as HCS-11 lists it. Its listing returns
            # `problems` as an empty list whatever the case holds — so a screen built on
            # the listing shows a case under review with nothing wrong with it, and a
            # timeline built on it finds no step for the employee to act on and reports
            # that everything on their side is done. Only the per-case reading carries
            # what was actually found.
            summaries = await client.list_visa_cases(employee_id)
            cases = [settle_the_contract(await client.get_visa_case(case.case_id))
                     for case in summaries]
            return VisaCaseListResponse(cases=cases, count=len(cases))
    except HCS11ConnectionError:
        raise HTTPException(
            status_code=503,
            detail=format_error_message("connection", "Service unavailable"),
        )
    except HCS11TimeoutError as e:
        raise HTTPException(status_code=504, detail=format_error_message("timeout", e.message))


@router.get(
    "/cases/{case_id}",
    response_model=VisaCaseDetailResponse,
    summary="One visa case, with its checklist",
    dependencies=[Depends(require_hcs11_enabled)],
)
async def get_case(case_id: str) -> VisaCaseDetailResponse:
    try:
        async with get_hcs11_client() as client:
            case = settle_the_contract(await client.get_visa_case(case_id))
            # Derived here rather than in the browser: what is received is a set-difference
            # against `missing_documents`, and each fault is filed against the document its
            # own `about` names.
            return VisaCaseDetailResponse(
                case=case, documents=build_visa_document_statuses(case)
            )
    except HCS11CaseNotFoundError:
        raise HTTPException(status_code=404, detail=f"Visa case {case_id} not found")
    except HCS11ConnectionError:
        raise HTTPException(
            status_code=503,
            detail=format_error_message("connection", "Service unavailable"),
        )
    except HCS11TimeoutError as e:
        raise HTTPException(status_code=504, detail=format_error_message("timeout", e.message))


# ── The employment contract ──────────────────────────────────────────────────
#
# The one document on a visa case that goes towards the new joiner instead of away from
# them. It is not a fourth process and gets no router of its own: HCS-11 keeps it as a
# field on the visa case, and giving it a separate address on this side would be a second
# vocabulary for the same thing.
#
# Signing it files the signed copy as the job-offer document, so the answer below is the
# whole refreshed case rather than the contract alone — the checklist, the checks and the
# status have all moved.


@router.get(
    "/cases/{case_id}/contract",
    summary="The employment contract, as a PDF",
    dependencies=[Depends(require_hcs11_enabled)],
    response_class=Response,
)
async def get_contract(case_id: str) -> Response:
    """
    The contract itself, passed through as the file HCS-11 draws.

    Proxied rather than linked to directly so the browser talks to one origin, and so the
    feature flag and the error wording apply here as they do everywhere else. Sent
    `inline`, because this is opened to be read rather than saved.
    """
    try:
        async with get_hcs11_client() as client:
            payload, content_type, filename = await client.read_contract_pdf(case_id)
            return Response(
                content=payload,
                media_type=content_type,
                headers={"content-disposition": f'inline; filename="{filename}"'},
            )
    except HCS11CaseNotFoundError:
        raise HTTPException(status_code=404, detail=f"Visa case {case_id} not found")
    except HCS11ConnectionError:
        raise HTTPException(
            status_code=503,
            detail=format_error_message("connection", "Service unavailable"),
        )
    except HCS11TimeoutError as e:
        raise HTTPException(status_code=504, detail=format_error_message("timeout", e.message))


@router.post(
    "/cases/{case_id}/contract/sign",
    response_model=VisaCaseDetailResponse,
    summary="Accept the employment contract",
    dependencies=[Depends(require_hcs11_enabled)],
)
async def sign_contract(case_id: str) -> VisaCaseDetailResponse:
    """
    Sign it, and answer with the case as it now stands.

    The same shape `GET /cases/{case_id}` returns, so a screen can replace what it holds
    rather than reconciling a contract against a case it fetched earlier.

    **409 has two meanings and they are opposites**: already signed, or too early — HCS-11
    refuses until the documents have been checked. Neither is an error, and each carries
    HCS-11's own sentence, which is passed through rather than replaced. Deciding here that
    a 409 meant "already signed" told a joiner who had signed nothing the opposite.
    """
    try:
        async with get_hcs11_client() as client:
            case = settle_the_contract(await client.sign_contract(case_id))
            # Only ever reached once per case: a second attempt is refused upstream with a
            # 409, so this cannot write the same notification twice.
            tell_them_the_contract_is_signed(case.employee_id, case.case_id)
            return VisaCaseDetailResponse(
                case=case, documents=build_visa_document_statuses(case)
            )
    except HCS11CaseNotFoundError:
        raise HTTPException(status_code=404, detail=f"Visa case {case_id} not found")
    except HCS11ValidationError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except HCS11ConnectionError:
        raise HTTPException(
            status_code=503,
            detail=format_error_message("connection", "Service unavailable"),
        )
    except HCS11TimeoutError as e:
        raise HTTPException(status_code=504, detail=format_error_message("timeout", e.message))


async def _read_and_check(files: list[UploadFile]) -> list[tuple[str, bytes, str]]:
    """Every file read into memory once, refusing anything obviously unusable."""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    ready: list[tuple[str, bytes, str]] = []
    for file in files:
        error = validate_file(file)
        if error:
            raise HTTPException(status_code=422, detail=error)
        content = await file.read()
        await file.seek(0)
        if not content:
            raise HTTPException(
                status_code=422,
                detail=f"'{file.filename}' is empty. Please choose the file again.",
            )
        ready.append((file.filename or "document", content, file.content_type or ""))
    return ready


def _as_response(case: VisaCaseOut, result: UploadResult | None = None) -> VisaUploadResponse:
    # The verdict is passed in where the caller has already worked it out to decide whether
    # to notify. Formatting it a second time would give the same answer and is simply work;
    # it stays optional so nothing else that calls this has to care.
    result = result or format_visa_upload_result(case)
    return VisaUploadResponse(
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
    )


@router.post(
    "/cases/{case_id}/documents",
    response_model=VisaUploadResponse,
    summary="Send visa documents in",
    dependencies=[Depends(require_hcs11_enabled)],
)
async def upload_documents(
    case_id: str,
    files: Annotated[list[UploadFile], File(description="PDF, PNG or JPEG")],
) -> VisaUploadResponse:
    """
    Send one or more documents, and get back what HCS-11 made of them.

    Sending a document of a kind already on the case replaces it. That is how a fault is
    corrected here, because HCS-11 offers no way to remove one.
    """
    ready = await _read_and_check(files)

    try:
        async with get_hcs11_client() as client:
            case = await client.upload_documents(
                case_id=case_id,
                files=[(name, ReadableBytes(body), kind) for name, body, kind in ready],
                process="visa",
            )
            verdict = format_visa_upload_result(case)
            tell_them_what_came_back(
                verdict,
                case.employee_id,
                VISA_DOCUMENTS_CHECKED,
                UPLOAD_VISA_DOCUMENTS,
            )
            return _as_response(case, verdict)

    except HCS11CaseNotFoundError:
        raise HTTPException(status_code=404, detail=f"Visa case {case_id} not found")
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
        raise HTTPException(status_code=504, detail=format_error_message("timeout", e.message))


@router.post(
    "/cases/{case_id}/documents/stream",
    summary="Send visa documents in, reporting progress as it goes",
    dependencies=[Depends(require_hcs11_enabled)],
)
async def upload_documents_streaming(
    case_id: str,
    files: Annotated[list[UploadFile], File(description="PDF, PNG or JPEG")],
) -> StreamingResponse:
    """
    The same upload, with progress.

    Reading a document takes HCS-11 the better part of a minute, and a browser showing
    nothing for that long looks broken. Three events: `stage` while it works, then either
    `complete` carrying the full answer or `error` carrying a sentence.
    """
    ready = await _read_and_check(files)

    async def progress():
        yield sse_event("stage", {"text": f"Sending {len(ready)} document(s)…"})
        try:
            async with get_hcs11_client() as client:
                yield sse_event("stage", {"text": "Reading and checking your documents…"})
                case = await client.upload_documents(
                    case_id=case_id,
                    files=[(name, ReadableBytes(body), kind) for name, body, kind in ready],
                    process="visa",
                )
            # Hooked here as well as on the plain endpoint above, and this is the one
            # that matters: the browser posts to this route and never to that one, so a
            # notification written only there would pass every test and never once fire.
            verdict = format_visa_upload_result(case)
            tell_them_what_came_back(
                verdict,
                case.employee_id,
                VISA_DOCUMENTS_CHECKED,
                UPLOAD_VISA_DOCUMENTS,
            )
            # Every field the plain endpoint returns, so a browser reading this stream is
            # not left rendering half a result. The school stream omits its checklist and
            # its own client then hardcodes an empty one; this does not repeat that.
            yield sse_event("complete", _as_response(case, verdict).model_dump())

        except HCS11CaseNotFoundError:
            yield sse_event("error", {"detail": f"Visa case {case_id} not found"})
        except HCS11DocumentError as e:
            yield sse_event(
                "error", {"detail": format_error_message(e.error_type, e.detail, e.filename)}
            )
        except HCS11ValidationError as e:
            yield sse_event("error", {"detail": e.detail})
        except HCS11ConnectionError:
            yield sse_event(
                "error", {"detail": format_error_message("connection", "Service unavailable")}
            )
        except HCS11TimeoutError as e:
            yield sse_event("error", {"detail": format_error_message("timeout", e.message)})
        except Exception:
            logger.exception(f"Sending visa documents to case {case_id} failed")
            yield sse_event("error", {"detail": "Something went wrong. Please try again."})

    return StreamingResponse(
        progress(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
