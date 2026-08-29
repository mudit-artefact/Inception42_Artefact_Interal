"""
A conversation's saved state outlives the question that filled it in.

Everything a question works out about itself — the query it was rewritten into, the
parts it was split into, where it was routed, why it fell back — has to be cleared
before the next question, or the next question is answered as if it were the last one.
"""

import pytest

from app.domain.enums import AnswerStatus


@pytest.fixture(autouse=True)
def _canned_evidence(stub_policy_search_service, temporary_database):
    pass


def test_a_follow_up_that_needs_no_rewording_is_not_searched_as_the_last_question(
    conversation_workflow, start_turn, saved_conversation, script_understanding,
    script_decomposition, script_routing, fake_language_model,
):
    """
    The first question is reworded; the second is already clear and so is never reworded.
    The second must still be searched for as itself.
    """
    script_understanding(needs_rewrite=True)
    script_decomposition("annual leave carry over limit")
    script_routing(required_evidence="policy")
    fake_language_model.reply_to_plain_call("Carry-over is capped at 10 working days.")
    conversation_workflow.invoke(start_turn("what about carry over?"), saved_conversation)

    script_understanding(needs_rewrite=False)
    second = conversation_workflow.invoke(
        start_turn("How much sick leave do I get?"), saved_conversation
    )

    assert [plan["question"] for plan in second["subquery_plans"]] == [
        "How much sick leave do I get?"
    ]


def test_a_question_asking_one_thing_is_not_split_by_the_last_question(
    conversation_workflow, start_turn, saved_conversation, script_understanding,
    script_decomposition, script_routing, fake_language_model,
):
    script_understanding(is_multi_question=True)
    script_decomposition("annual leave entitlement", "annual leave carry over limit")
    script_routing(required_evidence="policy")
    fake_language_model.reply_to_plain_call("You accrue 25 working days.")
    first = conversation_workflow.invoke(
        start_turn("What do I get, and how much carries over?"), saved_conversation
    )
    assert len(first["subquery_statuses"]) == 2

    script_understanding(is_multi_question=False)
    second = conversation_workflow.invoke(
        start_turn("How much sick leave do I get?"), saved_conversation
    )

    assert len(second["subquery_statuses"]) == 1
    assert second["subqueries"] == []


def test_a_question_does_not_inherit_the_last_questions_reason_for_falling_back(
    conversation_workflow, start_turn, saved_conversation, script_understanding, script_routing,
    fake_language_model,
):
    """The fallback message an employee reads is chosen by this reason."""
    script_understanding(intent="out_of_scope", confidence=0.97)
    first = conversation_workflow.invoke(start_turn("What is the weather?"), saved_conversation)
    assert first["fallback_reason"] == "out_of_scope"

    script_understanding(confidence=0.4)
    script_routing(required_evidence="unsupported")
    second = conversation_workflow.invoke(
        start_turn("Can you dispute my payroll deduction?"), saved_conversation
    )

    assert second["fallback_reason"] == "needs_human"
    assert second["answer_status"] == AnswerStatus.SAFE_FALLBACK


def test_a_pause_for_clarification_keeps_what_the_question_had_worked_out(
    conversation_workflow, start_turn, saved_conversation, script_understanding, script_routing,
    fake_language_model,
):
    """
    Resuming continues the same question, so it must not be reset. It resumes at the
    pause rather than at the start of the turn, which is what keeps it intact.
    """
    from langgraph.types import Command

    script_understanding(needs_clarification=True, missing_information=["which leave"])
    fake_language_model.reply_to_structured_call(
        "ClarificationQuestion",
        {"clarification_question": "Which type of leave?", "missing_information": "leave type"},
    )
    conversation_workflow.invoke(start_turn("How many leaves can I take?"), saved_conversation)

    script_understanding(needs_clarification=False)
    script_routing(required_evidence="policy")
    fake_language_model.reply_to_plain_call("You accrue 25 working days of annual leave.")
    resumed = conversation_workflow.invoke(Command(resume="annual"), saved_conversation)

    assert resumed["clarification_round"] == 1, "the round already asked was not forgotten"
    assert resumed["original_question"] == "How many leaves can I take?"
    assert resumed["answer_status"] == AnswerStatus.VERIFIED
