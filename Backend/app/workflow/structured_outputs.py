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
