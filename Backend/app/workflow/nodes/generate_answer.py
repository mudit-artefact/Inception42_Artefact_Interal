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
            {"role": "user", "content": state["employee_question"]},
        ]
    )

    logger.info(f"Drafted an answer of {len(draft_answer)} characters ({tokens_used} tokens)")
    return {"draft_answer": draft_answer, "tokens_used": tokens_used}
