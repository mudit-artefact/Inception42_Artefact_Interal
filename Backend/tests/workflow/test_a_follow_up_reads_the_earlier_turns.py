"""
A follow-up is resolved against what was actually said before it.

The instructions have always told the model to resolve a question that leans on the
previous turn. Until the conversation was given to it, it could only guess: "what about
sick leave?" was correctly spotted as needing a rewrite and then rewritten blind.

These tests read the prompts the workflow actually sent, off the fake model's recorded
calls, because what matters is not that memory is stored but that it reaches the step
that needs it — and, just as much, that it never reaches the step that must not have it.
"""

import pytest

from app.domain.enums import AnswerStatus
from app.workflow.conversation_memory import TRANSCRIPT_OPENING, TURNS_WORTH_REMEMBERING


@pytest.fixture(autouse=True)
def _canned_evidence(stub_policy_search_service, temporary_database):
    pass


def prompts_asking_for(fake_language_model, output_model_name: str | None) -> list[str]:
    """Every user message sent to the model for one kind of call, in order."""
    return [
        call["messages"][1]["content"]
        for call in fake_language_model.recorded_calls
        if call["response_format"] == output_model_name
    ]


def system_prompts_for_the_answer(fake_language_model) -> list[str]:
    """The instructions the answer was written from. The answer step takes no history."""
    return [
        call["messages"][0]["content"]
        for call in fake_language_model.recorded_calls
        if call["response_format"] is None
    ]


@pytest.fixture
def ask(conversation_workflow, start_turn, saved_conversation):
    """Ask one question in the conversation under test."""

    def send(question: str):
        return conversation_workflow.invoke(start_turn(question), saved_conversation)

    return send


def test_the_first_question_of_a_conversation_carries_no_transcript(
    ask, script_understanding, script_routing, fake_language_model
):
    script_understanding()
    script_routing(required_evidence="policy")
    fake_language_model.reply_to_plain_call("Carry-over is capped at 10 working days.")

    ask("What is the carry over limit?")

    assert TRANSCRIPT_OPENING not in prompts_asking_for(fake_language_model, "QueryUnderstanding")[0]


def test_a_follow_up_is_given_the_previous_turn_when_the_question_is_read(
    ask, script_understanding, script_routing, fake_language_model
):
    script_understanding()
    script_routing(required_evidence="policy")
    fake_language_model.reply_to_plain_call("Carry-over is capped at 10 working days.")
    ask("What is the carry over limit?")

    ask("what about sick leave?")

    latest = prompts_asking_for(fake_language_model, "QueryUnderstanding")[-1]
    assert "What is the carry over limit?" in latest
    assert "Carry-over is capped at 10 working days." in latest
    # The message being judged comes last, after what was said before it.
    assert latest.index("What is the carry over limit?") < latest.index("what about sick leave?")


def test_the_step_that_rewrites_a_follow_up_is_given_the_previous_turn(
    ask, script_understanding, script_routing, script_decomposition, fake_language_model
):
    """
    The defect this whole change exists for. The rewriting step was told to resolve
    references to earlier turns and handed nothing to resolve them against.
    """
    script_understanding()
    script_routing(required_evidence="policy")
    fake_language_model.reply_to_plain_call("Carry-over is capped at 10 working days.")
    ask("What is the carry over limit?")

    script_understanding(needs_rewrite=True)
    script_decomposition("sick leave entitlement")
    ask("what about sick leave?")

    rewrite_prompt = prompts_asking_for(fake_language_model, "DecomposedQuery")[-1]
    assert "What is the carry over limit?" in rewrite_prompt
    assert 'Prepare this for policy search: "what about sick leave?"' in rewrite_prompt


def test_the_answer_is_never_shown_an_earlier_turn(
    ask, script_understanding, script_routing, fake_language_model
):
    """
    The guardrail. Every figure in an answer is checked against the evidence retrieved
    for this question, so a number carried over from an earlier answer would be rejected
    and a good answer would become a refusal. The answer step is kept on evidence alone.
    """
    script_understanding()
    script_routing(required_evidence="policy")
    fake_language_model.reply_to_plain_call("Carry-over is capped at 10 working days.")
    ask("What is the carry over limit?")
    ask("What is the carry over limit?")

    for instructions in system_prompts_for_the_answer(fake_language_model):
        assert TRANSCRIPT_OPENING not in instructions
        assert "Turn 1 — you answered" not in instructions


