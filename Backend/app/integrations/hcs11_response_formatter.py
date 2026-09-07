"""
Converts HCS-11 API responses into user-friendly chat messages.

The HCS-11 backend returns technical verification results. This module
translates them into clear, actionable messages for employees.
"""

from dataclasses import dataclass, field
from enum import Enum

from .hcs11_schemas import CaseDetail, EmployeeIssueOut, RequiredDocumentOut


class UploadStatus(str, Enum):
    """Overall status of an upload attempt."""
    SUCCESS = "success"
    PARTIAL = "partial"
    NEEDS_REUPLOAD = "needs_reupload"
    NEEDS_REVIEW = "needs_review"
    INCOMPLETE = "incomplete"
    ALREADY_PAID = "already_paid"
    ERROR = "error"


@dataclass
class DocumentStatus:
    """Status of a single document."""
    kind: str
    label: str
    filename: str | None
    received: bool
    has_issues: bool = False
    issue_message: str | None = None


@dataclass
class UploadResult:
    """
    Complete result of a document upload, ready for display in chat.

    This is what the chatbot frontend receives and renders.
    """
    status: UploadStatus
    title: str
    message: str
    documents: list[DocumentStatus] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    missing_documents: list[str] = field(default_factory=list)
    can_reupload: bool = False
    reupload_message: str | None = None
    case_id: str | None = None
    case_status: str | None = None
    payment_amount: float | None = None
    payment_status: str | None = None


def format_upload_result(case: CaseDetail) -> UploadResult:
    """
    Convert an HCS-11 CaseDetail into a chat-friendly UploadResult.

    Analyzes the case status, documents, issues, and verification results
    to produce a clear message with actionable next steps.
    """
    documents = _build_document_statuses(case)
    issues = _extract_issues(case)
    missing = case.missing_documents

    status = _determine_status(case, issues, missing)
    title, message = _build_message(case, status, issues, missing)
    can_reupload, reupload_message = _build_reupload_prompt(case, issues, missing)

    return UploadResult(
        status=status,
        title=title,
        message=message,
        documents=documents,
        issues=issues,
        missing_documents=missing,
        can_reupload=can_reupload,
        reupload_message=reupload_message,
        case_id=case.case_id,
        case_status=case.case_status,
        payment_amount=case.schooling_aed or case.paid_aed,
        payment_status=case.payment_status,
    )


def _build_document_statuses(case: CaseDetail) -> list[DocumentStatus]:
    """Build status list for each required document."""
    statuses = []

    doc_issues = {
        issue.kind: issue.what_to_do
        for issue in case.employee_issues
    }

    for req in case.required_documents:
        has_issue = req.kind in doc_issues
        statuses.append(DocumentStatus(
            kind=req.kind,
            label=req.label,
            filename=req.file_name,
            received=req.received,
            has_issues=has_issue,
            issue_message=doc_issues.get(req.kind),
        ))

    return statuses


def _extract_issues(case: CaseDetail) -> list[str]:
    """Extract user-facing issue messages."""
    messages = []

    for issue in case.employee_issues:
        messages.append(f"{issue.title}: {issue.what_to_do}")

    for check in case.match_checks:
        if check.result == "fail":
            messages.append(_format_match_failure(check))

    return messages


def _format_match_failure(check) -> str:
    """Convert a matching check failure into a readable message."""
    code = check.code

    if "name" in code.lower():
        return (
            f"Name mismatch: The document shows '{check.document_value}' "
            f"but your HR record has '{check.master_value}'. "
            "Please upload a document with the correct name."
        )

    if "date" in code.lower() or "year" in code.lower():
        return (
            f"Date issue: The document shows '{check.document_value}' "
            f"but we expected '{check.master_value}'. "
            "Please check the document dates."
        )

    if "school" in code.lower():
        return (
            f"School mismatch: The documents reference different schools. "
            f"Please ensure all documents are from the same school."
        )

    return check.detail


def _determine_status(
    case: CaseDetail,
    issues: list[str],
    missing: list[str],
) -> UploadStatus:
    """Determine the overall status based on case state."""

    if case.payment_status in ("Sent", "Paid"):
        return UploadStatus.ALREADY_PAID

    if case.route == "approve" or case.case_status == "Approved":
        return UploadStatus.SUCCESS

    if case.route == "review" or case.awaiting_review:
        return UploadStatus.NEEDS_REVIEW

    if missing:
        return UploadStatus.INCOMPLETE

    if issues:
        return UploadStatus.NEEDS_REUPLOAD

    if case.case_status == "Under Review":
        return UploadStatus.NEEDS_REVIEW

    return UploadStatus.PARTIAL


