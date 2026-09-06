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


class ChartDataPoint(BaseModel):
    """One data point in a chart."""

    label: str = Field(description="The category label (e.g., 'Annual Leave', 'January')")
    value: float = Field(description="The numeric value for this data point")
    value2: float | None = Field(
        default=None,
        description="Second value for grouped charts (e.g., 'Used' when value is 'Entitled')"
    )


class ChartData(BaseModel):
    """
    Visualization data for numeric comparisons.

    Include chart data ONLY when:
    - The numbers DIRECTLY answer the question asked
    - There are 2+ comparable numeric values forming a meaningful comparison
    - Visualization genuinely adds value beyond the text answer

    Do NOT include charts for:
    - Process/how-to questions ("How do I submit leave?")
    - Policy explanations without personal data
    - Single-value answers ("You have 12 days left")
    - Numbers mentioned incidentally but not central to the answer
    """

    chart_type: str = Field(
        description=(
            "nested_bar | horizontal_bar | grouped_bar | stacked_bar | progress | line. "
            "Use nested_bar for balance questions (Total vs Remaining as overlapping bars). "
            "Use grouped_bar for side-by-side comparison (2025 vs 2026)."
        )
    )
    title: str = Field(description="Short title (e.g., 'Leave Balance by Type')")
    data: list[ChartDataPoint] = Field(
        default_factory=list,
        description=(
            "Data points. For grouped_bar/stacked_bar: each point needs label, value (1st metric), "
            "value2 (2nd metric). E.g., for Annual Leave: label='Annual', value=24 (entitled), value2=12 (used)."
        )
    )
    series_names: list[str] = Field(
        default_factory=list,
        description=(
            "REQUIRED for grouped_bar/stacked_bar: exactly 2 names. "
            "First name = what 'value' represents, second = what 'value2' represents. "
            "E.g., ['Entitled', 'Used']"
        )
    )
    unit: str | None = Field(
        default=None,
        description="Unit label for the values (e.g., 'days', 'AED', 'employees')"
    )
    max_value: float | None = Field(
        default=None,
        description="For progress charts: the maximum/total value (e.g., 24 for '12 of 24 days')"
    )


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
    chart: ChartData | None = Field(
        default=None,
        description=(
            "Optional chart visualization when the answer contains 3+ numeric values forming "
            "a meaningful breakdown or comparison. Include ONLY when visualization adds value."
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
