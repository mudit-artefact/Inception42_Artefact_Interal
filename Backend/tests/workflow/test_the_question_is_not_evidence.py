"""
A number the employee typed is not proof of itself.

The evidence shown to the model names the question each extract was gathered for, so the
model can tell the parts of a split message apart. That same string used to be what every
figure in the answer was checked against — so a number inside the question counted as
evidence for itself. Ask "can I carry over 77 days?", get "yes, 77 days", and the check
passed on the strength of the 77 in the question.
"""

import pytest

from app.domain.enums import AnswerStatus


@pytest.fixture(autouse=True)
def _canned_evidence(stub_policy_search_service, temporary_database):
    """The canned extracts mention 25 days of leave and a 10-day carry-over cap."""


def test_a_figure_only_the_employee_typed_is_not_supported(
    conversation_workflow, start_turn, saved_conversation, script_understanding,
    script_routing, fake_language_model,
):
    script_understanding()
    script_routing(required_evidence="policy")
    # 77 appears in the question and in the answer, and in no extract.
    fake_language_model.reply_to_plain_call("Yes, you may carry over 77 days.")

    result = conversation_workflow.invoke(
        start_turn("Can I carry over 77 days?"), saved_conversation
    )

    assert result["answer_verdict"] == "invalid"
    assert "77 days" in result["unsupported_claims"]
    assert result["answer_status"] == AnswerStatus.SAFE_FALLBACK


def test_a_figure_the_extracts_state_is_still_supported(
    conversation_workflow, start_turn, saved_conversation, script_understanding,
    script_routing, fake_language_model,
):
    """The check must not have become so strict that a real answer cannot get through."""
    script_understanding()
    script_routing(required_evidence="policy")
    fake_language_model.reply_to_plain_call("Carry-over is capped at 10 working days.")

    result = conversation_workflow.invoke(
        start_turn("What is the carry over limit?"), saved_conversation
    )

    assert result["answer_verdict"] == "valid"
    assert result["answer_status"] == AnswerStatus.VERIFIED


def test_the_model_is_still_told_which_question_each_extract_answers(
    conversation_workflow, start_turn, saved_conversation, script_understanding,
    script_routing, fake_language_model,
):
    """
    Keeping questions out of the check must not take them away from the model, which
    needs them to know which part of a split message an extract belongs to.
    """
    script_understanding()
    script_routing(required_evidence="policy")
    fake_language_model.reply_to_plain_call("Carry-over is capped at 10 working days.")

    conversation_workflow.invoke(
        start_turn("What is the carry over limit?"), saved_conversation
    )

    instructions = [
        call["messages"][0]["content"]
        for call in fake_language_model.recorded_calls
        if call["response_format"] == "AnswerWithWorking"
    ][0]
    assert "What is the carry over limit?" in instructions
