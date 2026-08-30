"""The check between drafting an answer and showing it to the employee."""

import logging

from app.workflow.answer_validation import validate_answer as run_validation_checks
from app.workflow.conversation_state import ConversationState

logger = logging.getLogger(__name__)


def validate_answer(state: ConversationState) -> dict:
    """Decide whether the drafted answer may be shown."""
    policy_passages = state.get("policy_passages") or []
    hr_data = state.get("hr_data_facts") or {}
    checkable_evidence = state.get("checkable_evidence", "")

    # A rewrite of an earlier reply retrieves nothing, and is checked against that reply
    # instead — which was itself checked against real extracts when it was written.
    has_any_evidence = (
        bool(policy_passages) or bool(hr_data.get("fields")) or bool(checkable_evidence.strip())
    )

    outcome = run_validation_checks(
        answer=state.get("draft_answer", ""),
        evidence_text=checkable_evidence,
        employee_id=state["employee_id"],
        requested_language=state.get("requested_language", "en"),
        has_any_evidence=has_any_evidence,
        declared_calculations=state.get("declared_calculations") or [],
        # The employee's own words, so a figure they supposed can be quoted back to them
        # once a sum anchored in real evidence has used it.
        employee_question=state.get("employee_question", ""),
    )

    return {
        "answer_verdict": "valid" if outcome.is_valid else "invalid",
        "validation_reason": outcome.reason,
        "unsupported_claims": outcome.unsupported_claims,
    }
