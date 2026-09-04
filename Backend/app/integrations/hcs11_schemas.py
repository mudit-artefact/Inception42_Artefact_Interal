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
    """One matching check result."""
    code: str
    result: str
    document_value: str | None = None
    master_value: str | None = None
    detail: str


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
