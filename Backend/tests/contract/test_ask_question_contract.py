"""
Pins the JSON contract of POST /api/v1/hcs01/query.

The React frontend reads these exact keys. Any refactor that changes a key name, a
type, or the clarification pair invariant must fail here rather than silently render
blank bubbles in the browser.

Reference: Frontend/src/lib/api/types.ts and Frontend/src/hooks/useConcierge.ts
"""

import pytest

pytestmark = pytest.mark.contract

QUERY_ENDPOINT = "/api/v1/hcs01/query"

# Every key the frontend's ChatResponse type declares.
EXPECTED_ANSWER_KEYS = {
    "answer",
    "sources",
    "conversation_id",
    "employee_profile",
    "target_language",
    "latency_ms",
    "tokens_used",
    "intent",
    "rewritten_query",
    "confidence_score",
    "original_question",
    "clarifying_question",
    "is_awaiting_clarification",
}

# Every key the frontend's PolicySource type reads off a citation.
EXPECTED_SOURCE_KEYS = {
    "id",
    "title",
    "source",
    "source_type",
    "table_name",
    "section",
    "page_number",
    "score",
    "language",
    "snippet",
    "url",
    "pdf_url",
    "has_image",
}


def script_an_in_scope_question(fake_language_model, answer_text="You have 25 working days."):
    """
    Script both the old and the new vocabularies.

    These assertions are about the JSON the browser receives, which must be identical
    whichever path produced it, so the same test covers both.
    """
    fake_language_model.reply_to_structured_call(
        "ClassifierOutput",
        {"intent": "in_scope", "confidence": 0.95, "reasoning": "Asks about leave entitlement."},
    )
    fake_language_model.reply_to_structured_call(
        "QueryUnderstanding",
        {
            "intent": "hr_question",
            "confidence": 0.95,
            "needs_clarification": False,
            "missing_information": [],
            "needs_rewrite": True,
            "reasoning": "Asks about leave entitlement.",
        },
    )
    fake_language_model.reply_to_structured_call(
        "DecomposedQuery",
        {"subqueries": ["annual leave entitlement days per year"], "reasoning": "One question."},
    )
    fake_language_model.reply_to_structured_call(
        "SourceRoutingDecision",
        {
            "required_evidence": "both",
            "requested_hr_data_fields": ["annual_leave_balance"],
            "reason": "Their own balance, read against the rules.",
        },
    )
    fake_language_model.reply_to_plain_call(answer_text)


