"""Step 1: work out what is being asked, and whether enough is known to answer."""

import logging
import re

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
    q_norm = question.lower().strip()

    # Fast deterministic intent override for checking own leave status
    own_status_patterns = [
        r"\bhas (my leave|my leave request|it) been approved\b",
        r"\b(has|is) my leave( request)? (been )?approved\b",
        r"\brequested leaves?\b",
        r"\brequested leaves\?\s*\(\s*does my leaves? approved by my manager\??\s*\)",
        r"\bdoes my leaves?\b",
        r"\bdid my manager approve\b",
        r"\bapproved by my manager\b",
        r"\bis (it|my leave) approved\b",
        r"\bare (they|my leaves) approved\b",
        r"\bhas (it|my leave) been approved\b",
        r"\bwhat about (my )?leave\b",
        r"\bleave(s)? i requested\b",
        r"\bleave(s)? i applied\b",
        r"\brequest(s)? i sent\b",
        r"\bstatus of (my )?leave\b",
        r"\bmy leave status\b",
        r"\bmy leave requests?\b",
    ]

    # Fast deterministic intent override for manager approval inquiries
    manager_approval_patterns = [
        r"\bwhat leave requests? do i need to approve\b",
        r"\bleave request\s*\(\s*what leave requests? do i need to approve\??\s*\)",
        r"\bleave requests? to approve\b",
        r"\bneed to approve\b",
        r"\brequests? i need to approve\b",
        r"\bwhat do i need to approve\b",
        r"\bpending approvals? from my team\b",
        r"\bteam leave requests?\b",
        r"\bleave requests? awaiting (my )?approval\b",
        r"\b(is there )?any (leave )?pending (for me )?to approve\b",
        r"\bany pending leave(s)?\b",
        r"\bpending leave(s)? to approve\b",
        r"\bdo i have (any )?(leave(s)?|approvals?) pending\b",
        r"\bare there (any )?pending leave(s)?\b",
        r"\b(any )?leave(s)? pending for me to approve\b",
        r"\bjunior(s)?('s)? leave\b",
        r"\bdid (my |any )?junior(s)? (ask|request)\b",
        r"\bleave request(s)? of (my )?junior(s)?\b",
        r"\b(approve|reject|review) (my |their )?junior(s)?\b",
    ]

    # Fast deterministic intent override for conversational greetings, acknowledgments, pleasantries & gratitude
    conversational_patterns = [
        r"^(ok|okay|k|noted|got it|all right|alright|understood|sounds good|sure|fine|great|perfect|done|تمام|حسنا|حسناً|ماشي|اوكي|أوكي|طيب|تسلم)[\.\!\s]*$",
        r"\b(how are you|how're you|how r u|how are you doing|how is it going|how's it going|how do you do|how have you been|how are things|كيف حالك|شخبارك|كيفك|شلونك|عساك بخير)\b",
        r"^(thank you|thanks|thank u|thx|much appreciated|many thanks|thanks a lot|شكرا|شكراً|مشكور|تسلم|يعطيك العافية|جزاك الله خير)[\.\!\s]*$",
    ]

    if any(re.search(pat, q_norm) for pat in own_status_patterns):
        understanding = QueryUnderstanding(
            intent=QuestionIntent.CHECK_LEAVE_STATUS,
            confidence=1.0,
            needs_clarification=False,
            needs_rewrite=False,
            is_multi_question=False,
            missing_information=[],
        )
    elif any(re.search(pat, q_norm) for pat in manager_approval_patterns):
        understanding = QueryUnderstanding(
            intent=QuestionIntent.APPROVE_LEAVE,
            confidence=1.0,
            needs_clarification=False,
            needs_rewrite=False,
            is_multi_question=False,
            missing_information=[],
        )
    elif any(re.search(pat, q_norm) for pat in conversational_patterns):
        understanding = QueryUnderstanding(
            intent=QuestionIntent.GREETING,
            confidence=1.0,
            needs_clarification=False,
            needs_rewrite=False,
            is_multi_question=False,
            missing_information=[],
        )
    else:
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
