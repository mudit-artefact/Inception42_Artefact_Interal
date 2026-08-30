"""Step 5: write the answer from the evidence that was gathered."""

import logging

from app.workflow.conversation_state import ConversationState
from app.workflow.language_model_client import generate_text
from app.workflow.prompts import ANSWER_INSTRUCTIONS_TEMPLATE, language_name_for

logger = logging.getLogger(__name__)


def generate_answer(state: ConversationState) -> dict:
    """
    Draft one answer covering every part of the question.

    The evidence goes in exactly as it was assembled, part by part, so the model reads
    the same text the numeric check will later hold the answer against. Building a second
    version of it here is how an answer could cite a figure the check has never seen.
    """
    requested_language = state.get("requested_language", "en")

    instructions = ANSWER_INSTRUCTIONS_TEMPLATE.format(
        language_name=language_name_for(requested_language),
        evidence=state.get("evidence_summary", ""),
    )

    draft_answer, tokens_used = generate_text(
        messages=[
            {"role": "system", "content": instructions},
            {"role": "user", "content": _what_is_being_asked(state)},
        ]
    )

    logger.info(f"Drafted an answer of {len(draft_answer)} characters ({tokens_used} tokens)")
    return {"draft_answer": draft_answer, "tokens_used": tokens_used}


def _what_is_being_asked(state: ConversationState) -> str:
    """
    The employee's own words, and what the assistant worked them out to mean.

    "okay, do the calculation" means nothing on its own. The step that resolves a
    follow-up against the conversation turns it into a standalone question, and that is
    what the search ran on — but this step used to be given the raw words alone. So the
    model was handed the evidence for a question it could not see, and asked, quite
    reasonably, which calculation.

    The employee's own words come first. The resolved form is written to search well, not
    to read well, and a reply should sound like an answer to what was actually asked.
    """
    asked = state["employee_question"]
    resolved = (state.get("retrieval_query") or "").strip()

    if not resolved or resolved == asked.strip():
        return asked
    return f'{asked}\n\n(Understood as: "{resolved}")'
