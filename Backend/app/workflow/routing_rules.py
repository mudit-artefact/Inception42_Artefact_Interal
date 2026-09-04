"""
Every branching decision in the workflow.

These are the diamonds in the design: "Missing information?", "Rewrite or decompose?",
"Source(s) per subquery?" and the check on the finished answer. They used to be `if`
statements buried in a Python function between two separate graphs, which meant they
could not be seen in a trace or tested on their own.

Each one is a plain function of the state — no model calls, no database, no side
effects — so every branch can be tested directly.
"""

import logging

from langgraph.types import Send

from app.domain.enums import QuestionIntent, RequiredEvidence
from app.workflow.conversation_state import ConversationState

logger = logging.getLogger(__name__)

# How many times a single question may be sent back for clarification.
MAXIMUM_CLARIFICATION_ROUNDS = 1

GATHER_EVIDENCE_FOR_ONE_PART = "gather_subquery_evidence"


def decide_after_understanding(state: ConversationState) -> str:
    """
    The first fork: greet, refuse, ask something back, prepare the question, or go on.

    Clarification is capped. Without a cap, a question the model keeps finding vague
    could be sent back to the employee forever.
    """
    intent = state.get("question_intent")

    if intent == QuestionIntent.GREETING:
        return "generate_greeting"

    if intent == QuestionIntent.OUT_OF_SCOPE:
        return "build_safe_fallback"

    if intent == QuestionIntent.APPLY_LEAVE:
        return "handle_leave_application"

    if intent == QuestionIntent.CANCEL_LEAVE:
        return "handle_leave_cancellation"

    if intent == QuestionIntent.CHECK_LEAVE_STATUS:
        return "handle_leave_status"

    if intent in (QuestionIntent.APPROVE_LEAVE, QuestionIntent.REJECT_LEAVE):
        return "handle_manager_approval"

    if intent in (
        QuestionIntent.CHECK_SCHOOL_VERIFICATION,
        QuestionIntent.SUBMIT_SCHOOL_VERIFICATION,
        QuestionIntent.REVIEW_SCHOOL_CASES,
    ):
        return "handle_school_verification"

    if intent == QuestionIntent.DOCUMENT_UPLOAD:
        return "generate_document_upload_prompt"


    # A request to rework the last reply is answered from that reply, not by searching
    # the policy documents for the words "make that shorter". Asked before there is a
    # reply to rework, it gets a plain explanation rather than a pointless search.
    if intent == QuestionIntent.ABOUT_THE_LAST_ANSWER:
        if (state.get("previous_reply") or {}).get("text"):
            return "rephrase_previous_answer"
        logger.info("Asked to rework a reply, but nothing has been said yet")
        return "build_safe_fallback"

    already_asked = state.get("clarification_round", 0)
    if state.get("needs_clarification") and already_asked < MAXIMUM_CLARIFICATION_ROUNDS:
        return "compose_clarification_question"

    if state.get("needs_clarification"):
        logger.info("Already asked for clarification once; answering with what is known")

    # A message asking two things has to be split even when each part is worded well, or
    # the second thing is never searched for and never answered.
    if state.get("needs_rewrite") or state.get("is_multi_question"):
        return "rewrite_and_decompose_query"

    return "route_each_subquery"


def fan_out_to_each_subquery(state: ConversationState) -> list[Send] | str:
    """
    The second fork: start one branch per part of the question, all at the same time.

    A part that cannot be served starts no branch — there is nothing to look for. When no
    part can be served there is nothing to gather at all, and the turn goes straight to
    the controlled response.
    """
    plans = state.get("subquery_plans") or []
    servable = [
        plan for plan in plans if plan["required_evidence"] != RequiredEvidence.UNSUPPORTED
    ]

    if not servable:
        logger.info("No part of this question can be served from policy or the employee record")
        return "build_safe_fallback"

    if len(plans) > 1:
        logger.info(f"Gathering evidence for {len(servable)} of {len(plans)} parts at once")

    return [
        Send(
            GATHER_EVIDENCE_FOR_ONE_PART,
            {
                "index": plan["index"],
                "question": plan["question"],
                "required_evidence": plan["required_evidence"],
                "requested_hr_data_fields": plan["requested_hr_data_fields"],
                "employee_facts": state.get("employee_facts") or {},
                "requested_language": state.get("requested_language", "en"),
            },
        )
        for plan in servable
    ]


def decide_answer_validity(state: ConversationState) -> str:
    """The last fork: show the answer, or fall back safely."""
    if state.get("answer_verdict") == "valid":
        return "finalize_verified_answer"
    return "build_safe_fallback"
