"""
Reworking the reply just given, instead of searching for it again.

"Make that shorter", "say that in Arabic", "as bullet points" are not questions about HR
policy. The answer already exists; the employee wants it presented differently. Sending
those words to the policy search finds nothing useful and produces a reply that asks them
to repeat themselves.

Nothing new is asserted here. The previous reply is the only source, and the check that
runs afterwards holds every figure in the rewrite against it — so the trail back to a
real policy extract is never broken, only one step longer. That is what makes this safe
where handing the whole conversation to the step that writes fresh answers would not be.
"""

import logging

from app.workflow.conversation_state import ConversationState
from app.workflow.language_model_client import generate_structured_output
from app.workflow.prompts import REPHRASE_INSTRUCTIONS
from app.workflow.structured_outputs import RephrasedAnswer

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = ("en", "ar")


def rephrase_previous_answer(state: ConversationState) -> dict:
    """Write the last reply again, the way the employee asked for it."""
    previous_reply = state.get("previous_reply") or {}
    previous_text = previous_reply.get("text", "")
    request = state["employee_question"]

    rewritten = generate_structured_output(
        messages=[
            {"role": "system", "content": REPHRASE_INSTRUCTIONS},
            {
                "role": "user",
                "content": (
                    f"The reply you gave was:\n\n{previous_text}\n\n"
                    f'The employee now asks: "{request}"'
                ),
            },
        ],
        output_model=RephrasedAnswer,
    )

    answer_language = _a_language_we_can_check(rewritten.answer_language, previous_reply)

    logger.info(
        f"Reworked the previous reply for '{request[:40]}' "
        f"({len(previous_text)} -> {len(rewritten.answer)} characters, {answer_language})"
    )

    return {
        "draft_answer": rewritten.answer,
        # The reply being reworked is the evidence. Every figure in the rewrite is held
        # against it, and it was itself held against real extracts when it was written.
        "checkable_evidence": previous_text,
        # Re-shown unchanged: the content is the same content, so its sources are the
        # same sources. A shorter reply cannot rest on an extract the longer one did not.
        "citations": previous_reply.get("citations", []),
        # The language the rewrite came out in, not the language the request was typed
        # in. "Say that in Arabic" is an English sentence, so without this the check at
        # the end would reject the Arabic translation for not being English.
        "requested_language": answer_language,
    }


def _a_language_we_can_check(reported: str, previous_reply: dict) -> str:
    """
    The language to hold the rewrite against.

    The model reports what it wrote in. A value outside the two languages this assistant
    speaks would make the check meaningless, so it falls back to the language the reply
    was already in — which is what an unasked-for translation would have kept.
    """
    if reported in SUPPORTED_LANGUAGES:
        return reported
    return previous_reply.get("language", "en")
