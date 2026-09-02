"""
The shapes the language model is asked to reply in.

Each one is a small, closed contract. Where a field names something the system will act
on — which employee facts to read — it is typed as an enum, so a value outside the list
is dropped before it can reach anything.
"""

from pydantic import BaseModel, Field

from app.domain.enums import HrDataField, QuestionIntent, RequiredEvidence


class QueryUnderstanding(BaseModel):
    """Step 1: what is being asked, and is enough known to answer it."""

    intent: QuestionIntent = Field(description="What the employee is trying to do")
    confidence: float = Field(description="How certain this reading is, 0 to 1", ge=0.0, le=1.0)
    needs_clarification: bool = Field(
        description="True when the question is too vague to answer without asking back"
    )
    missing_information: list[str] = Field(
        default_factory=list, description="What is missing, when clarification is needed"
    )
    needs_rewrite: bool = Field(
        description="True when the question should be reworded before searching the policies"
    )
    is_multi_question: bool = Field(
        default=False,
        description="True when the message asks about more than one distinct thing",
    )
    reasoning: str = Field(default="", description="Brief explanation for this reading")


class ClarificationQuestion(BaseModel):
    """Step 2A: what to ask the employee back."""

    clarification_question: str = Field(description="The single question to ask the employee")
    missing_information: str = Field(description="What the answer will supply")


class DecomposedQuery(BaseModel):
    """
    Step 2B: the question, reworded and split into the things it actually asks.

    One entry per distinct question. A message asking one thing yields exactly one entry,
    which is the reworded query — the same result the rewriting step used to return on
    its own.
    """

    subqueries: list[str] = Field(
        description=(
            "One standalone query per distinct thing asked, in the order asked. "
            "Exactly one entry when the message asks a single thing."
        )
    )
    reasoning: str = Field(default="", description="Brief explanation for this split")


class Calculation(BaseModel):
    """
    One figure the answer worked out, and what it worked it out from.

    This is what lets an answer say "19 days at half pay" when 19 is printed nowhere. The
    check that follows accepts a figure it can see was built out of figures that ARE
    printed, so the assistant can subtract and cannot invent: a fabricated number has no
    inputs to point at.
    """

    result: float = Field(description="The figure this produced")
    from_numbers: list[float] = Field(
        default_factory=list,
        description="Every figure from the evidence that went into it",
    )
    how: str = Field(default="", description="The sum in words, e.g. '34 - 15'")


class AnswerWithWorking(BaseModel):
    """Step 5: the reply, and any figures it had to work out to write it."""

    answer: str = Field(description="The reply the employee will read")
    calculations: list[Calculation] = Field(
        default_factory=list,
        description=(
            "One entry per figure worked out rather than copied from the evidence. "
            "Empty when every figure in the answer was quoted directly."
        ),
    )


class RephrasedAnswer(BaseModel):
    """The last reply, written again as the employee asked for it."""

    answer: str = Field(description="The previous reply, reworked as requested")
    answer_language: str = Field(
        description="The language the reply above is written in: 'en' or 'ar'"
    )


class SourceRoutingDecision(BaseModel):
    """Step 3: what this part of the question has to be answered from."""

    required_evidence: RequiredEvidence = Field(description="Where the answer must come from")
    requested_hr_data_fields: list[HrDataField] = Field(
        default_factory=list,
        description="Which of the employee's own facts are needed, from the allowed list only",
    )
    reason: str = Field(default="", description="Brief explanation for this routing")


class LeaveApplicationDraft(BaseModel):
    """Extracted parameters for an actionable leave application."""

    leave_type: str = Field(
        default="Annual leave",
        description="Leave type, e.g. 'Annual leave', 'Sick leave', 'Emergency leave', 'Unpaid leave'",
    )
    start_date: str | None = Field(default=None, description="Start date in YYYY-MM-DD format")
    end_date: str | None = Field(default=None, description="End date in YYYY-MM-DD format (inclusive)")
    days_requested: float | None = Field(
        default=None, description="Number of days requested if specified by user"
    )
    reason: str | None = Field(default=None, description="Reason or notes provided by the employee")
    is_complete: bool = Field(
        default=False, description="True if both start_date and end_date/days are known"
    )
    missing_fields: list[str] = Field(
        default_factory=list,
        description="List of missing required fields e.g. ['start_date', 'end_date']",
    )


class LeaveValidationResult(BaseModel):
    """Deterministic validation of a leave application against balances and policies."""

    is_valid: bool = Field(description="True if the request passes all policy and balance checks")
    violations: list[str] = Field(
        default_factory=list, description="Reasons for rejection if invalid"
    )
    leave_type: str = Field(description="The leave type validated")
    start_date: str = Field(description="Start date YYYY-MM-DD")
    end_date: str = Field(description="End date YYYY-MM-DD")
    working_days: int = Field(
        description="Actual working days calculated (excluding weekends and public holidays)"
    )
    balance_before: float = Field(description="Remaining balance before this request")
    balance_after: float = Field(description="Projected remaining balance if approved")
    notice_days_provided: int = Field(
        description="Working days between request date and leave start date"
    )
    notice_days_required: int = Field(
        description="Notice days required by policy clause HC-PC-001 §1.4"
    )
    notice_compliant: bool = Field(
        default=True, description="Whether notice requirement is satisfied"
    )
    requires_medical_certificate: bool = Field(
        default=False, description="Whether medical cert is required per HC-PC-002 §2.4"
    )
    approver_name: str = Field(description="Name of the manager who will approve this")


class LeaveCancellationDraft(BaseModel):
    """Parameters for cancelling a pending or future leave request."""

    request_id: int | None = Field(default=None, description="Specific leave request ID to cancel")
    leave_type: str | None = Field(
        default=None, description="Leave type to cancel if ID is not stated"
    )
    date_hint: str | None = Field(default=None, description="Date or month hint mentioned by user")

