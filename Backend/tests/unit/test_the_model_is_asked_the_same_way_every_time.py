"""
Every call to the model carries a temperature, and it is the one from settings.

None of the five model calls in a turn wants variety. Four are classifications — what is
being asked, how it splits, which sources it needs — and the fifth reads figures out of
documents. All five ran at the provider's default until this test existed, for two reasons
that were each invisible on their own:

  * temperature was only ever set on the prose call, and the answer step stopped using
    that call when it moved to a structured reply
  * a helper excluded Gemini entirely, on the grounds that Gemini rejects the parameter.
    Gemini accepts it. The belief outlived whatever made it true.

The result was a benchmark whose score moved by three or four points between identical
runs, which made every measurement taken against it an argument rather than a fact.
"""

import pytest

from app.core.settings import settings
from app.workflow import language_model_client
from app.workflow.structured_outputs import QueryUnderstanding


@pytest.fixture
def recorded_requests(monkeypatch):
    """Every request the client would have sent."""
    sent: list[dict] = []

    class Reply:
        class Choice:
            class Message:
                content = (
                    '{"intent":"hr_question","confidence":0.9,"needs_clarification":false,'
                    '"missing_information":[],"needs_rewrite":false,'
                    '"is_multi_question":false,"reasoning":""}'
                )

            message = Message()

        choices = [Choice()]
        usage = None

    def capture(**keyword_arguments):
        sent.append(keyword_arguments)
        return Reply()

    monkeypatch.setattr(language_model_client, "_request_completion", capture)
    return sent


def test_a_structured_call_carries_the_temperature(recorded_requests):
    """
    The one that mattered most and had it least.

    Reading a question, splitting it, routing it and writing the answer are all structured
    calls. This is four of the five.
    """
    language_model_client.generate_structured_output(
        messages=[{"role": "user", "content": "anything"}],
        output_model=QueryUnderstanding,
    )

    assert recorded_requests[0]["temperature"] == settings.llm_temperature


def test_a_prose_call_carries_the_temperature(recorded_requests):
    language_model_client.generate_text(messages=[{"role": "user", "content": "anything"}])

    assert recorded_requests[0]["temperature"] == settings.llm_temperature


def test_the_default_is_zero():
    """
    Anything above zero buys variety nobody asked for, at the cost of a benchmark that
    cannot be read. Raise it deliberately, in the environment, or not at all.
    """
    assert settings.llm_temperature == 0.0


def test_no_provider_is_excluded_from_having_one(recorded_requests, monkeypatch):
    """
    The exclusion was a name check against "gemini", and it silently disabled the setting
    for the only provider this system runs on.
    """
    monkeypatch.setattr(settings, "llm_model", "gemini/gemini-3.7-flash")

    language_model_client.generate_structured_output(
        messages=[{"role": "user", "content": "anything"}],
        output_model=QueryUnderstanding,
    )

    assert "temperature" in recorded_requests[0]
