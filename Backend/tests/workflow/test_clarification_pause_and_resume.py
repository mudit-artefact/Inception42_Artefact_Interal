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


# ── When the employee asks something else instead of answering ───────────────


def test_a_new_question_abandons_the_pause_instead_of_being_swallowed(
    conversation_workflow, script_understanding, script_routing, fake_language_model,
    temporary_database, stub_policy_search_service,
):
    """
    A paused conversation used to take whatever arrived next as its answer.

    So an employee asked about leave, was asked which type, and then asked about working
    from home — and the two were glued into one question and answered together, in the
    language of the one they had moved on from. The question they actually asked was
    never answered.
    """
    from app.services.answer_question_service import answer_question

    script_understanding(needs_clarification=True, confidence=0.55,
                         missing_information=["which kind of leave"])
    fake_language_model.reply_to_structured_call(
        "ClarificationQuestion",
        {"clarification_question": "Which type of leave did you mean?",
         "missing_information": "leave type"},
    )
    paused = answer_question(
        workflow=conversation_workflow, employee_question="How many leaves can I take?",
        employee_id="EMP001", conversation_id="swallow-test",
    )
    assert paused.is_awaiting_clarification

    # Not an answer to "which type of leave" — a different subject entirely.
    script_understanding(needs_clarification=False, confidence=0.95)
    script_routing(required_evidence="policy")
    fake_language_model.reply_to_plain_call("Class A roles may work remotely two days a week.")

    fake_language_model.recorded_calls.clear()
    answered = answer_question(
        workflow=conversation_workflow,
        employee_question="Can I work from home two days a week?",
        employee_id="EMP001", conversation_id="swallow-test",
    )

    assert not answered.is_awaiting_clarification

    # Asserted on what the model was asked, not on what it replied. The fake returns the
    # same scripted text whichever path runs, so a test that checks only the answer passes
    # with the fix removed — this one caught exactly that and was rewritten.
    everything_asked = " ".join(
        message["content"]
        for call in fake_language_model.recorded_calls
        for message in call["messages"]
    )
    assert "work from home" in everything_asked
    # The merge writes the reply in brackets after the question it was answering. That
    # exact shape is what tells the two paths apart: the earlier question appearing in the
    # remembered transcript is correct and expected, it being folded INTO this question is
    # the bug.
    assert "(Can I work from home two days a week?)" not in everything_asked, (
        "the new question was merged into the abandoned one instead of replacing it"
    )


# ── When the employee moves on instead of answering ──────────────────────────


def test_a_short_reply_is_folded_into_the_paused_question():
    """The ordinary case: two words that answer what was asked."""
    from app.workflow.nodes.clarification import merge_clarification_into_question

    merged = merge_clarification_into_question(
        {
            "employee_question": "How many leaves can I take?",
            "original_question": "How many leaves can I take?",
            "employee_clarification_reply": "Annual leave",
        }
    )

    assert merged["employee_question"] == "How many leaves can I take? (Annual leave)"


def test_a_new_question_replaces_the_paused_one_instead_of_joining_it():
    """
    An employee who ignores the question and asks a different one gets answered on the
    new one.

    Gluing the two together answers neither. Omar was asked which leave type he meant,
    asked instead whether he could work from home, and got a reply covering both — in
    Arabic, to a question he had asked in English.
    """
    from app.workflow.nodes.clarification import merge_clarification_into_question

    merged = merge_clarification_into_question(
        {
            "employee_question": "لماذا ليست 24 يوماً؟",
            "original_question": "لماذا ليست 24 يوماً؟",
            "employee_clarification_reply": "Can I work from home one day a week?",
        }
    )

    assert merged["employee_question"] == "Can I work from home one day a week?"
    assert merged["original_question"] is None
    assert merged["is_awaiting_clarification"] is False
