"""
One branch for every action the assistant takes.

There used to be a top-level branch per action: cancelling, checking status, a manager's
approvals, school verification, each its own destination out of the first fork. Adding a
sixth meant adding a seventh destination, and the diagram grew a lane every time the
product grew a feature.

They are all the same shape — read the request, do the thing, say what happened — so they
are one destination now, and which one runs is a lookup. What decides is the intent the
question was already understood as, so nothing is asked twice and nothing new can be
reached that was not registered here.

Applying for leave is the exception and keeps its own steps, because it is the only one
that pauses to ask the employee something.
"""

import logging

from app.domain.enums import AnswerStatus, QuestionIntent
from app.workflow.conversation_state import ConversationState
from app.workflow.nodes.handle_leave_action import (
    handle_leave_cancellation,
    handle_leave_status,
    handle_manager_approval,
)
from app.workflow.nodes.handle_school_verification import handle_school_verification

logger = logging.getLogger(__name__)


# Which step runs for which understood intent. A new action is a line here and a tool in
# the registry — not a new branch in the graph.
ACTION_FOR_INTENT = {
    QuestionIntent.CANCEL_LEAVE.value: handle_leave_cancellation,
    QuestionIntent.CHECK_LEAVE_STATUS.value: handle_leave_status,
    QuestionIntent.APPROVE_LEAVE.value: handle_manager_approval,
    QuestionIntent.REJECT_LEAVE.value: handle_manager_approval,
    QuestionIntent.CHECK_SCHOOL_VERIFICATION.value: handle_school_verification,
    QuestionIntent.SUBMIT_SCHOOL_VERIFICATION.value: handle_school_verification,
    QuestionIntent.REVIEW_SCHOOL_CASES.value: handle_school_verification,
}


def run_action(state: ConversationState) -> dict:
    """Do what the question asked for, and say what happened."""
    intent = state.get("question_intent")
    action = ACTION_FOR_INTENT.get(intent)

    if action is None:
        # Unreachable through the graph — the fork only sends registered intents here —
        # but an intent added to the enum and to the fork and forgotten here would
        # otherwise answer with an empty string.
        logger.error(f"No action is registered for {intent!r}")
        language = state.get("requested_language", "en")
        return {
            "final_answer": (
                "لا أستطيع تنفيذ هذا الطلب. يرجى التواصل مع قسم شؤون الموظفين."
                if language == "ar"
                else "I cannot carry that out. Please contact People & Culture."
            ),
            "answer_status": AnswerStatus.SAFE_FALLBACK.value,
            "citations": [],
        }

    logger.info(f"Running {action.__name__} for {intent}")
    return action(state)
