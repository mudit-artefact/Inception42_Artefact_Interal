"""
"I sent my documents. What happened?"

The bell has only ever carried leave. A new joiner cannot apply for leave at all
(HC-PC-013 §13.2.2), so their bell was structurally empty — while the one thing they most
need to hear about, a document returned with a fault, was shown once in a panel and lost
the moment they closed it.

Two rules are worth pinning here rather than trusting.

**"Still waiting" is not news.** Sending two documents of four is a real verdict that says
what the panel and the joining board both already say. Notifying on it would put three
copies of "still waiting on some documents" in front of somebody before the one that
mattered.

**A notification that cannot be written must not lose the upload.** The documents are with
HCS-11 either way, and failing the request over a bell entry would throw away the thing
that actually happened.
"""

import pytest

from app.integrations.hcs11_response_formatter import UploadResult, UploadStatus
from app.services import document_notifications
from app.services.document_notifications import (
    CONTRACT_SIGNED,
    VISA_DOCUMENTS_CHECKED,
    tell_them_the_contract_is_signed,
    tell_them_what_came_back,
)
from app.services.notification_service import list_employee_notifications


def a_verdict(status: UploadStatus, **overrides) -> UploadResult:
    """What the formatters hand back, with HCS-11's own wording on it."""
    fields = {
        "status": status,
        "title": "One document needs replacing",
        "message": "Send a corrected copy of the document below.",
        "issues": ["The photograph cannot be used: the background is blue."],
        "missing_documents": [],
        "case_id": "VISA0001",
        "case_status": "Under Review",
        "reupload_message": "Please send a corrected copy of: Recent colour photograph.",
    }
    fields.update(overrides)
    return UploadResult(**fields)


def bell(employee_id: str = "EMP013") -> list[dict]:
    return list_employee_notifications(employee_id=employee_id)


# ── what reaches the bell ───────────────────────────────────────────────────

def test_a_returned_document_reaches_the_bell(temporary_database):
    tell_them_what_came_back(
        a_verdict(UploadStatus.NEEDS_REUPLOAD), "E0013", VISA_DOCUMENTS_CHECKED, "go"
    )

    [told] = bell()
    assert told["event_type"] == VISA_DOCUMENTS_CHECKED
    assert told["is_read"] is False


def test_the_bell_uses_hcs11s_own_words(temporary_database):
    """
    Not a second description of the same fault.

    The panel and the bell reading differently about one document is how two screens come
    to disagree, which has already had to be fixed twice on these surfaces.
    """
    verdict = a_verdict(UploadStatus.NEEDS_REUPLOAD)
    tell_them_what_came_back(verdict, "E0013", VISA_DOCUMENTS_CHECKED, "go")

    [told] = bell()
    assert told["title"] == verdict.title
    assert verdict.message in told["message"]


def test_the_bell_names_the_document_first(temporary_database):
    """
    "Send a corrected copy of the document below" means the checklist, in a panel.

    In a bell there is no below, so the sentence naming the paper has to be there — and it
    has to be *first*, because the bell clamps a message to two lines. Appended, it was
    written, delivered and then cut off the bottom of the card.
    """
    tell_them_what_came_back(
        a_verdict(UploadStatus.NEEDS_REUPLOAD), "E0013", VISA_DOCUMENTS_CHECKED, "go"
    )

    [told] = bell()
    assert "Recent colour photograph" in told["message"]
    assert told["message"].index("Recent colour photograph") < told["message"].index(
        "the document below"
    )


def test_everything_accepted_reaches_the_bell_too(temporary_database):
    """A receipt, not only bad news."""
    tell_them_what_came_back(
        a_verdict(UploadStatus.SUCCESS, title="Everything we need is here"),
        "E0013",
        VISA_DOCUMENTS_CHECKED,
        "go",
    )

    assert bell()[0]["title"] == "Everything we need is here"


def test_the_button_carries_what_to_say_to_the_assistant(temporary_database):
    tell_them_what_came_back(
        a_verdict(UploadStatus.NEEDS_REUPLOAD),
        "E0013",
        VISA_DOCUMENTS_CHECKED,
        "I want to upload my visa documents",
    )

    assert bell()[0]["action_payload"]["prompt"] == "I want to upload my visa documents"


# ── what deliberately does not ──────────────────────────────────────────────

def test_a_partial_upload_says_nothing(temporary_database):
    """
    The rule this file mostly exists for.

    "You have sent two of four" is true, and it is already on the panel and on the joining
    board. A bell entry per file sent would bury the one that mattered.
    """
    tell_them_what_came_back(
        a_verdict(UploadStatus.INCOMPLETE, missing_documents=["passport", "photograph"]),
        "E0013",
        VISA_DOCUMENTS_CHECKED,
        "go",
    )

    assert bell() == []


def test_somebody_we_do_not_have_gets_nothing_written(temporary_database, caplog):
    """
    The recipient column is a foreign key that nothing enforces.

    SQLite does not check foreign keys unless asked and nothing asks, so a wrong id writes
    cleanly, logs success and turns up in nobody's bell. Refusing early makes that visible.
    """
    tell_them_what_came_back(
        a_verdict(UploadStatus.NEEDS_REUPLOAD), "E9999", VISA_DOCUMENTS_CHECKED, "go"
    )

    assert bell("EMP999") == []
    assert "not in our employee records" in caplog.text


def test_a_case_belonging_to_nobody_is_not_written(temporary_database):
    tell_them_what_came_back(
        a_verdict(UploadStatus.NEEDS_REUPLOAD), "", VISA_DOCUMENTS_CHECKED, "go"
    )

    assert bell() == []


def test_a_failure_to_notify_does_not_raise(temporary_database, monkeypatch, caplog):
    """
    Best-effort, deliberately.

    The documents are with HCS-11 whatever happens here, and failing the upload over a
    bell entry would throw away the part that mattered.
    """
    def refuses(**_):
        raise RuntimeError("the database went away")

    monkeypatch.setattr(document_notifications, "create_notification", refuses)

    tell_them_what_came_back(
        a_verdict(UploadStatus.NEEDS_REUPLOAD), "E0013", VISA_DOCUMENTS_CHECKED, "go"
    )

    assert "Could not put" in caplog.text


# ── the contract ────────────────────────────────────────────────────────────

def test_signing_the_contract_reaches_the_bell(temporary_database):
    tell_them_the_contract_is_signed("E0013", "VISA0001")

    [told] = bell()
    assert told["event_type"] == CONTRACT_SIGNED
    assert told["title"] == "Contract signed"


def test_the_contract_notification_says_contract(temporary_database):
    """
    Signing answers with a case, not a verdict, so there is no title to reuse.

    Reusing one anyway would have said "still waiting on some documents" — true of the
    case, and no answer at all to what just happened.
    """
    tell_them_the_contract_is_signed("E0013", "VISA0001")

    said = bell()[0]["message"].lower()
    assert "contract" in said
    assert "still waiting" not in said


@pytest.mark.parametrize("their_id, ours", [("E0013", "EMP013"), ("E0001", "EMP001")])
def test_the_notification_is_addressed_in_our_vocabulary(temporary_database, their_id, ours):
    """HCS-11 says whose case it is in its own ids; our employee table uses ours."""
    tell_them_the_contract_is_signed(their_id, "VISA0001")

    assert bell(ours)[0]["recipient_id"] == ours
