"""
The clarification exchange, over HTTP, exactly as the browser performs it.

The browser sends a question, gets a question back, and sends the employee's reply as a
new request carrying the same conversation_id. The server must pick the conversation back
up on its own.
"""

import pytest

pytestmark = pytest.mark.contract

QUERY_ENDPOINT = "/api/v1/hcs01/query"


@pytest.fixture
def script_a_vague_then_clear_question(fake_language_model):
    fake_language_model.reply_to_structured_call(
        "QueryUnderstanding",
        {
            "intent": "hr_question",
            "confidence": 0.55,
            "needs_clarification": True,
            "missing_information": ["which kind of leave"],
            "needs_rewrite": False,
            "reasoning": "The kind of leave is not stated.",
        },
    )
    fake_language_model.reply_to_structured_call(
        "ClarificationQuestion",
        {
            "clarification_question": "Which type of leave did you mean?",
            "missing_information": "leave type",
        },
    )
    fake_language_model.reply_to_structured_call(
        "SourceRoutingDecision",
        {"required_evidence": "policy", "requested_hr_data_fields": [], "reason": "policy rules"},
    )
    fake_language_model.reply_to_plain_call("Carry-over is capped at 10 working days.")


def test_the_first_turn_asks_the_employee_something_back(
    api_client, script_a_vague_then_clear_question, stub_policy_search_service
):
    response = api_client.post(
        QUERY_ENDPOINT,
        json={"message": "How many leaves can I take?", "conversation_id": "conversation-a"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["is_awaiting_clarification"] is True
    assert body["original_question"] == "How many leaves can I take?"
    assert body["answer"] == "Which type of leave did you mean?"
    assert body["conversation_id"] == "conversation-a"


def test_the_second_turn_continues_where_the_first_left_off(
    api_client, script_a_vague_then_clear_question, stub_policy_search_service
):
    api_client.post(
        QUERY_ENDPOINT,
        json={"message": "How many leaves can I take?", "conversation_id": "conversation-b"},
    )

    second_response = api_client.post(
        QUERY_ENDPOINT,
        json={"message": "annual leave", "conversation_id": "conversation-b"},
    )

    assert second_response.status_code == 200, second_response.text
    body = second_response.json()
    assert body["is_awaiting_clarification"] is False
    assert "10 working days" in body["answer"]


def test_the_exchange_survives_the_browser_forgetting_everything(
    api_client, script_a_vague_then_clear_question, stub_policy_search_service
):
    """
    The pause is held by the server, so a page reload no longer breaks it.

    Previously the pending question lived only in the page's memory. After a reload the
    interface still showed its "clarification needed" badge, but the next message went out
    with no clarification context at all and the exchange silently fell apart.
    """
    api_client.post(
        QUERY_ENDPOINT,
        json={"message": "How many leaves can I take?", "conversation_id": "conversation-c"},
    )

    # A reloaded page sends only what it stored: the conversation's id and the new text.
    response_after_reload = api_client.post(
        QUERY_ENDPOINT,
        json={
            "message": "annual leave",
            "conversation_id": "conversation-c",
            "original_question": None,
            "user_clarification": None,
        },
    )

    assert response_after_reload.status_code == 200, response_after_reload.text
    assert response_after_reload.json()["is_awaiting_clarification"] is False
    assert "10 working days" in response_after_reload.json()["answer"]


def test_a_different_conversation_is_unaffected_by_a_pending_question(
    api_client, script_a_vague_then_clear_question, stub_policy_search_service, fake_language_model
):
    api_client.post(
        QUERY_ENDPOINT,
        json={"message": "How many leaves can I take?", "conversation_id": "conversation-d"},
    )

    # A separate conversation, which happens to be a greeting.
    fake_language_model.reply_to_structured_call(
        "QueryUnderstanding",
        {
            "intent": "greeting",
            "confidence": 0.99,
            "needs_clarification": False,
            "missing_information": [],
            "needs_rewrite": False,
            "reasoning": "A greeting.",
        },
    )
    other_response = api_client.post(
        QUERY_ENDPOINT, json={"message": "Hello", "conversation_id": "conversation-e"}
    )

    assert other_response.json()["intent"] == "greeting"
    assert other_response.json()["is_awaiting_clarification"] is False
