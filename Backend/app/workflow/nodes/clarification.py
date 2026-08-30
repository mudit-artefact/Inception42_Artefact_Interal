"""
Step 2A: ask the employee something back, and wait for their reply.

The waiting is a real pause. The conversation's state is saved, the request returns, and
the conversation resumes from this exact point whenever the employee answers — even
though that arrives as a separate request, possibly much later.

Composing the question and waiting for the reply are deliberately two separate steps.
Resuming re-runs the waiting step from its beginning, so anything sitting in front of the
pause would run a second time. Keeping the model call in its own earlier step means a
resumed conversation never pays for it twice.
"""

import logging
import re

from langgraph.types import interrupt

from app.workflow.conversation_state import ConversationState
from app.workflow.language_model_client import generate_structured_output
from app.workflow.prompts import CLARIFICATION_INSTRUCTIONS
from app.workflow.structured_outputs import ClarificationQuestion

logger = logging.getLogger(__name__)


def compose_clarification_question(state: ConversationState) -> dict:
    """Write the one question worth asking back."""
    question = state["employee_question"]
    missing_information = ", ".join(state.get("missing_information") or []) or "not stated"

    clarification = generate_structured_output(
        messages=[
            {"role": "system", "content": CLARIFICATION_INSTRUCTIONS},
            {
                "role": "user",
                "content": (
                    f'The employee asked: "{question}"\n'
                    f"What is unclear: {missing_information}\n"
                    f"Reply in {state.get('requested_language', 'en')}."
                ),
            },
        ],
        output_model=ClarificationQuestion,
    )

    logger.info(f"Asking back: {clarification.clarification_question}")

    return {
        "clarification_question": clarification.clarification_question,
        "original_question": question,
        "is_awaiting_clarification": True,
    }


def wait_for_clarification(state: ConversationState) -> dict:
    """
    Pause here until the employee replies.

    This step contains nothing but the pause, on purpose — see the note at the top.
    """
    employee_reply = interrupt(
        {
            "clarification_question": state.get("clarification_question"),
            "original_question": state.get("original_question"),
        }
    )
    return {
        "employee_clarification_reply": employee_reply,
        "is_awaiting_clarification": False,
    }


# Words a question starts with, in both languages. An employee answering "which leave
# type?" says "annual leave"; one who has moved on says "can I work from home?".
OPENS_A_QUESTION = re.compile(
    r"^\s*(what|how|when|where|why|who|which|can|could|do|does|did|is|are|am|should"
    r"|would|will|may|tell|show|give|explain|summarise|summarize)\b"
    r"|^\s*(ما|ماذا|كيف|متى|أين|لماذا|من|هل|كم|أقدر|هل\s+يمكن)",
    re.IGNORECASE,
)


def _is_a_new_question_rather_than_an_answer(reply: str) -> bool:
    """
    Whether the employee has moved on instead of answering what was asked.

    A conversation that pauses to ask something treats the next message as the answer,
    whatever it is. So an employee who ignored the question and asked a different one had
    the two glued together: Omar was asked which leave type he meant, asked instead
    whether he could work from home, and was answered on both — in the wrong language.

    A reply is a reply when it is short and does not open like a question. "Annual leave"
    and "the three days from last year" answer something; "Can I work from home one day a
    week?" does not. Both halves are required, so a two-word reply that happens to start
    with "which" is still read as an answer.
    """
    reply = (reply or "").strip()
    if not reply:
        return False

    looks_like_a_question = bool(OPENS_A_QUESTION.match(reply)) or reply.endswith(("?", "؟"))
    return looks_like_a_question and len(reply.split()) >= 4


def merge_clarification_into_question(state: ConversationState) -> dict:
    """
    Fold the employee's reply back into the question and read it again.

    Re-reading matters: an employee who answers a clarification with something unrelated
    would otherwise sail past every check straight into retrieval.
    """
    original_question = state.get("original_question") or state["employee_question"]
    employee_reply = state.get("employee_clarification_reply") or ""

    if _is_a_new_question_rather_than_an_answer(employee_reply):
        # The employee moved on. Answer what they actually asked and let the abandoned
        # question go — pairing it with a question it does not answer produces a reply to
        # neither.
        logger.info(f"Reply reads as a new question; dropping the paused one: {employee_reply[:60]}")
        return {
            "employee_question": employee_reply.strip(),
            "clarification_round": state.get("clarification_round", 0) + 1,
            "is_awaiting_clarification": False,
            "clarification_question": None,
            "original_question": None,
        }

    merged_question = f"{original_question} ({employee_reply})".strip()

    logger.info(f"Merged clarification into: {merged_question[:80]}")

    return {
        "employee_question": merged_question,
        "clarification_round": state.get("clarification_round", 0) + 1,
        "is_awaiting_clarification": False,
        "clarification_question": None,
    }
