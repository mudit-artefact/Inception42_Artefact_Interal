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

import pytest

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


# ── nothing HCS-11 found may fall out on the way to the screen ────────────────
#
# The panel used to decide for itself which document each finding belonged against, from
# a hand-written list of HCS-11's problem kinds and check codes. The list named two kinds
# HCS-11 has never sent and missed six it does, and had no branch for anything unlisted:
# a problem it did not recognise was attached to no document, counted in no total, and
# drawn as a green tick. Measured across the twenty demo claims, thirty-one problems were
# being hidden and five claims told the employee "Everything we need is here" while
# HCS-11 was asking for better copies.
#
# These tests are the reason it cannot come back. Every kind HCS-11 emits is named here,
# and so is the rule that an unrecognised one must still be shown.

# Every problem kind in hcs-11's app/services/employee_feedback.py. If they add one, the
# last test in this block is what should fail — noisily, here, rather than silently on a
# screen an employee is reading.
EVERY_PROBLEM_KIND_HCS11_SENDS = [
    "unreadable",       # a required detail could not be read
    "wrong_kind",       # not one of the four documents
    "wrong_child",      # the invoice is for a different child
    "wrong_reference",  # the receipt settles a different bill
    "wrong_signer",     # the declaration was signed by somebody else
    "wrong_year",       # the documents are for different school years
    "wrong_school",     # the certificate and the invoice are from different schools
]


def a_problem(kind: str, about=CERTIFICATE) -> dict:
    return {
        "kind": kind,
        "title": f"Something is wrong ({kind})",
        "what_to_do": "Please send another copy.",
        "documents": [about],
        "document_ids": [],
    }


@pytest.mark.parametrize("kind", EVERY_PROBLEM_KIND_HCS11_SENDS)
def test_every_problem_kind_reaches_the_document_it_is_about(kind):
    result = format_upload_result(a_case(employee_issues=[a_problem(kind)]))

    certificate = next(d for d in result.documents if d.filename == CERTIFICATE)
    assert certificate.has_issues, f"a {kind!r} problem was not shown against the file"
    assert kind in certificate.issue_message


def test_a_problem_kind_nobody_has_seen_before_is_still_shown():
    """
    The rule that makes the others redundant.

    The old panel matched a problem's kind against a fixed list and dropped anything
    absent. Nothing here reads the kind at all — HCS-11 says which file a problem is
    about, and that is the only thing consulted.
    """
    result = format_upload_result(
        a_case(employee_issues=[a_problem("a_kind_invented_next_year")])
    )

    certificate = next(d for d in result.documents if d.filename == CERTIFICATE)
    assert certificate.has_issues


def test_a_failing_check_is_shown_even_with_no_issue_written_for_it():
    """
    `employee_issues` is HCS-11's plain-English list, and it does not cover every check.
    Reading only that list meant a failing check with no prose written for it was
    attached to nothing. `match_checks` carries the rest, each naming its document.
    """
    result = format_upload_result(a_case(
        employee_issues=[],
        documents=[{"document_id": "DOC-2", "file_name": INVOICE, "uploaded_at": "2026-09-01"}],
        match_checks=[{
            "code": "INVOICE_IS_SAME_CHILD",
            "result": "fail",
            "detail": "The invoice names a different child.",
            "document_id": "DOC-2",
        }],
    ))

    invoice = next(d for d in result.documents if d.filename == INVOICE)
    assert invoice.has_issues
    assert "different child" in invoice.issue_message


@pytest.mark.parametrize("result_value", ["fail", "review", "missing"])
def test_a_check_that_did_not_pass_is_not_treated_as_one_that_did(result_value):
    """
    Only `fail` used to count. A check HCS-11 could not complete, or sent for review, is
    not a check that passed — and "review" is what it returns for a name spelled
    differently and for a scan it could not read confidently, which are the two commonest
    things wrong with a real claim.
    """
    result = format_upload_result(a_case(
        employee_issues=[],
        match_checks=[{
            "code": "DEPENDENT_NAME",
            "result": result_value,
            "detail": "The name does not match the HR record.",
            "document_id": "DOC-1",
        }],
    ))

    certificate = next(d for d in result.documents if d.filename == CERTIFICATE)
    assert certificate.has_issues, f"a {result_value!r} check was read as a pass"


def test_a_passing_check_says_nothing():
    """The other direction: the fix must not start warning about claims that are fine."""
    result = format_upload_result(a_case(
        employee_issues=[],
        match_checks=[
            {"code": "DEPENDENT_NAME", "result": "pass", "detail": "Matches.",
             "document_id": "DOC-1"},
            {"code": "SAME_SCHOOL", "result": "not_comparable",
             "detail": "Different alphabets, so not compared.", "document_id": "DOC-1"},
        ],
    ))

    assert not any(document.has_issues for document in result.documents)
    assert result.issues == []


