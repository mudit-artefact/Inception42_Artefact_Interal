"""Helpers for driving the workflow directly, without going through HTTP."""

import time

import pytest

from app.workflow.conversation_state import thread_name_for


@pytest.fixture
def start_turn():
    """Build the opening state for one turn."""

    def build(question: str, employee_id: str = "EMP001", language: str = "en") -> dict:
        return {
            "conversation_id": "conversation-under-test",
            "employee_id": employee_id,
            "employee_question": question,
            "requested_language": language,
            "started_at_seconds": time.time(),
            "clarification_round": 0,
            "is_awaiting_clarification": False,
            "original_question": None,
            "employee_clarification_reply": None,
        }

    return build


@pytest.fixture
def saved_conversation():
    """Where one test's conversation is filed."""
    return {"configurable": {"thread_id": thread_name_for("conversation-under-test")}}


@pytest.fixture
def script_understanding(fake_language_model):
    """Script step 1's reading of the question."""

    def script(
        intent: str = "hr_question",
        confidence: float = 0.95,
        needs_clarification: bool = False,
        needs_rewrite: bool = False,
        is_multi_question: bool = False,
        missing_information: list[str] | None = None,
    ):
        fake_language_model.reply_to_structured_call(
            "QueryUnderstanding",
            {
                "intent": intent,
                "confidence": confidence,
                "needs_clarification": needs_clarification,
                "missing_information": missing_information or [],
                "needs_rewrite": needs_rewrite,
                "is_multi_question": is_multi_question,
                "reasoning": "scripted for this test",
            },
        )

    return script


@pytest.fixture
def script_decomposition(fake_language_model):
    """Script step 2B's rewording of the question and the parts it splits into."""

    def script(*subqueries: str):
        fake_language_model.reply_to_structured_call(
            "DecomposedQuery",
            {"subqueries": list(subqueries), "reasoning": "scripted for this test"},
        )

    return script


@pytest.fixture
def script_routing_per_part(fake_language_model):
    """
    Script a different route for each part, in the order the parts are routed.

    The fake answers by requested output model, so a plain script would give every part
    the same route. This replaces that one entry with a queue.
    """

    def script(*routes: tuple[str, list[str]]):
        remaining = list(routes)

        def next_decision(**keyword_arguments):
            required_evidence, fields = remaining.pop(0) if remaining else ("policy", [])
            return {
                "required_evidence": required_evidence,
                "requested_hr_data_fields": fields,
                "reason": "scripted for this test",
            }

        fake_language_model.reply_to_structured_calls_in_turn(
            "SourceRoutingDecision", next_decision
        )

    return script


@pytest.fixture
def script_routing(fake_language_model):
    """Script step 3's decision about where the answer must come from."""

    def script(required_evidence: str = "policy", fields: list[str] | None = None):
        fake_language_model.reply_to_structured_call(
            "SourceRoutingDecision",
            {
                "required_evidence": required_evidence,
                "requested_hr_data_fields": fields or [],
                "reason": "scripted for this test",
            },
        )

    return script