def test_in_scope_question_returns_the_expected_keys(api_client, fake_language_model, stub_policy_search_service):
    script_an_in_scope_question(fake_language_model)

    response = api_client.post(
        QUERY_ENDPOINT,
        json={
            "message": "How many annual leave days do I get?",
            "query": "How many annual leave days do I get?",
            "employee_id": "EMP001",
            "conversation_id": None,
            "original_question": None,
            "user_clarification": None,
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == EXPECTED_ANSWER_KEYS

    assert isinstance(body["answer"], str) and body["answer"]
    assert isinstance(body["sources"], list)
    assert isinstance(body["conversation_id"], str) and body["conversation_id"]
    assert isinstance(body["is_awaiting_clarification"], bool)
    assert isinstance(body["latency_ms"], int)
    assert isinstance(body["tokens_used"], int)


def test_every_citation_carries_the_keys_the_frontend_reads(api_client, fake_language_model, stub_policy_search_service):
    script_an_in_scope_question(fake_language_model)

    response = api_client.post(
        QUERY_ENDPOINT, json={"message": "How many annual leave days do I get?"}
    )
    sources = response.json()["sources"]

    assert sources, "an in-scope answer must cite at least the employee database record"
    for source in sources:
        assert set(source) == EXPECTED_SOURCE_KEYS
        assert source["source_type"] in {"policy", "database"}


def test_citation_score_stays_between_zero_and_one(api_client, fake_language_model, stub_policy_search_service):
    """SourceCitations.tsx multiplies score by 100 to render a percentage."""
    script_an_in_scope_question(fake_language_model)

    response = api_client.post(
        QUERY_ENDPOINT, json={"message": "How many annual leave days do I get?"}
    )

    for source in response.json()["sources"]:
        assert 0.0 <= source["score"] <= 1.0, f"score out of range: {source['score']}"


def test_confidence_score_stays_between_zero_and_one(api_client, fake_language_model, stub_policy_search_service):
    """ChatPanel.tsx renders confidence_score as a percentage badge."""
    script_an_in_scope_question(fake_language_model)

    response = api_client.post(
        QUERY_ENDPOINT, json={"message": "How many annual leave days do I get?"}
    )

    assert 0.0 <= response.json()["confidence_score"] <= 1.0


def test_greeting_is_reported_with_the_intent_the_frontend_matches_on(
    api_client, fake_language_model
):
    """ChatPanel.tsx compares intent against the literal string "greeting"."""
    fake_language_model.reply_to_structured_call(
        "ClassifierOutput",
        {"intent": "greeting", "confidence": 0.99, "reasoning": "A greeting."},
    )
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

    response = api_client.post(QUERY_ENDPOINT, json={"message": "Hello"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["intent"] == "greeting"
    assert body["is_awaiting_clarification"] is False


def test_out_of_scope_is_reported_with_the_intent_the_frontend_matches_on(
    api_client, fake_language_model
):
    fake_language_model.reply_to_structured_call(
        "ClassifierOutput",
        {"intent": "not_in_scope", "confidence": 0.97, "reasoning": "Unrelated to HR policy."},
    )
    fake_language_model.reply_to_structured_call(
        "QueryUnderstanding",
        {
            "intent": "out_of_scope",
            "confidence": 0.97,
            "needs_clarification": False,
            "missing_information": [],
            "needs_rewrite": False,
            "reasoning": "Unrelated to HR policy.",
        },
    )

    response = api_client.post(QUERY_ENDPOINT, json={"message": "What is the weather today?"})

    assert response.status_code == 200, response.text
    assert response.json()["intent"] == "not_in_scope"


def test_clarification_sets_the_flag_and_the_original_question_together(
    api_client, fake_language_model
):
    """
    useConcierge.ts requires `is_awaiting_clarification && original_question` to both be
    truthy before it will enter clarification mode. If either is missing the UI silently
    drops back to ready and the next turn loses its context.
    """
    fake_language_model.reply_to_structured_call(
        "ClassifierOutput",
        {"intent": "ambiguous", "confidence": 0.55, "reasoning": "Leave type is unclear."},
    )
    fake_language_model.reply_to_structured_call(
        "QueryUnderstanding",
        {
            "intent": "hr_question",
            "confidence": 0.55,
            "needs_clarification": True,
            "missing_information": ["which kind of leave"],
            "needs_rewrite": False,
            "reasoning": "Leave type is unclear.",
        },
    )
    fake_language_model.reply_to_structured_call(
        "ClarifyingQuestionOutput",
        {
            "clarifying_question": "Which type of leave did you mean?",
            "missing_info": "leave type",
        },
    )
    fake_language_model.reply_to_structured_call(
        "ClarificationQuestion",
        {
            "clarification_question": "Which type of leave did you mean?",
            "missing_information": "leave type",
        },
    )
    response = api_client.post(QUERY_ENDPOINT, json={"message": "How many leaves can I take?"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["is_awaiting_clarification"] is True
    assert body["original_question"], "the frontend needs this to send the next turn"
    assert body["intent"] == "ambiguous"


def test_an_empty_question_is_rejected(api_client):
    response = api_client.post(QUERY_ENDPOINT, json={"message": "   "})
    assert response.status_code == 422


def test_unknown_request_fields_do_not_break_the_endpoint(api_client, fake_language_model, stub_policy_search_service):
    """A future frontend field must not turn into a 422 for everybody."""
    script_an_in_scope_question(fake_language_model)

    response = api_client.post(
        QUERY_ENDPOINT,
        json={"message": "How many annual leave days do I get?", "a_field_from_the_future": True},
    )

    assert response.status_code == 200, response.text
