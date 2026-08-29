"""
A conversation belongs to the employee who started it.

Nothing here authenticates anybody — `employee_id` is still whatever the caller sends.
What this stops is one employee reaching another employee's conversation by naming it,
which matters more now than it did: a conversation carries what was said in it, so
attaching to somebody else's reads their questions and answers rather than, at worst,
their one pending clarification.
"""

import pytest

pytestmark = pytest.mark.contract

QUERY_ENDPOINT = "/api/v1/hcs01/query"


@pytest.fixture
def script_an_answerable_question(fake_language_model):
    fake_language_model.reply_to_structured_call(
        "QueryUnderstanding",
        {
            "intent": "hr_question",
            "confidence": 0.95,
            "needs_clarification": False,
            "missing_information": [],
            "needs_rewrite": False,
            "is_multi_question": False,
            "reasoning": "Asks about carry-over.",
        },
    )
    fake_language_model.reply_to_structured_call(
        "SourceRoutingDecision",
        {"required_evidence": "policy", "requested_hr_data_fields": [], "reason": "policy rules"},
    )
    fake_language_model.reply_to_plain_call("Carry-over is capped at 10 working days.")


def test_another_employee_cannot_attach_to_a_conversation(
    api_client, script_an_answerable_question, stub_policy_search_service
):
    started = api_client.post(
        QUERY_ENDPOINT,
        json={"message": "What is the carry over limit?", "employee_id": "EMP001"},
    )
    conversation_id = started.json()["conversation_id"]

    intruder = api_client.post(
        QUERY_ENDPOINT,
        json={
            "message": "What did they just ask?",
            "employee_id": "EMP002",
            "conversation_id": conversation_id,
        },
    )

    assert intruder.status_code == 200, intruder.text
    assert intruder.json()["conversation_id"] != conversation_id, (
        "the intruder was given a conversation of their own, not the one they named"
    )
    assert intruder.json()["employee_profile"]["user_id"] == "EMP002"


def test_the_employee_who_started_a_conversation_keeps_it(
    api_client, script_an_answerable_question, stub_policy_search_service
):
    started = api_client.post(
        QUERY_ENDPOINT,
        json={"message": "What is the carry over limit?", "employee_id": "EMP001"},
    )
    conversation_id = started.json()["conversation_id"]

    continued = api_client.post(
        QUERY_ENDPOINT,
        json={
            "message": "What is the carry over limit?",
            "employee_id": "EMP001",
            "conversation_id": conversation_id,
        },
    )

    assert continued.json()["conversation_id"] == conversation_id


def test_a_conversation_nobody_has_used_is_nobodys_to_lose(
    api_client, script_an_answerable_question, stub_policy_search_service
):
    """A caller naming a conversation that does not exist yet simply gets it."""
    response = api_client.post(
        QUERY_ENDPOINT,
        json={
            "message": "What is the carry over limit?",
            "employee_id": "EMP002",
            "conversation_id": "conversation-never-used-before",
        },
    )

    assert response.json()["conversation_id"] == "conversation-never-used-before"


def test_a_named_conversation_is_not_guessable(api_client):
    """
    The name used to be the millisecond clock, so a conversation could be found by
    counting — and two started in the same millisecond shared one thread.
    """
    from app.core.conversation_identifier import create_conversation_identifier

    names = {create_conversation_identifier() for _ in range(200)}

    assert len(names) == 200
