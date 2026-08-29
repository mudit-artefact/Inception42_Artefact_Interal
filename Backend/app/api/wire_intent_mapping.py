"""
Translating the workflow's vocabulary into the labels the web interface matches on.

The interface compares `intent` against specific strings to decide what to render, so
those strings are part of the published contract even though the names used inside the
workflow have changed.
"""

from app.domain.enums import AnswerStatus, QuestionIntent

GREETING_LABEL = "greeting"
OUT_OF_SCOPE_LABEL = "not_in_scope"
AWAITING_CLARIFICATION_LABEL = "ambiguous"
ANSWERED_LABEL = "in_scope"


def wire_intent_for(
    question_intent: str | None,
    answer_status: str | None,
    is_awaiting_clarification: bool,
) -> str:
    """The label the web interface expects for this turn."""
    if is_awaiting_clarification:
        return AWAITING_CLARIFICATION_LABEL
    if question_intent == QuestionIntent.GREETING:
        return GREETING_LABEL
    if question_intent == QuestionIntent.OUT_OF_SCOPE or answer_status == AnswerStatus.REFUSED:
        return OUT_OF_SCOPE_LABEL
    return ANSWERED_LABEL
