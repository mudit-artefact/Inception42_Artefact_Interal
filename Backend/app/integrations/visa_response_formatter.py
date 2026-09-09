"""
Turning a visa case from HCS-11 into something a new joiner can read.

The school twin of this file rebuilds, in the browser, which document each fault belongs
to — from three lookup tables copied out of HCS-11's internals. None of that is needed
here. A visa check carries `about`, naming the document kinds it concerns, and HCS-11
computes `problems` as the detail sentence of every check that failed. So a fault is shown
against the row HCS-11 says it belongs to, in HCS-11's own words.

The one thing that must be derived rather than read is the checklist itself. A school
checklist row arrives as an object with its own `received` flag; a visa case sends
`required_documents` as plain kind strings and says separately which are still `missing`.
So `received` is a set-difference, the filename is joined back through the uploaded
documents by kind, and the human label comes from the map the answer path already uses.

That join is safe here and was not on the school side: HCS-11 keeps only the newest
document per kind on a visa case and hides what it replaced, so kind is unique.
"""

import logging

from app.integrations.hcs11_response_formatter import (
    DocumentStatus,
    UploadResult,
    UploadStatus,
)
from app.integrations.hcs11_schemas import VisaCaseOut
from app.workflow.evidence_formatting import VISA_DOCUMENT_NAMES

logger = logging.getLogger(__name__)

# HCS-11 says a check failed with "fail"; anything else it ran is not a fault to show.
FAILED = "fail"

# The two states a visa case has. There is no payment leg.
READY = "Ready for the PRO"


def format_visa_upload_result(case: VisaCaseOut) -> UploadResult:
    """What to show a new joiner after their documents have been read."""
    documents = build_visa_document_statuses(case)
    problems = list(case.problems) or _problems_from_checks(case)
    status = _determine_visa_status(case, problems)

    title, message = _visa_message(case, status, problems)

    return UploadResult(
        status=status,
        title=title,
        message=message,
        documents=documents,
        issues=problems,
        missing_documents=names_for(case, case.missing_documents),
        can_reupload=status in (UploadStatus.NEEDS_REUPLOAD, UploadStatus.INCOMPLETE),
        reupload_message=_what_to_send_again(documents),
        case_id=case.case_id,
        case_status=case.case_status,
        # A visa case is never paid; the fields stay empty rather than reading zero.
        payment_amount=None,
        payment_status=None,
    )


def build_visa_document_statuses(case: VisaCaseOut) -> list[DocumentStatus]:
    """
    One row per document the route requires, in the order HCS-11 lists them.

    `received` is derived: a kind absent from `missing_documents` has arrived. HCS-11 does
    not send a per-row flag on a visa case, and inventing one from `documents` alone would
    call a file received that HCS-11 had rejected outright.
    """
    outstanding = set(case.missing_documents)
    filed = {document.kind: document for document in case.documents if document.kind}
    faults = _faults_by_kind(case)

    rows: list[DocumentStatus] = []
    for required in case.required_documents:
        document = filed.get(required.kind)
        problems = faults.get(required.kind, [])
        rows.append(
            DocumentStatus(
                kind=required.kind,
                label=required.label or _name_for(required.kind, document),
                filename=document.file_name if document else None,
                received=required.kind not in outstanding,
                has_issues=bool(problems),
                # HCS-11's own sentence, not a second description of the same fault.
                issue_message=" ".join(problems) if problems else None,
            )
        )
    return rows


def names_for(case: VisaCaseOut, kinds) -> list[str]:
    """
    Kinds written the way HCS-11 writes them, for a list that names rows of the checklist.

    `missing_documents` arrives as kinds. Translating them through a map kept here is what
    broke when a fifth kind appeared: the map had four, so a missing residence visa was
    listed under its raw code. The case already carries the labels, so use those and fall
    back only for a kind that is not on this route's checklist at all.
    """
    labels = {row.kind: row.label for row in case.required_documents if row.label}
    return [labels.get(kind) or _name_for(kind) for kind in kinds]


def _faults_by_kind(case: VisaCaseOut) -> dict[str, list[str]]:
    """
    Each failed check filed against the document kinds it names.

    This is the whole reason the visa panel needs no lookup tables: `about` comes from
    HCS-11, so a fault lands on the row it belongs to rather than on one worked out here.
    """
    faults: dict[str, list[str]] = {}
    for check in case.checks:
        if check.result != FAILED:
            continue
        for kind in check.about:
            faults.setdefault(kind, []).append(check.detail or check.code)
    return faults


def _problems_from_checks(case: VisaCaseOut) -> list[str]:
    """
    The fallback for `problems`.

    HCS-11 computes that list itself, and this says the same thing the same way if a
    future case ever arrives without it. It is not a second opinion.
    """
    return [check.detail or check.code for check in case.checks if check.result == FAILED]


def _name_for(kind: str, document: object | None = None) -> str:
    """
    What HCS-11 calls this kind of paper when it is talking to a person.

    Its own label wins. The fallback map is written for the middle of a sentence — "your
    passport copy and photograph" — so its first letter is raised for a checklist row,
    where the two would otherwise sit side by side in different cases.
    """
    label = getattr(document, "kind_label", None)
    if label:
        return label
    written_for_prose = VISA_DOCUMENT_NAMES.get(kind, kind.replace("_", " "))
    return written_for_prose[:1].upper() + written_for_prose[1:]


def _determine_visa_status(case: VisaCaseOut, problems: list[str]) -> UploadStatus:
    """
    Which of the shared statuses this case is in.

    Order matters, and it is the order a new joiner cares about: something to fix beats
    something missing, because sending the last document will not help if one already sent
    is wrong.
    """
    if problems:
        return UploadStatus.NEEDS_REUPLOAD
    if case.missing_documents:
        return UploadStatus.INCOMPLETE
    if case.route == "ready" or case.case_status == READY:
        return UploadStatus.SUCCESS
    return UploadStatus.NEEDS_REVIEW


def _visa_message(
    case: VisaCaseOut, status: UploadStatus, problems: list[str]
) -> tuple[str, str]:
    """The heading and the sentence under it."""
    if status is UploadStatus.SUCCESS:
        return (
            "Everything we need is here",
            "All of your documents have been accepted and your case has gone to the "
            "public relations officer to lodge. There is nothing further for you to do.",
        )

    if status is UploadStatus.NEEDS_REUPLOAD:
        one = "One document needs" if len(problems) == 1 else "Some documents need"
        return (
            f"{one} replacing",
            "Send a corrected copy of the document below and your case will be checked "
            "again. Sending it again replaces what is there — nothing needs removing "
            "first.",
        )

    if status is UploadStatus.INCOMPLETE:
        outstanding = [_name_for(kind) for kind in case.missing_documents]
        return (
            "Still waiting on some documents",
            "Your case is not assessed until everything the route needs has arrived. "
            f"Still to send: {', '.join(outstanding)}.",
        )

    return (
        "With HC Services",
        "Your documents have arrived and are being looked at. There is nothing further "
        "for you to do at the moment.",
    )


def _what_to_send_again(documents: list[DocumentStatus]) -> str | None:
    """
    Which papers to send again, named as papers rather than as faults.

    The school twin got this wrong once and told an employee to re-send "Unreadable". A
    person is being asked for a document, so the list has to be of documents.
    """
    faulty = [row.label for row in documents if row.has_issues]
    if not faulty:
        return None
    return f"Please send a corrected copy of: {', '.join(faulty)}."
