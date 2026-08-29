"""The check between drafting an answer and showing it to the employee."""

import logging

from app.workflow.answer_validation import validate_answer as run_validation_checks
from app.workflow.conversation_state import ConversationState

logger = logging.getLogger(__name__)


def validate_answer(state: ConversationState) -> dict:
    """Decide whether the drafted answer may be shown."""
    policy_passages = state.get("policy_passages") or []
    hr_data = state.get("hr_data_facts") or {}
    has_any_evidence = bool(policy_passages) or bool(hr_data.get("fields"))

    outcome = run_validation_checks(
        answer=state.get("draft_answer", ""),
        evidence_text=state.get("evidence_summary", ""),
        employee_id=state["employee_id"],
        requested_language=state.get("requested_language", "en"),
        has_any_evidence=has_any_evidence,
    )

    return {
        "answer_verdict": "valid" if outcome.is_valid else "invalid",
        "validation_reason": outcome.reason,
        "unsupported_claims": outcome.unsupported_claims,
    }
