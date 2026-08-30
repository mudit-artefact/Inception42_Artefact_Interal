"""
"Make that shorter" is not a question about HR policy.

The answer already exists. Searching the policy documents for those words finds nothing
useful, and the reply that comes back asks the employee to repeat themselves. So a
request to change the *form* of the last reply is answered from that reply instead.

Nothing new is asserted on this path. The check that runs afterwards holds every figure
in the rewrite against the reply being reworked, and that reply was itself checked
against real policy extracts when it was written — so the trail back to a document is
never broken, only one step longer.
"""

import pytest

from app.domain.enums import AnswerStatus


@pytest.fixture(autouse=True)
def _canned_evidence(stub_policy_search_service, temporary_database):
    pass


@pytest.fixture
def after_a_real_answer(
    conversation_workflow, start_turn, saved_conversation, script_understanding,
    script_routing, fake_language_model,
):
    """One genuine answered turn, so there is something to rework."""
    script_understanding()
    script_routing(required_evidence="policy")
    fake_language_model.reply_to_plain_call(
        "Carry-over is capped at 10 working days and must be used before 31 March."
    )
    first = conversation_workflow.invoke(
        start_turn("What is the carry over limit?"), saved_conversation
    )
    assert first["answer_status"] == AnswerStatus.VERIFIED
    return first


def _ask(conversation_workflow, start_turn, saved_conversation, message):
    return conversation_workflow.invoke(start_turn(message), saved_conversation)


def test_the_previous_reply_is_reworked_without_searching_again(
    after_a_real_answer, conversation_workflow, start_turn, saved_conversation,
    script_understanding, script_rephrase, fake_language_model,
):
    script_understanding(intent="about_the_last_answer")
    script_rephrase("Carry-over is capped at 10 working days, usable until 31 March.")
    calls_before = fake_language_model.count_calls_for("SourceRoutingDecision")

    result = _ask(conversation_workflow, start_turn, saved_conversation, "make that shorter")

    assert "10 working days" in result["final_answer"]
    assert result["answer_status"] == AnswerStatus.VERIFIED
    # Routing is what starts a search. It never ran.
    assert fake_language_model.count_calls_for("SourceRoutingDecision") == calls_before


def test_the_reworked_reply_keeps_the_sources_of_the_reply_it_reworked(
    after_a_real_answer, conversation_workflow, start_turn, saved_conversation,
    script_understanding, script_rephrase,
):
    """The content is the same content, so it rests on the same extracts."""
    script_understanding(intent="about_the_last_answer")
    script_rephrase("Carry-over is capped at 10 working days.")

    result = _ask(conversation_workflow, start_turn, saved_conversation, "make that shorter")

    assert result["citations"], "a reworked reply came back with no sources"
    assert {citation["source_type"] for citation in result["citations"]} == {"policy"}


def test_a_figure_invented_during_the_rework_is_rejected(
    after_a_real_answer, conversation_workflow, start_turn, saved_conversation,
    script_understanding, script_rephrase,
):
    """
    The whole safety argument for this path. A rewrite may only restate what the previous
    reply said, and the number check is what enforces it.
    """
    script_understanding(intent="about_the_last_answer")
    script_rephrase("Carry-over is capped at 45 working days.")  # the reply said 10

    result = _ask(conversation_workflow, start_turn, saved_conversation, "make that shorter")

    assert result["answer_verdict"] == "invalid"
    assert "45 working days" in result["unsupported_claims"]
    assert result["answer_status"] == AnswerStatus.SAFE_FALLBACK


def test_a_translation_is_not_rejected_for_being_in_the_language_it_was_asked_for(
    after_a_real_answer, conversation_workflow, start_turn, saved_conversation,
    script_understanding, script_rephrase,
):
    """
    "Say that in Arabic" is an English sentence, so the turn's language is decided as
    English. Without the rework declaring what it produced, the check at the end rejects
    the Arabic translation for not being English and the employee gets a refusal.
    """
    script_understanding(intent="about_the_last_answer")
    script_rephrase("يبلغ الحد الأقصى للترحيل 10 أيام عمل.", answer_language="ar")

    result = _ask(conversation_workflow, start_turn, saved_conversation, "say that in Arabic")

    assert result["answer_verdict"] == "valid"
    assert result["answer_status"] == AnswerStatus.VERIFIED
    assert any("؀" <= character <= "ۿ" for character in result["final_answer"])


def test_being_asked_to_rework_a_reply_that_was_never_given(
    conversation_workflow, start_turn, saved_conversation, script_understanding,
    fake_language_model,
):
    """The first message of a conversation. Explain, rather than search for the words."""
    script_understanding(intent="about_the_last_answer")

    result = _ask(conversation_workflow, start_turn, saved_conversation, "make that shorter")

    assert result["fallback_reason"] == "nothing_to_rephrase"
    assert result["answer_status"] == AnswerStatus.SAFE_FALLBACK
    assert fake_language_model.count_calls_for("SourceRoutingDecision") == 0
    assert fake_language_model.count_calls_for("RephrasedAnswer") == 0
