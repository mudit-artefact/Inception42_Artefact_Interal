"""
What a new joiner is told after sending their visa documents in.

The school twin of this formatter rebuilds, in the browser, which document each fault
belongs to — from three tables copied out of HCS-11's internals. None of that happens here.
A visa check carries `about`, naming the document kinds it concerns, so a fault is filed
against the row HCS-11 says it belongs to.

The thing that must be derived rather than read is the checklist. A school row arrives as
an object with its own `received` flag; a visa case sends `required_documents` as plain
kind strings and says separately which are still `missing`. Getting that set-difference
backwards would tell somebody a document had arrived when it had not.
"""

import pytest

from app.integrations.hcs11_schemas import VisaCaseOut
from app.integrations.hcs11_response_formatter import UploadStatus
from app.integrations.visa_response_formatter import (
    build_visa_document_statuses,
    format_visa_upload_result,
)

PASSPORT = "1-passport--Daniel-Okonkwo.pdf"
PHOTOGRAPH = "2-photograph--Daniel-Okonkwo.jpg"
OFFER = "3-offer--Daniel-Okonkwo.pdf"

# The exact sentence HCS-11 returns for the photograph-on-blue scenario.
BLUE_BACKGROUND = "The photograph cannot be used: the background is blue, not white."


def a_visa_case(**overrides) -> VisaCaseOut:
    """Daniel's case: the route that needs no academic certificate."""
    body = {
        "case_id": "VISA0003",
        "employee_id": "E0015",
        "employee_name": "Daniel Okonkwo",
        "plan_code": "VISA_STANDARD",
        "plan_name": "Employment visa — no degree required",
        "case_status": "Awaiting Submission",
        "submission_deadline": "2026-10-07",
        "required_documents": ["passport", "photograph", "job_offer"],
        "missing_documents": ["passport", "photograph", "job_offer"],
        "documents": [],
        "checks": [],
        "problems": [],
    }
    body.update(overrides)
    return VisaCaseOut(**body)


def everything_sent(**overrides) -> VisaCaseOut:
    filed = {
        "missing_documents": [],
        "documents": [
            {"document_id": "D1", "file_name": PASSPORT, "kind": "passport",
             "kind_label": "Passport copy", "uploaded_at": "2026-09-08T10:00:00+00:00"},
            {"document_id": "D2", "file_name": PHOTOGRAPH, "kind": "photograph",
             "kind_label": "Photograph", "uploaded_at": "2026-09-08T10:00:00+00:00"},
            {"document_id": "D3", "file_name": OFFER, "kind": "job_offer",
             "kind_label": "Signed job-offer form", "uploaded_at": "2026-09-08T10:00:00+00:00"},
        ],
    }
    filed.update(overrides)
    return a_visa_case(**filed)


def row(case, kind):
    return next(r for r in build_visa_document_statuses(case) if r.kind == kind)


# ── the checklist is derived, not read ───────────────────────────────────────


def test_a_kind_still_missing_has_not_been_received():
    assert row(a_visa_case(), "passport").received is False


def test_a_kind_absent_from_missing_has_arrived_and_names_its_file():
    sent = row(everything_sent(), "passport")

    assert sent.received is True
    assert sent.filename == PASSPORT


def test_the_route_decides_the_rows_not_the_policy():
    """
    Daniel needs three documents. A checklist showing four has been built from the
    policy's first table rather than from his own case.
    """
    kinds = [r.kind for r in build_visa_document_statuses(a_visa_case())]

    assert kinds == ["passport", "photograph", "job_offer"]
    assert "academic_certificate" not in kinds


def test_the_degree_route_does_show_the_certificate():
    ahmed = a_visa_case(
        required_documents=["passport", "photograph", "job_offer", "academic_certificate"],
        missing_documents=["academic_certificate"],
    )

    assert "academic_certificate" in [r.kind for r in build_visa_document_statuses(ahmed)]


def test_a_document_of_a_kind_the_route_does_not_need_adds_no_row():
    """The route is the list. An extra file does not extend it."""
    stray = everything_sent(
        documents=[
            {"document_id": "D9", "file_name": "something.pdf", "kind": "academic_certificate",
             "kind_label": "Attested academic certificate", "uploaded_at": "2026-09-08T10:00:00+00:00"},
        ],
    )

    assert [r.kind for r in build_visa_document_statuses(stray)] == [
        "passport", "photograph", "job_offer"
    ]


# ── a fault lands on the document it is about ────────────────────────────────


def test_a_failed_check_is_shown_against_the_document_it_names():
    case = everything_sent(
        checks=[
            {"code": "PHOTOGRAPH_USABLE", "result": "fail", "detail": BLUE_BACKGROUND,
             "about": ["photograph"]},
            {"code": "PASSPORT_VALIDITY", "result": "pass", "detail": "Valid until 2031.",
             "about": ["passport"]},
        ],
        problems=[BLUE_BACKGROUND],
    )

    assert row(case, "photograph").has_issues is True
    assert row(case, "photograph").issue_message == BLUE_BACKGROUND
    assert row(case, "passport").has_issues is False
    assert row(case, "passport").issue_message is None


