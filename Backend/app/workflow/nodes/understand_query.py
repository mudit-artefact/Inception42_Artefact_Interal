"""Step 1: work out what is being asked, and whether enough is known to answer."""

import logging

from app.domain.enums import QuestionIntent
from app.workflow.conversation_memory import describe_the_conversation_so_far
from app.workflow.conversation_state import ConversationState
from app.workflow.language_model_client import generate_structured_output
from app.workflow.prompts import QUERY_UNDERSTANDING_INSTRUCTIONS
from app.workflow.structured_outputs import QueryUnderstanding

logger = logging.getLogger(__name__)


def understand_query(state: ConversationState) -> dict:
    """
    Read the employee's question.

    A failure here raises. It used to be caught and turned into "this is an in-scope
    question, confidence 0.5", which meant an unreachable model produced a system that
    looked healthy while routing every question — including ones it should refuse —
    straight into retrieval.
    """
    question = state["employee_question"]
    understanding = generate_structured_output(
        messages=[
            {"role": "system", "content": QUERY_UNDERSTANDING_INSTRUCTIONS},
            {"role": "user", "content": _describe_the_turn(state)},
        ],
        output_model=QueryUnderstanding,
    )

    # A greeting or an out-of-scope question is answered directly, so there is never
    # anything to clarify about it.
    needs_clarification = understanding.needs_clarification and (
        understanding.intent == QuestionIntent.HR_QUESTION
    )

    # Only a real question can ask two things. A greeting reading as multi-question
    # would send "hello, how are you?" through splitting and retrieval.
    is_multi_question = understanding.is_multi_question and (
        understanding.intent == QuestionIntent.HR_QUESTION
    )

    logger.info(
        f"Understood '{question[:50]}' as {understanding.intent} "
        f"(confidence {understanding.confidence:.2f}, clarify={needs_clarification}, "
        f"multi={is_multi_question})"
    )

    return {
        "question_intent": understanding.intent.value,
        "intent_confidence": understanding.confidence,
        "needs_clarification": needs_clarification,
        "needs_rewrite": understanding.needs_rewrite,
        "is_multi_question": is_multi_question,
        "missing_information": understanding.missing_information,
    }


def _describe_the_turn(state: ConversationState) -> str:
    """
    The conversation so far, the question, and the clarification already given.

    What was said before comes first and the new message last, so the message actually
    being judged sits closest to the reply the model has to make.
    """
    question = state["employee_question"]
    clarification_reply = state.get("employee_clarification_reply")
    original_question = state.get("original_question")

    if clarification_reply and original_question:
        this_turn = (
            f'The employee originally asked: "{original_question}"\n'
            f'They were asked to clarify, and replied: "{clarification_reply}"\n'
            f"Read those together as one question."
        )
    else:
        this_turn = f'The employee asked: "{question}"'

    conversation_so_far = describe_the_conversation_so_far(state.get("remembered_turns"))
    if not conversation_so_far:
        return this_turn
    return f"{conversation_so_far}\n\n{this_turn}"
