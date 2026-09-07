"""
What HCS-11 decided is what the employee is told.

HCS-11 answers an upload with HTTP 200 and the finished claim, whatever it decided — a
rejection is in the body, not in the status code. And it has only two routes, approve and
review, so three different outcomes arrive as "review":

    rules passed         -> route "approve", recommendation "approve"
    rules FAILED         -> route "review",  recommendation "reject"
    paperwork is poor    -> route "review",  recommendation "request_documents"
    judgement call       -> route "review",  recommendation None

Reading only the route collapsed the last three into "received, under review". A claim the
rules had rejected was reported to the employee as a successful submission awaiting
routine review, with nothing to say anything was wrong or that they had to do something.
"""

from app.integrations.hcs11_response_formatter import UploadStatus, format_upload_result
from app.integrations.hcs11_schemas import CaseDetail

CERTIFICATE = "1-certificate.pdf"
INVOICE = "2-invoice.pdf"


def a_case(**overrides) -> CaseDetail:
    """A claim with four documents in, and one problem on the certificate."""
    body = {
        "case_id": "CASE0002",
        "employee_id": "EMP001",
        "employee_name": "Alia Al Suwaidi",
        "dependent_id": "DEP001",
        "dependent_name": "Fatima Al Suwaidi",
        "academic_year": "2026-2027",
        "cycle_id": "AC2026-27",
        "benefit_plan_name": "Education Allowance – Enhanced",
        "submission_deadline": "2026-10-31",
        "case_status": "Under Review",
        "payment_status": "Not Sent",
        "route": "review",
        "documents": [
            {"document_id": "DOC-1", "file_name": CERTIFICATE, "uploaded_at": "2026-09-01"},
            {"document_id": "DOC-2", "file_name": INVOICE, "uploaded_at": "2026-09-01"},
        ],
        "required_documents": [
            {"kind": "enrolment_certificate", "label": "Enrolment certificate",
             "received": True, "file_name": CERTIFICATE},
            {"kind": "school_invoice", "label": "Itemised school invoice",
             "received": True, "file_name": INVOICE},
        ],
        "employee_issues": [
            {
                "kind": "unreadable",
                "title": "Your enrolment certificate does not show a date of birth",
                "what_to_do": "Please send a copy that does.",
                "documents": [CERTIFICATE],
                "document_ids": ["DOC-1"],
            }
        ],
    }
    body.update(overrides)
    return CaseDetail(**body)


def test_a_rejected_claim_is_not_reported_as_under_review():
    """The one that shipped: a rejection read as a normal submission."""
    result = format_upload_result(a_case(recommendation="reject", rules_outcome="fail"))

    assert result.status == UploadStatus.REJECTED
    assert "under review" not in result.message.lower()
    assert "not been approved" in result.message.lower()


def test_a_claim_needing_better_paperwork_asks_for_it():
    result = format_upload_result(a_case(recommendation="request_documents"))

    assert result.status == UploadStatus.NEEDS_REUPLOAD
    assert result.can_reupload


def test_a_genuine_judgement_call_is_still_a_review():
    """No recommendation means a person has to decide, and that is what we say."""
    result = format_upload_result(a_case(recommendation=None, awaiting_review=True))

    assert result.status == UploadStatus.NEEDS_REVIEW


def test_a_passing_claim_is_still_approved():
    result = format_upload_result(
        a_case(route="approve", recommendation="approve", case_status="Approved",
               employee_issues=[], schooling_aed=25000)
    )

    assert result.status == UploadStatus.SUCCESS


def test_the_problem_is_shown_against_the_file_it_is_about():
    """
    Problems used to be matched to files by `kind`. An issue's kind says what went wrong
    ("unreadable"); a checklist row's kind says which document it is
    ("enrolment_certificate"). They never matched, so no problem was ever shown beside a
    file — HCS-11 sends the filename and the document id precisely so that it can be.
    """
    result = format_upload_result(a_case(recommendation="request_documents"))

    flagged = {document.filename for document in result.documents if document.has_issues}
    assert flagged == {CERTIFICATE}, "only the certificate has a problem"

    certificate = next(d for d in result.documents if d.filename == CERTIFICATE)
    assert "date of birth" in certificate.issue_message

    invoice = next(d for d in result.documents if d.filename == INVOICE)
    assert invoice.issue_message is None


def test_the_reupload_list_names_the_document_not_the_fault():
    """It used to read "Unreadable (…)" — the fault where the document should be."""
    result = format_upload_result(a_case(recommendation="request_documents"))

    assert "Enrolment certificate" in result.reupload_message
    assert "Unreadable" not in result.reupload_message
