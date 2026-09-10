"""
Telling somebody what came back, after they sent a document in.

The bell has only ever carried leave, all of it written from `leave_service`. That leaves a
new joiner's bell structurally empty — they cannot apply for leave at all (HC-PC-013
§13.2.2) — while the one thing they most need to hear about, a document returned with a
fault, is shown once in a panel and gone the moment they close it.

Three rules shape everything here.

**The wording is HCS-11's, not ours.** `format_visa_upload_result` and its school twin
already produce the title and sentence the panel shows. Those exact strings become the
notification. Writing a second description of the same fault is how two screens come to
disagree about it, which has already had to be fixed twice on the document surfaces.

**"Still waiting" is not news.** Sending two documents of four produces a real verdict, and
it says what the panel and the joining board both already say. A bell entry per file would
be three copies of "still waiting on some documents" and then the one that mattered.

**It is best-effort, loudly.** A notification that cannot be written must never turn a
successful upload into an error. It is caught and logged, which does mean a broken
notification is invisible in the running system — so the failures worth catching are caught
before the write instead, chiefly the recipient not existing.
"""

import logging
from typing import Any

from app.database.engine import SessionLocal
from app.database.tables import Employee
from app.integrations.hcs11_client import map_hcs11_to_hcs01_employee_id
from app.integrations.hcs11_response_formatter import UploadResult, UploadStatus
from app.services.notification_service import create_notification

logger = logging.getLogger(__name__)


# The verdicts worth a bell entry: something came back wrong, everything was accepted, or
# the case has moved on to somebody else. `INCOMPLETE` is the one deliberately absent —
# it means "you have sent some of them", which is true, unhelpful, and already on screen
# in two other places.
#
# `ALREADY_PAID` and `ERROR` are unreachable here: the first is raised as a 409 before any
# case exists to read, and the second is not a verdict HCS-11 returns.
WORTH_TELLING_THEM = {
    UploadStatus.SUCCESS,
    UploadStatus.PARTIAL,
    UploadStatus.NEEDS_REUPLOAD,
    UploadStatus.NEEDS_REVIEW,
    UploadStatus.REJECTED,
}

VISA_DOCUMENTS_CHECKED = "VISA_DOCUMENTS_CHECKED"
SCHOOL_DOCUMENTS_CHECKED = "SCHOOL_DOCUMENTS_CHECKED"
CONTRACT_SIGNED = "CONTRACT_SIGNED"


def tell_them_what_came_back(
    verdict: UploadResult,
    hcs11_employee_id: str,
    event_type: str,
    prompt: str,
) -> None:
    """
    Put a document verdict in the employee's bell, if it is one worth putting there.

    `prompt` is what the notification's button says to the assistant — the same imperative
    sentences the action cards use, so the button opens the window the employee expects
    rather than starting a conversation about it.
    """
    if verdict.status not in WORTH_TELLING_THEM:
        logger.info(
            f"Not telling {hcs11_employee_id} about a {verdict.status.value} verdict: "
            f"there is nothing in it they cannot already see"
        )
        return

    # The specific sentence first, the general one after.
    #
    # Two reasons. The panel's message says "send a corrected copy of the document below",
    # which means the checklist when there is a checklist under it and nothing at all in a
    # bell — so the sentence that names the papers has to be there too. And the bell clamps
    # a message to two lines, so whichever half comes second is the half that gets cut:
    # appended, the naming sentence was written, delivered, and then hidden.
    message = verdict.message
    if verdict.reupload_message:
        message = f"{verdict.reupload_message} {verdict.message}"

    _write_it(
        hcs11_employee_id=hcs11_employee_id,
        event_type=event_type,
        title=verdict.title,
        message=message,
        prompt=prompt,
        extra={
            "case_id": verdict.case_id,
            "case_status": verdict.case_status,
            "verdict": verdict.status.value,
            "problems": verdict.issues,
            "still_to_send": verdict.missing_documents,
        },
    )


def tell_them_the_contract_is_signed(hcs11_employee_id: str, case_id: str) -> None:
    """
    The one notification with wording of its own.

    Signing answers with a case rather than an upload verdict, so there is no title or
    message to reuse — and none of the four the formatter can produce mentions a contract.
    Reusing one would have said "still waiting on some documents", which is true of the
    case and not an answer to what just happened.
    """
    _write_it(
        hcs11_employee_id=hcs11_employee_id,
        event_type=CONTRACT_SIGNED,
        title="Contract signed",
        message=(
            "Your employment contract has been signed and filed with your visa documents "
            "as your signed job-offer form. There is nothing further to send for it."
        ),
        prompt="I want to sign my contract",
        extra={"case_id": case_id},
    )


def _write_it(
    hcs11_employee_id: str,
    event_type: str,
    title: str,
    message: str,
    prompt: str,
    extra: dict[str, Any],
) -> None:
    """
    Address it and write it, or say in the log why it could not be.

    No session is passed to `create_notification` on purpose, and it matters most for the
    two streaming endpoints: a `Depends`-provided session is closed before a
    `StreamingResponse` body is consumed, so one handed in here would already be shut by
    the time the notification is written. Letting it open its own is the only shape that
    works in all five places, so all five use it.
    """
    recipient = map_hcs11_to_hcs01_employee_id(hcs11_employee_id or "").upper()
    if not recipient:
        logger.warning(f"No employee on the case, so {event_type} was not sent to anybody")
        return

    # The recipient column is declared a foreign key and nothing enforces it — SQLite does
    # not check foreign keys unless asked, and nothing here asks. So a wrong id writes
    # cleanly, logs success, and turns up in nobody's bell. Look them up first; a warning
    # is worth more than a row nobody will ever read.
    session = SessionLocal()
    try:
        known = session.query(Employee).filter(Employee.user_id == recipient).first()
    finally:
        session.close()

    if known is None:
        logger.warning(
            f"{event_type} not sent: {hcs11_employee_id} maps to {recipient}, "
            f"who is not in our employee records"
        )
        return

    try:
        create_notification(
            recipient_id=recipient,
            # No sender. HCS-11 read the documents, and there is no employee row standing
            # for it — the leave notifications name a person because a person decided.
            sender_id=None,
            event_type=event_type,
            title=title,
            message=message,
            action_payload={"prompt": prompt, **extra},
        )
        logger.info(f"Told {recipient} about {event_type}")
    except Exception as could_not_tell_them:
        # Best-effort by design: the documents are safely with HCS-11 either way, and
        # failing the upload over a notification would lose the thing that mattered.
        logger.warning(f"Could not put {event_type} in {recipient}'s bell: {could_not_tell_them}")