def test_a_check_that_passed_is_not_reported_as_a_fault():
    case = everything_sent(
        checks=[{"code": "PHOTOGRAPH_USABLE", "result": "pass", "detail": "Fine.",
                 "about": ["photograph"]}],
    )

    assert row(case, "photograph").has_issues is False


def test_a_fault_about_two_documents_is_shown_against_both():
    """SAME_PERSON names every document it compared."""
    case = everything_sent(
        checks=[{"code": "SAME_PERSON", "result": "fail",
                 "detail": "The passport and the offer name different people.",
                 "about": ["passport", "job_offer"]}],
    )

    assert row(case, "passport").has_issues is True
    assert row(case, "job_offer").has_issues is True
    assert row(case, "photograph").has_issues is False


def test_the_employee_is_told_hcs11s_own_sentence():
    """Not a second description of the same fault written here."""
    case = everything_sent(
        checks=[{"code": "PHOTOGRAPH_USABLE", "result": "fail", "detail": BLUE_BACKGROUND,
                 "about": ["photograph"]}],
        problems=[BLUE_BACKGROUND],
    )

    assert BLUE_BACKGROUND in format_visa_upload_result(case).issues


def test_a_check_code_is_never_shown_in_place_of_a_sentence():
    """A code is HCS-11 talking to itself. It only appears if there is no sentence at all."""
    case = everything_sent(
        checks=[{"code": "PHOTOGRAPH_USABLE", "result": "fail", "detail": BLUE_BACKGROUND,
                 "about": ["photograph"]}],
    )

    assert "PHOTOGRAPH_USABLE" not in (row(case, "photograph").issue_message or "")


# ── what the whole result says ───────────────────────────────────────────────


def test_still_missing_documents_reads_as_incomplete_not_as_a_fault():
    result = format_visa_upload_result(a_visa_case())

    assert result.status is UploadStatus.INCOMPLETE
    assert "Passport copy" in " ".join(result.missing_documents)


def test_a_fault_outranks_a_missing_document():
    """
    Sending the last document will not help if one already sent is wrong, so that is what
    the employee is told about first.
    """
    case = a_visa_case(
        missing_documents=["job_offer"],
        checks=[{"code": "PHOTOGRAPH_USABLE", "result": "fail", "detail": BLUE_BACKGROUND,
                 "about": ["photograph"]}],
        problems=[BLUE_BACKGROUND],
    )

    assert format_visa_upload_result(case).status is UploadStatus.NEEDS_REUPLOAD


def test_a_complete_clean_case_is_a_success():
    result = format_visa_upload_result(
        everything_sent(case_status="Ready for the PRO", route="ready")
    )

    assert result.status is UploadStatus.SUCCESS
    assert "nothing further" in result.message.lower()


def test_the_reupload_prompt_names_documents_not_faults():
    """
    The school twin got this wrong once and asked an employee to re-send "Unreadable".
    Somebody is being asked for a piece of paper, so the list must be of paper.
    """
    case = everything_sent(
        checks=[{"code": "PHOTOGRAPH_USABLE", "result": "fail", "detail": BLUE_BACKGROUND,
                 "about": ["photograph"]}],
        problems=[BLUE_BACKGROUND],
    )

    prompt = format_visa_upload_result(case).reupload_message

    assert "Photograph" in prompt
    assert "background" not in prompt


def test_the_wording_never_offers_to_remove_a_document():
    """
    HCS-11 has no way to delete a visa document — it keeps the newest of each kind. An
    interface that offered removal would be offering something that cannot happen.
    """
    case = everything_sent(
        checks=[{"code": "PHOTOGRAPH_USABLE", "result": "fail", "detail": BLUE_BACKGROUND,
                 "about": ["photograph"]}],
        problems=[BLUE_BACKGROUND],
    )
    result = format_visa_upload_result(case)
    everything_said = " ".join([result.title, result.message, result.reupload_message or ""])

    assert "remove" not in everything_said.lower()
    assert "replac" in everything_said.lower()


def test_a_visa_case_reports_no_payment():
    """It is never paid. The fields stay empty rather than reading zero."""
    result = format_visa_upload_result(everything_sent())

    assert result.payment_amount is None
    assert result.payment_status is None


@pytest.mark.parametrize("count,expected", [(1, "One document needs"), (2, "Some documents need")])
def test_the_heading_counts_correctly(count, expected):
    faults = ["passport", "photograph"][:count]
    case = everything_sent(
        checks=[{"code": f"CHECK_{k}", "result": "fail", "detail": f"{k} is wrong.",
                 "about": [k]} for k in faults],
        problems=[f"{k} is wrong." for k in faults],
    )

    assert format_visa_upload_result(case).title.startswith(expected)
