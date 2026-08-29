"""
Defect 6: a failing language model used to look like a working one.

Every model call was wrapped in an `except` that fell back to "this is an in-scope
question, confidence 0.5". So when the model was unreachable the system did not fail — it
classified nothing, and sent every question, including ones it should refuse, straight
into retrieval.

The damage was measurable. Running the old router's own test suite with no API key
reported "6 passed, 13 failed", and the 6 that passed were exactly the 6 cases expecting
"in_scope". Not one classification had actually happened.
"""

import pytest

from app.core.errors import LanguageModelUnavailableError


@pytest.fixture(autouse=True)
def _employee_record(temporary_database):
    """The workflow reads the employee's record before it reads the question."""


def test_an_unreachable_model_raises_instead_of_inventing_a_reading(
    conversation_workflow, start_turn, saved_conversation, fake_language_model
):
    fake_language_model.fail_every_call_with(RuntimeError("the model is unreachable"))

    with pytest.raises(LanguageModelUnavailableError):
        conversation_workflow.invoke(
            start_turn("What is the weather in Dubai?"), saved_conversation
        )


def test_an_unreachable_model_does_not_let_an_out_of_scope_question_through(
    conversation_workflow, start_turn, saved_conversation, fake_language_model
):
    """
    The point of the change. This question must never be answered, and while the model is
    unreachable it cannot be answered at all — which is the honest outcome.
    """
    fake_language_model.fail_every_call_with(RuntimeError("the model is unreachable"))

    with pytest.raises(LanguageModelUnavailableError):
        conversation_workflow.invoke(
            start_turn("Write me a Python script to scrape a website"), saved_conversation
        )


def test_a_reply_that_does_not_fit_the_expected_shape_is_a_failure(
    conversation_workflow, start_turn, saved_conversation, fake_language_model, monkeypatch
):
    """A malformed reply must not be silently replaced by a default reading either."""
    from app.workflow import language_model_client

    class ReplyThatIsNotJson:
        choices = [type("Choice", (), {"message": type("Message", (), {"content": "not json"})()})()]
        usage = None

    monkeypatch.setattr(
        language_model_client, "_request_completion", lambda **kwargs: ReplyThatIsNotJson()
    )

    with pytest.raises(LanguageModelUnavailableError):
        conversation_workflow.invoke(start_turn("How much leave do I have?"), saved_conversation)