def test_a_failed_eligibility_rule_is_not_lost():
    """
    The rules are about the claim, not about one file, so they have no row to sit against
    and were shown nowhere at all. The claim-level list is the floor beneath the rows.
    """
    result = format_upload_result(a_case(
        employee_issues=[],
        rule_results=[{
            "code": "ACADEMIC_YEAR",
            "result": "fail",
            "detail": "The invoice is for the 2025-2026 academic year.",
            "inputs": {},
        }],
    ))

    assert any("2025-2026" in problem for problem in result.issues)


def test_a_problem_belonging_to_no_file_still_reaches_the_employee():
    """
    A finding HCS-11 could not pin to one document must not vanish for want of a home.
    """
    result = format_upload_result(a_case(
        employee_issues=[],
        documents=[],
        match_checks=[{
            "code": "SAME_ACADEMIC_YEAR",
            "result": "fail",
            "detail": "Your documents are for different school years.",
            "document_id": None,
        }],
    ))

    assert not any(document.has_issues for document in result.documents)
    assert any("different school years" in problem for problem in result.issues)


def test_hcs11s_own_wording_is_not_rewritten_into_something_untrue():
    """
    A cross-document check compares one document against another. Its two values were
    being printed as "the document shows X but your HR record has Y", and the HR record
    had nothing to do with it. HCS-11 sends the real labels for exactly this reason.
    """
    result = format_upload_result(a_case(
        employee_issues=[],
        match_checks=[{
            "code": "SAME_SCHOOL",
            "result": "fail",
            "detail": "The certificate and the invoice are from different schools.",
            "document_value": "Al Noor School",
            "master_value": "Green Valley School",
            "document_label": "On the invoice",
            "master_label": "On the certificate",
            "document_id": "DOC-1",
        }],
    ))

    said = " ".join(result.issues)
    assert "On the invoice" in said and "On the certificate" in said
    assert "HR record" not in said


def test_a_check_waiting_on_a_document_that_has_not_arrived_is_not_a_complaint():
    """
    The other half of "missing".

    A cross-document check on a half-sent claim reports `missing` because there was
    nothing yet to compare against — "There is no declaration to check this against",
    beside a checklist row already reading "waiting". Printed as problems these bury the
    real ones, and a screen full of noise is skimmed exactly like a screen full of green.
    """
    result = format_upload_result(a_case(
        employee_issues=[],
        missing_documents=["employee_declaration"],
        match_checks=[{
            "code": "DECLARATION_IS_THIS_EMPLOYEE",
            "result": "missing",
            "detail": "There is no declaration to check this against.",
            "document_id": None,
        }],
    ))

    assert result.issues == []
    assert not any(document.has_issues for document in result.documents)


def test_a_real_problem_is_still_shown_on_a_half_sent_claim():
    """The guard above must not become a second hiding place."""
    result = format_upload_result(a_case(
        employee_issues=[],
        missing_documents=["employee_declaration"],
        match_checks=[{
            "code": "DEPENDENT_NAME",
            "result": "fail",
            "detail": "The certificate names a different child.",
            "document_id": "DOC-1",
        }],
    ))

    certificate = next(d for d in result.documents if d.filename == CERTIFICATE)
    assert certificate.has_issues
    assert "different child" in certificate.issue_message


def test_the_open_claim_is_read_the_same_way_as_any_other():
    """
    `/active-case` filled two of its response's five fields, so `documents`, `problems`
    and `everything_is_settled` came back empty on every call — it reported "nothing
    wrong" whatever HCS-11 had decided. It was the one endpoint missed when the panel was
    fixed, and harmless only because nothing called it yet. Both routes now build the
    response through the same function.
    """
    from app.api.endpoints.hcs11_documents import _as_case_detail

    reading = _as_case_detail(a_case(recommendation="request_documents"))

    assert reading.everything_is_settled is False
    assert any(document.has_issues for document in reading.documents), (
        "a claim HCS-11 sent back must not read as a clean one"
    )


def test_a_settled_claim_reads_as_settled():
    from app.api.endpoints.hcs11_documents import _as_case_detail

    reading = _as_case_detail(
        a_case(route="approve", recommendation="approve", case_status="Approved",
               employee_issues=[])
    )

    assert reading.everything_is_settled is True
    assert not any(document.has_issues for document in reading.documents)
