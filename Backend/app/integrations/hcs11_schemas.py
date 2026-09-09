"""
Pydantic models matching HCS-11 API responses.

These mirror the schemas in hcs-11-verification/backend/app/api/schemas/responses.py,
but only include fields the chatbot needs. The full extraction details, rule checks,
and audit logs stay on the HCS-11 side.
"""

from pydantic import BaseModel


class DocumentOut(BaseModel):
    """One document in a claim."""
    document_id: str
    file_name: str
    kind: str | None = None
    kind_label: str | None = None
    uploaded_at: str


class RequiredDocumentOut(BaseModel):
    """One row of the document checklist."""
    kind: str
    label: str
    received: bool
    file_name: str | None = None


class EmployeeIssueOut(BaseModel):
    """
    One problem the employee can fix.

    These are safe to show directly — anything requiring reviewer judgement
    is filtered out by HCS-11 before it reaches this list.
    """
    kind: str
    title: str
    what_to_do: str
    # Which files the problem is about. HCS-11 sends both, and says why in its own
    # comment: the ids are "for a caller that shows the message against the upload
    # itself", because names are not unique on a claim — a replaced file keeps the name
    # it was sent under. We are that caller, and both fields used to be dropped here,
    # so a problem with one certificate could only ever be shown as a note about the
    # claim as a whole.
    documents: list[str] = []
    document_ids: list[str] = []


class ExtractedField(BaseModel):
    """One value read from a document."""
    key: str
    label: str
    value: str | None = None
    flagged: bool = False
    mandatory: bool = False


class ExtractionOut(BaseModel):
    """What was read from a document."""
    document_language: str
    overall_confidence: float
    confidence_threshold: float
    below_threshold: bool
    fields: list[ExtractedField] = []
    missing_mandatory: list[str] = []


class CheckOut(BaseModel):
    """
    One matching check result.

    `document_id` is the document to show the check against, and HCS-11 works it out per
    claim rather than reading it off the stored row — every row it stores carries the
    certificate's id, whatever the check compared. Reading the stored one put "your
    declaration is signed by somebody else" beside the certificate; this field is the
    answer to that, and it is the reason no lookup table is needed on our side.

    `result` is one of pass, fail, review, missing, not_comparable. Only `pass` and
    `not_comparable` mean there is nothing to tell the employee.
    """
    code: str
    result: str
    document_value: str | None = None
    master_value: str | None = None
    detail: str
    document_id: str | None = None
    # What the two values above actually are. A cross-document check compares one document
    # against another, and both sides were being labelled "on the document" and "in the HR
    # record" — the second of which is simply untrue when the comparison was invoice
    # against certificate. HCS-11 sends the real labels; we used to drop them.
    document_label: str | None = None
    master_label: str | None = None


class RuleOut(BaseModel):
    """One eligibility rule result."""
    code: str
    result: str
    detail: str
    inputs: dict[str, str | None] = {}


class CaseSummary(BaseModel):
    """Summary of a verification case, for listing."""
    case_id: str
    employee_id: str
    employee_name: str
    dependent_id: str
    dependent_name: str
    academic_year: str
    cycle_id: str
    benefit_plan_name: str
    submission_deadline: str
    submitted_on: str | None = None
    case_status: str
    matching_outcome: str | None = None
    rules_outcome: str | None = None
    route: str | None = None
    recommendation: str | None = None
    assigned_reviewer: str | None = None
    invoiced_aed: float | None = None
    schooling_aed: float | None = None
    paid_aed: float | None = None
    approved_on: str | None = None
    approved_by: str | None = None
    payment_status: str
    reminder_count: int = 0
    document_name: str | None = None
    awaiting_review: bool = False


class CaseDetail(CaseSummary):
    """
    Full details of a verification case.

    Extends CaseSummary with documents, issues, and verification results.
    """
    documents: list[DocumentOut] = []
    required_documents: list[RequiredDocumentOut] = []
    missing_documents: list[str] = []
    employee_issues: list[EmployeeIssueOut] = []
    match_checks: list[CheckOut] = []
    rule_results: list[RuleOut] = []
    unresolved: list[RuleOut] = []


class HealthResponse(BaseModel):
    """HCS-11 health check response."""
    status: str
    employees: int
    cases: int
    open_cycle: str
    extraction_model: str
    confidence_threshold: float


# ── The visa side ────────────────────────────────────────────────────────────
#
# A separate set, not an extension of the school ones. Six of CaseSummary's fields are
# required and have no visa counterpart — dependent, academic year, cycle, benefit plan,
# payment status — so CaseSummary(**visa_json) raises rather than degrading.
#
# The difference that shapes everything downstream: a school checklist row arrives as an
# object carrying its own `received` flag, while a visa case sends `required_documents`
# without one and says separately which kinds are still `missing`. The checklist is
# therefore derived here rather than read. See `visa_response_formatter`.


class VisaRequiredDocumentOut(BaseModel):
    """
    One row of the checklist, and what HCS-11 calls it.

    These used to be bare kind strings and we kept our own map of kinds to names. HCS-11
    now sends the label with the kind, and says why in its own comment: so that a screen
    does not keep a second copy of the names. It was right — a fifth kind arrived
    (`residence_visa`, for somebody already in the country changing employer) and every
    private copy of that list was silently one short.

    Read `label`. The map in `evidence_formatting` is a fallback for nothing else.
    """
    kind: str
    label: str = ""


class VisaReadField(BaseModel):
    """One value read off a visa document — a passport number, a signature date."""
    key: str
    label: str
    value: str | None = None
    mandatory: bool = False


class VisaDocumentOut(BaseModel):
    """One document on a visa case."""
    document_id: str
    file_name: str
    kind: str | None = None
    kind_label: str | None = None
    uploaded_at: str
    stored: bool = False
    fields: list[VisaReadField] = []


class VisaCheckOut(BaseModel):
    """
    One check HCS-11 ran, and what it concluded.

    `about` is the field the school side lacks and the reason the visa panel needs no
    lookup tables: HCS-11 names the document kinds each check concerns, so a failure can be
    shown against the row it belongs to instead of being reconstructed in the browser from
    a copy of HCS-11's internals.
    """
    code: str
    result: str
    detail: str | None = None
    document_value: str | None = None
    master_value: str | None = None
    about: list[str] = []


class VisaCaseOut(BaseModel):
    """
    A new joiner's employment visa case.

    `problems` arrives already computed — HCS-11 builds it as the detail sentence of every
    check that failed — so what an employee is told about a fault is HCS-11's own wording,
    not a second description of it written here.
    """
    case_id: str
    process: str = "visa"
    employee_id: str
    employee_name: str
    job_title: str | None = None
    plan_code: str | None = None
    plan_name: str | None = None
    case_status: str
    outcome: str | None = None
    route: str | None = None
    submission_deadline: str | None = None
    submitted_on: str | None = None
    required_documents: list[VisaRequiredDocumentOut] = []
    # Kinds, not labels — this list names rows in the one above rather than repeating them.
    missing_documents: list[str] = []
    documents: list[VisaDocumentOut] = []
    checks: list[VisaCheckOut] = []
    problems: list[str] = []
