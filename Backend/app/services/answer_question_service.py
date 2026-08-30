"""
Running one turn of a conversation.

Decides whether this request continues a conversation that paused for a clarification, or
starts a fresh one, then presents the result as the API's answer.
"""

import logging
import re
import time
from typing import Optional

from langgraph.types import Command

from app.api.wire_intent_mapping import wire_intent_for
from app.core.conversation_identifier import (
    create_conversation_identifier,
    use_or_create_conversation_identifier,
)
from app.core.language_detection import detect_language
from app.schemas.answer import AnswerResponse, SourceCitation
from app.workflow.conversation_state import thread_name_for

logger = logging.getLogger(__name__)


def answer_question(
    workflow,
    employee_question: str,
    employee_id: str,
    conversation_id: Optional[str] = None,
    requested_language: Optional[str] = None,
) -> AnswerResponse:
    """Answer one question, continuing the conversation where it left off."""
    started_at = time.time()
    conversation_id = use_or_create_conversation_identifier(conversation_id)
    requested_language = requested_language or detect_language(employee_question)

    saved_conversation = {"configurable": {"thread_id": thread_name_for(conversation_id)}}
    saved_state = _saved_state_of(workflow, saved_conversation)

    if _belongs_to_somebody_else(saved_state, employee_id):
        logger.warning(
            f"Conversation {conversation_id} belongs to another employee; "
            f"starting a new one for {employee_id}"
        )
        conversation_id = create_conversation_identifier()
        saved_conversation = {"configurable": {"thread_id": thread_name_for(conversation_id)}}
        saved_state = None

    if _is_waiting_for_an_answer(saved_state) and not _reads_as_a_new_question(employee_question):
        logger.info(f"Resuming conversation {conversation_id} with the employee's reply")
        result = workflow.invoke(Command(resume=employee_question), saved_conversation)
    else:
        if _is_waiting_for_an_answer(saved_state):
            logger.info(
                f"Conversation {conversation_id} was waiting for an answer and got a new "
                f"question instead; abandoning the pause"
            )
        result = workflow.invoke(
            _new_turn(
                conversation_id=conversation_id,
                employee_question=employee_question,
                employee_id=employee_id,
                requested_language=requested_language,
                started_at=started_at,
            ),
            saved_conversation,
        )

    return _present(result, conversation_id, requested_language, started_at)


def _saved_state_of(workflow, saved_conversation: dict):
    """
    The conversation as it was left, or None when there is nothing saved to read.

    One read, used for both of the questions asked of it below. A conversation that has
    never been used comes back as an empty snapshot rather than an error, so a brand new
    conversation takes the same path as an unreadable one.
    """
    try:
        return workflow.get_state(saved_conversation)
    except Exception as error:
        # Treated as "nothing saved": a conversation that cannot be read is started
        # again rather than resumed, and — importantly — never treated as belonging to
        # whoever happens to be asking.
        logger.warning(f"Could not read the saved conversation: {error}")
        return None


def _belongs_to_somebody_else(saved_state, employee_id: str) -> bool:
    """
    Whether this conversation was started by a different employee.

    A conversation now carries what was said in it, so attaching to one that is not
    yours reads somebody else's questions and answers, not just their pending
    clarification. Nothing above this line authenticates `employee_id` — this stops one
    employee reaching another's conversation, not somebody claiming to be them.
    """
    if saved_state is None:
        return False
    started_by = (saved_state.values or {}).get("employee_id")
    return bool(started_by) and started_by != employee_id


# A message that asks something, rather than answering what was asked. Short replies are
# excluded deliberately: "annual leave?" is somebody answering with a shrug, not opening a
# new subject, and the question mark alone should not throw away the pause.
SHORTEST_NEW_QUESTION = 4
ASKS_SOMETHING = re.compile(
    r"\?\s*$"
    r"|^\s*(what|when|who|whom|whose|how|why|which|where|can|could|do|does|did|is|are|am"
    r"|was|were|will|would|should|shall|may|might|tell me|show me|give me|explain)\b"
    r"|^\s*(هل|ما|ماذا|متى|من|كيف|لماذا|أي|كم|أين|اشرح|أعطني)\b",
    re.IGNORECASE,
)


def _reads_as_a_new_question(message: str) -> bool:
    """
    Whether this message opens a new subject rather than answering the pending question.

    A paused conversation used to take whatever arrived next as the answer it was waiting
    for. So an employee asked about their leave, was asked which type, and then asked
    something else entirely — and the two were glued together and answered as one, in the
    language of the abandoned question. The new subject was never answered at all.

    Judged on the message alone, without a model call: this runs before the graph starts
    and a wrong guess here is cheap in one direction only. Treating a genuine reply as a
    new question loses the pause and asks again; treating a new question as a reply loses
    the question itself.
    """
    words = (message or "").split()
    if len(words) < SHORTEST_NEW_QUESTION:
        return False
    return ASKS_SOMETHING.search(message.strip()) is not None


def _is_waiting_for_an_answer(saved_state) -> bool:
    """Whether this conversation paused to ask the employee something."""
    if saved_state is None:
        return False
    return bool(saved_state.tasks) and any(task.interrupts for task in saved_state.tasks)


def _new_turn(
    conversation_id: str,
    employee_question: str,
    employee_id: str,
    requested_language: str,
    started_at: float,
) -> dict:
    return {
        "conversation_id": conversation_id,
        "employee_id": employee_id,
        "employee_question": employee_question,
        "requested_language": requested_language,
        "started_at_seconds": started_at,
        "clarification_round": 0,
        "is_awaiting_clarification": False,
        "original_question": None,
        "employee_clarification_reply": None,
    }


def _present(
    result: dict,
    conversation_id: str,
    requested_language: str,
    started_at: float,
) -> AnswerResponse:
    """Turn the finished state into the answer the web interface reads."""
    pause = _pending_clarification(result)

    if pause:
        # The interface will only enter its clarification mode when the flag and the
        # original question are both present, so they are always set together.
        return AnswerResponse(
            answer=pause["clarification_question"],
            sources=[],
            conversation_id=conversation_id,
            target_language=requested_language,
            latency_ms=int((time.time() - started_at) * 1000),
            intent=wire_intent_for(None, None, is_awaiting_clarification=True),
            confidence_score=result.get("intent_confidence", 1.0),
            is_awaiting_clarification=True,
            original_question=pause["original_question"],
            clarifying_question=pause["clarification_question"],
        )

    return AnswerResponse(
        answer=result.get("final_answer", ""),
        sources=[SourceCitation(**citation) for citation in result.get("citations", [])],
        conversation_id=conversation_id,
        employee_profile=result.get("employee_profile", {}),
        target_language=requested_language,
        latency_ms=result.get("latency_milliseconds")
        or int((time.time() - started_at) * 1000),
        tokens_used=result.get("tokens_used", 0),
        intent=wire_intent_for(
            result.get("question_intent"),
            result.get("answer_status"),
            is_awaiting_clarification=False,
        ),
        rewritten_query=result.get("retrieval_query"),
        confidence_score=result.get("intent_confidence", 1.0),
        is_awaiting_clarification=False,
    )


def _pending_clarification(result: dict) -> Optional[dict]:
    """The question the workflow paused to ask, when it paused."""
    interrupts = result.get("__interrupt__")
    if not interrupts:
        return None

    raised = interrupts[0]
    payload = getattr(raised, "value", None) or {}
    clarification_question = payload.get("clarification_question")
    if not clarification_question:
        return None

    return {
        "clarification_question": clarification_question,
        "original_question": payload.get("original_question") or "",
    }