def _build_message(
    case: CaseDetail,
    status: UploadStatus,
    issues: list[str],
    missing: list[str],
) -> tuple[str, str]:
    """Build title and message based on status."""

    if status == UploadStatus.SUCCESS:
        amount = case.schooling_aed or case.paid_aed or 0
        return (
            "Documents Verified Successfully!",
            f"All documents for {case.dependent_name} have been verified. "
            f"Your claim for AED {amount:,.0f} is approved and will be "
            f"processed in the next payroll cycle."
        )

    if status == UploadStatus.ALREADY_PAID:
        return (
            "Claim Already Processed",
            f"This claim for {case.dependent_name} was already sent to payroll. "
            "Documents cannot be replaced. If you need to make changes, "
            "please contact HC Services."
        )

    if status == UploadStatus.NEEDS_REVIEW:
        return (
            "Documents Received - Under Review",
            f"Your documents for {case.dependent_name} have been received "
            f"but require review by HC Services. You'll be notified once "
            f"the review is complete. Reference: {case.case_id}"
        )

    if status == UploadStatus.INCOMPLETE:
        missing_str = ", ".join(missing)
        return (
            "Documents Missing",
            f"Your submission for {case.dependent_name} is incomplete. "
            f"Still needed: {missing_str}. Please upload the missing documents."
        )

    if status == UploadStatus.NEEDS_REUPLOAD:
        return (
            "Documents Need Attention",
            f"Some documents for {case.dependent_name} have issues that "
            "need to be fixed. Please review the problems below and "
            "upload corrected documents."
        )

    return (
        "Documents Received",
        f"Your documents for {case.dependent_name} are being processed."
    )


def _build_reupload_prompt(
    case: CaseDetail,
    issues: list[str],
    missing: list[str],
) -> tuple[bool, str | None]:
    """Build the reupload prompt if documents need to be fixed."""

    needs_reupload = bool(issues) or bool(missing)

    if not needs_reupload:
        return False, None

    lines = ["To complete your submission, please upload:"]

    for doc in case.required_documents:
        if not doc.received:
            lines.append(f"• {doc.label} (not yet received)")

    for issue in case.employee_issues:
        lines.append(f"• {_get_label_for_kind(issue.kind, case.required_documents)} ({issue.title.lower()})")

    return True, "\n".join(lines)


def _get_label_for_kind(kind: str, required_docs: list[RequiredDocumentOut]) -> str:
    """Get the display label for a document kind."""
    for doc in required_docs:
        if doc.kind == kind:
            return doc.label
    return kind.replace("_", " ").title()


def format_case_status_message(case: CaseDetail) -> str:
    """
    Format a case status for display when user asks about their submission.

    Used when employee asks "what's the status of my documents?"
    """
    dependent = case.dependent_name
    status = case.case_status

    if case.payment_status == "Sent":
        amount = case.paid_aed or case.schooling_aed or 0
        return (
            f"Your claim for {dependent} has been approved and sent to payroll. "
            f"Amount: AED {amount:,.0f}."
        )

    if case.payment_status == "Paid":
        amount = case.paid_aed or case.schooling_aed or 0
        return (
            f"Your claim for {dependent} has been paid. Amount: AED {amount:,.0f}."
        )

    if status == "Approved":
        amount = case.schooling_aed or 0
        return (
            f"Your claim for {dependent} is approved for AED {amount:,.0f}. "
            "It will be included in the next payroll batch."
        )

    if status == "Under Review" and case.awaiting_review:
        return (
            f"Your documents for {dependent} are being reviewed by HC Services. "
            f"Reference: {case.case_id}"
        )

    if case.missing_documents:
        missing = ", ".join(case.missing_documents)
        return (
            f"Your submission for {dependent} is incomplete. "
            f"Still needed: {missing}."
        )

    if case.employee_issues:
        issue_count = len(case.employee_issues)
        return (
            f"Your submission for {dependent} has {issue_count} issue(s) "
            "that need your attention. Would you like to see the details?"
        )

    if status == "Awaiting Submission":
        return (
            f"You haven't submitted documents for {dependent} yet. "
            f"Deadline: {case.submission_deadline}."
        )

    return f"Your claim for {dependent} is currently: {status}."


def format_error_message(error_type: str, detail: str, filename: str | None = None) -> str:
    """
    Format a technical error into a user-friendly message.

    Used when an upload fails before reaching HCS-11's verification.
    """
    if error_type == "too_large":
        return (
            f"The file '{filename}' is too large. "
            "Maximum file size is 10MB. Please compress or re-scan the document."
        )

    if error_type == "unsupported_type":
        return (
            f"The file '{filename}' is not a supported format. "
            "Please upload PDF, PNG, or JPEG files only."
        )

    if error_type == "empty":
        return (
            f"The file '{filename}' appears to be empty. "
            "Please check the file and try again."
        )

    if error_type == "connection":
        return (
            "The document verification service is temporarily unavailable. "
            "Please try again in a few minutes."
        )

    if error_type == "timeout":
        return (
            "Document verification is taking longer than expected. "
            "Please try again in a few minutes. Your documents were not lost."
        )

    return f"An error occurred: {detail}"
