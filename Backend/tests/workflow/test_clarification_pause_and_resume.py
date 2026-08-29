"""
The clarification pause.

This is the behaviour the whole checkpointer exists for. A vague question is answered
with a question, the conversation stops there, and the employee's reply — which arrives
as a separate request, possibly minutes later — continues from that exact point.

Before this, the pause was not real: the graph ended, and the browser held the pending
question and posted it back. That state lived only in a page's memory, so a reload lost
it while the interface still showed the "clarification needed" badge.
"""

import pytest
from langgraph.types import Command

from app.domain.enums import AnswerStatus
from app.workflow.conversation_state import thread_name_for


@pytest.fixture(autouse=True)
def _use_canned_passages(stub_policy_search_service, temporary_database):
    """Every test here needs an employee record and canned policy extracts."""


@pytest.fixture
def script_a_vague_then_clear_question(fake_language_model, script_understanding, script_routing):
    """The question is vague at first, and clear once the employee has answered."""

    def script():
        script_understanding(needs_clarification=True, confidence=0.55,
                             missing_information=["which kind of leave"])
        fake_language_model.reply_to_structured_call(
            "ClarificationQuestion",
            {
                "clarification_question": "Which type of leave did you mean?",
                "missing_information": "leave type",
            },
        )
        script_routing(required_evidence="policy")
        fake_language_model.reply_to_plain_call("Carry-over is capped at 10 working days.")

    return script


def test_a_vague_question_pauses_and_asks_something_back(
    conversation_workflow, start_turn, saved_conversation, script_a_vague_then_clear_question
):
    script_a_vague_then_clear_question()

    result = conversation_workflow.invoke(
        start_turn("How many leaves can I take?"), saved_conversation
    )

    assert "__interrupt__" in result, "the workflow must pause, not answer"
    paused_with = result["__interrupt__"][0].value
    assert paused_with["clarification_question"] == "Which type of leave did you mean?"
    assert paused_with["original_question"] == "How many leaves can I take?"


def test_the_paused_conversation_is_saved_and_waiting(
    conversation_workflow, start_turn, saved_conversation, script_a_vague_then_clear_question
):
    script_a_vague_then_clear_question()
    conversation_workflow.invoke(start_turn("How many leaves can I take?"), saved_conversation)

    snapshot = conversation_workflow.get_state(saved_conversation)

    assert snapshot.tasks, "the conversation is parked mid-flow"
    assert any(task.interrupts for task in snapshot.tasks), "and it is waiting on the employee"


def test_the_employees_reply_continues_the_same_conversation(
    conversation_workflow, start_turn, saved_conversation, script_a_vague_then_clear_question
):
    script_a_vague_then_clear_question()
    conversation_workflow.invoke(start_turn("How many leaves can I take?"), saved_conversation)

    result = conversation_workflow.invoke(Command(resume="annual leave"), saved_conversation)

    assert "__interrupt__" not in result
    assert result["answer_status"] == AnswerStatus.VERIFIED
    # The reply was folded into the original question rather than replacing it.
    assert "How many leaves can I take?" in result["employee_question"]
    assert "annual leave" in result["employee_question"]


def test_resuming_does_not_pay_for_the_clarification_question_twice(
    conversation_workflow,
    start_turn,
    saved_conversation,
    script_a_vague_then_clear_question,
    fake_language_model,
):
    """
    A paused step runs again from its beginning when it resumes. The clarification
    question is written in its own earlier step precisely so that resuming does not
    repeat that call.
    """
    script_a_vague_then_clear_question()
    conversation_workflow.invoke(start_turn("How many leaves can I take?"), saved_conversation)
    conversation_workflow.invoke(Command(resume="annual leave"), saved_conversation)

    assert fake_language_model.count_calls_for("ClarificationQuestion") == 1


def test_the_employee_is_only_asked_to_clarify_once(
    conversation_workflow,
    start_turn,
    saved_conversation,
    fake_language_model,
    script_understanding,
    script_routing,
):
    """
    The question is still read as vague after the employee answers. Without a cap the
    workflow would keep asking them to clarify forever.
    """
    script_understanding(needs_clarification=True, confidence=0.5,
                         missing_information=["which kind of leave"])
    fake_language_model.reply_to_structured_call(
        "ClarificationQuestion",
        {"clarification_question": "Which type of leave?", "missing_information": "leave type"},
    )
    script_routing(required_evidence="policy")
    fake_language_model.reply_to_plain_call("Carry-over is capped at 10 working days.")

    conversation_workflow.invoke(start_turn("How many leaves can I take?"), saved_conversation)
    result = conversation_workflow.invoke(Command(resume="not sure"), saved_conversation)

    assert "__interrupt__" not in result, "it must answer rather than ask again"
    assert result["clarification_round"] == 1


def test_two_conversations_do_not_share_a_pause(
    conversation_workflow, start_turn, script_a_vague_then_clear_question
):
    """A pause belongs to one conversation, not to the employee."""
    script_a_vague_then_clear_question()
    first = {"configurable": {"thread_id": thread_name_for("conversation-one")}}
    second = {"configurable": {"thread_id": thread_name_for("conversation-two")}}

    conversation_workflow.invoke(
        {**start_turn("How many leaves can I take?"), "conversation_id": "conversation-one"}, first
    )

    assert not any(
        task.interrupts for task in conversation_workflow.get_state(second).tasks
    ), "the other conversation is not waiting on anything"