def test_a_greeting_is_not_remembered(
    ask, script_understanding, script_routing, fake_language_model
):
    """Its fixed reply is a menu of topics, which would read as a list of instructions."""
    script_understanding(intent="greeting", confidence=0.99)

    greeting = ask("Hello")

    assert greeting["answer_status"] == AnswerStatus.VERIFIED
    # Never written at all, so a conversation that has only been greeted has no
    # transcript rather than an empty one.
    assert greeting.get("remembered_turns", []) == []

    script_understanding()
    script_routing(required_evidence="policy")
    fake_language_model.reply_to_plain_call("Carry-over is capped at 10 working days.")
    ask("What is the carry over limit?")

    assert TRANSCRIPT_OPENING not in prompts_asking_for(
        fake_language_model, "QueryUnderstanding"
    )[-1]


def test_a_refused_question_is_remembered(
    ask, script_understanding, script_routing, fake_language_model
):
    """"What's the weather?" then "and tomorrow?" only makes sense with the first kept."""
    script_understanding(intent="out_of_scope", confidence=0.97)
    result = ask("What is the weather in Dubai?")

    assert [turn["question"] for turn in result["remembered_turns"]] == [
        "What is the weather in Dubai?"
    ]


def test_a_clarified_question_is_remembered_with_the_reply_folded_in(
    conversation_workflow, start_turn, saved_conversation, script_understanding,
    script_routing, fake_language_model,
):
    """The employee's clarification is usually the very detail a follow-up refers to."""
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

    assert resumed["remembered_turns"][0]["question"] == "How many leaves can I take? (annual)"


def test_only_the_last_few_turns_are_carried_forward(
    ask, script_understanding, script_routing, fake_language_model
):
    script_understanding()
    script_routing(required_evidence="policy")
    fake_language_model.reply_to_plain_call("Carry-over is capped at 10 working days.")

    for question_number in range(TURNS_WORTH_REMEMBERING + 2):
        result = ask(f"What is rule {question_number}?")

    assert len(result["remembered_turns"]) == TURNS_WORTH_REMEMBERING
    assert result["remembered_turns"][-1]["question"] == (
        f"What is rule {TURNS_WORTH_REMEMBERING + 1}?"
    )


def test_the_writer_is_told_the_question_that_was_worked_out(
    ask, script_understanding, script_routing, script_decomposition, fake_language_model
):
    """
    The reported failure. "okay, do the calculation" was resolved correctly, the right
    policy section was retrieved — and then the step that writes the reply was handed the
    evidence and those four words, with the resolved question nowhere in the prompt. It
    asked, reasonably, which calculation.
    """
    script_understanding()
    script_routing(required_evidence="policy")
    fake_language_model.reply_to_plain_call("Fifteen days at full pay, then half pay.")
    ask("If I am off sick for 50 days, how much is paid?")

    script_understanding(needs_rewrite=True)
    script_decomposition("calculate sick leave pay for 50 days of absence")
    ask("okay, do the calculation")

    written_from = [
        call["messages"][1]["content"]
        for call in fake_language_model.recorded_calls
        if call["response_format"] is None
    ][-1]
    assert "okay, do the calculation" in written_from, "the employee's own words are kept"
    assert "calculate sick leave pay for 50 days of absence" in written_from


def test_the_writer_is_given_the_question_but_still_not_the_conversation(
    ask, script_understanding, script_routing, script_decomposition, fake_language_model
):
    """
    The line this change walks. This turn's resolved question goes to the writer; the
    earlier turns do not. Figures may only come from evidence retrieved now, which is
    what the check at the end depends on.
    """
    script_understanding()
    script_routing(required_evidence="policy")
    fake_language_model.reply_to_plain_call("Carry-over is capped at 10 working days.")
    ask("What is the carry over limit?")

    script_understanding(needs_rewrite=True)
    script_decomposition("sick leave entitlement")
    ask("and sick leave?")

    for message in [
        content
        for call in fake_language_model.recorded_calls
        if call["response_format"] is None
        for content in (call["messages"][0]["content"], call["messages"][1]["content"])
    ]:
        assert TRANSCRIPT_OPENING not in message
        assert "Turn 1 — you answered" not in message
