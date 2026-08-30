"""Step 0: read who is asking, and start the turn from a clean sheet."""

import logging

from app.database.employee_lookup import get_employee_facts_for
from app.services.employee_directory_service import build_profile
from app.workflow.conversation_state import ConversationState

logger = logging.getLogger(__name__)

# Everything one question works out about itself. A conversation's saved state outlives
# the question that filled these in, so each one is emptied before the next question
# starts. Leaving them meant a follow-up that needed no rewording searched for the
# previous question's query and answered that instead, and a turn that fell back reused
# whatever reason the last fallback had.
#
# This dict is the boundary between what a question works out and what the conversation
# remembers. Adding a field here is how a question stops leaking into the next one;
# leaving a field out is how the conversation keeps anything at all.
WORKED_OUT_FRESH_EACH_QUESTION: dict = {
    # Step 1
    "question_intent": "",
    "intent_confidence": 0.0,
    "needs_clarification": False,
    "needs_rewrite": False,
    "is_multi_question": False,
    "missing_information": [],
    # Step 2A
    "original_question": None,
    "clarification_question": None,
    "employee_clarification_reply": None,
    "is_awaiting_clarification": False,
    "clarification_round": 0,
    # Step 2B
    "subqueries": [],
    "retrieval_query": "",
    # Step 3
    "subquery_plans": [],
    "required_evidence": "",
    "requested_hr_data_fields": [],
    "routing_reason": "",
    # Step 4 — None, not an empty list: this one is gathered by appending.
    "subquery_evidence": None,
    "subquery_statuses": [],
    "policy_passages": [],
    "hr_data_facts": {},
    "evidence_summary": "",
    # Step 5 and the check that follows it
    "draft_answer": "",
    "tokens_used": 0,
    "answer_verdict": "",
    "unsupported_claims": [],
    "validation_reason": "",
    # What the employee receives
    "final_answer": "",
    "citations": [],
    "answer_status": "",
    "fallback_reason": None,
    # `remembered_turns` and `previous_reply` are deliberately NOT here, and must never
    # be added.
    #
    # They are the fields that belong to the conversation rather than to a question:
    # written at the end of a turn, read at the start of the next. Emptying them here
    # would wipe them in the single step between those two — and the failure would be
    # invisible, because every one-turn test would still pass while the follow-up they
    # exist for silently lost its context. See app/workflow/conversation_memory.py.
}


def load_employee_facts(state: ConversationState) -> dict:
    """
    Load this employee's record, and clear what the last question left behind.

    Runs first because the greeting needs their name and every later decision is made on
    their behalf. Raises EmployeeNotFoundError for an unknown identifier rather than
    inventing a placeholder employee.

    A conversation that pauses for a clarification resumes at the pause, not here, so a
    half-finished question keeps everything it had worked out. Only a new question starts
    from a clean sheet.
    """
    facts = get_employee_facts_for(state["employee_id"])
    logger.info(f"Loaded the record for {facts.name} ({facts.employee_id})")

    return {
        **WORKED_OUT_FRESH_EACH_QUESTION,
        "employee_facts": facts.as_dictionary(),
        "employee_profile": build_profile(facts).model_dump(),
    }
