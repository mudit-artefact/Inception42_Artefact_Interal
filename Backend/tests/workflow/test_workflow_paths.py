"""
One test per route through the workflow, matching the designed flow.

Every language-model call is scripted, and the policy search is stubbed, so these run
offline and cost nothing.
"""

import pytest

from app.domain.enums import AnswerStatus


@pytest.fixture(autouse=True)
def _use_canned_passages(stub_policy_search_service, temporary_database):
    """Every path here needs an employee record and canned policy extracts."""


def test_a_greeting_is_answered_by_name_without_gathering_evidence(
    conversation_workflow, start_turn, saved_conversation, script_understanding, fake_language_model
):
    script_understanding(intent="greeting", confidence=0.99)

    result = conversation_workflow.invoke(start_turn("Hello"), saved_conversation)

    assert result["answer_status"] == AnswerStatus.VERIFIED
    assert "Ahmed" in result["final_answer"] or "Hello" in result["final_answer"]
    assert result["citations"] == []
    # Reading the question is the only call a greeting should cost.
    assert fake_language_model.call_count == 1


def test_an_out_of_scope_question_is_declined(
    conversation_workflow, start_turn, saved_conversation, script_understanding
):
    script_understanding(intent="out_of_scope", confidence=0.97)

    result = conversation_workflow.invoke(
        start_turn("What is the weather in Dubai?"), saved_conversation
    )

    assert result["answer_status"] == AnswerStatus.REFUSED
    assert result["fallback_reason"] == "out_of_scope"
    assert result["citations"] == []


def test_a_policy_question_searches_the_documents_only(
    conversation_workflow, start_turn, saved_conversation, script_understanding, script_routing,
    fake_language_model,
):
    script_understanding()
    script_routing(required_evidence="policy")
    fake_language_model.reply_to_plain_call("Carry-over is capped at 10 working days.")

    result = conversation_workflow.invoke(
        start_turn("What is the carry over limit?"), saved_conversation
    )

    assert result["required_evidence"] == "policy"
    assert result["policy_passages"] == [], "gathered evidence is cleared once the turn ends"
    assert result["answer_status"] == AnswerStatus.VERIFIED
    assert any(citation["source_type"] == "policy" for citation in result["citations"])


def test_a_personal_question_reads_the_employee_record_only(
    conversation_workflow, start_turn, saved_conversation, script_understanding, script_routing,
    fake_language_model,
):
    script_understanding()
    script_routing(required_evidence="hr_data", fields=["line_manager"])
    fake_language_model.reply_to_plain_call("Your line manager is Khalid Al Suwaidi.")

    result = conversation_workflow.invoke(
        start_turn("Who is my line manager?"), saved_conversation
    )

    assert result["required_evidence"] == "hr_data"
    # What the model named, plus what the words of the question point at. Routing adds
    # rather than replaces: a model that names one field short of what the answer needs
    # is the common failure, and it produced confidently wrong entitlements.
    assert "line_manager" in result["requested_hr_data_fields"]
    assert "manager_history" in result["requested_hr_data_fields"]
    assert result["answer_status"] == AnswerStatus.VERIFIED
    assert any(citation["source_type"] == "database" for citation in result["citations"])


def test_a_question_needing_both_gathers_both_kinds_of_evidence(
    conversation_workflow, start_turn, saved_conversation, script_understanding, script_routing,
    fake_language_model,
):
    script_understanding()
    script_routing(required_evidence="both", fields=["annual_leave_balance"])
    fake_language_model.reply_to_plain_call(
        "You have 18 days remaining, and carry-over is capped at 10 working days."
    )

    result = conversation_workflow.invoke(
        start_turn("Do I have enough leave for a two week holiday?"), saved_conversation
    )

    assert result["required_evidence"] == "both"
    citation_kinds = {citation["source_type"] for citation in result["citations"]}
    assert citation_kinds == {"policy", "database"}


def test_a_question_that_cannot_be_served_falls_back_to_a_person(
    conversation_workflow, start_turn, saved_conversation, script_understanding, script_routing
):
    # Low confidence, so the guard against over-refusing does not step in.
    script_understanding(confidence=0.4)
    script_routing(required_evidence="unsupported")

    result = conversation_workflow.invoke(
        start_turn("Can you dispute my payroll deduction with finance?"), saved_conversation
    )

    assert result["answer_status"] == AnswerStatus.SAFE_FALLBACK
    assert result["fallback_reason"] == "needs_human"


def test_an_answer_with_an_invented_figure_is_not_shown(
    conversation_workflow, start_turn, saved_conversation, script_understanding, script_routing,
    fake_language_model,
):
    """
    The evidence says 10 days of carry-over. The model claims 30. That answer must not
    reach the employee.
    """
    script_understanding()
    script_routing(required_evidence="policy")
    fake_language_model.reply_to_plain_call("You may carry over 30 working days.")

    result = conversation_workflow.invoke(
        start_turn("What is the carry over limit?"), saved_conversation
    )

    assert result["answer_verdict"] == "invalid"
    assert result["answer_status"] == AnswerStatus.SAFE_FALLBACK
    assert "30 working days" in result["unsupported_claims"]
    assert "people@hcservices.ae" in result["final_answer"]


def test_a_rejected_answer_still_shows_the_extracts_that_were_found(
    conversation_workflow, start_turn, saved_conversation, script_understanding, script_routing,
    fake_language_model,
):
    """An over-cautious check should leave the employee something to read, not nothing."""
    script_understanding()
    script_routing(required_evidence="policy")
    fake_language_model.reply_to_plain_call("You may carry over 30 working days.")

    result = conversation_workflow.invoke(
        start_turn("What is the carry over limit?"), saved_conversation
    )

    assert result["citations"], "the retrieved extracts are still worth showing"


def test_a_question_needing_rewording_is_reworded_before_searching(
    conversation_workflow, start_turn, saved_conversation, script_understanding, script_routing,
    script_decomposition, fake_language_model,
):
    script_understanding(needs_rewrite=True)
    script_decomposition("sick leave medical certificate rules")
    script_routing(required_evidence="policy")
    fake_language_model.reply_to_plain_call("A certificate is required after four days.")

    result = conversation_workflow.invoke(start_turn("what about MC?"), saved_conversation)

    assert result["retrieval_query"] == "sick leave medical certificate rules"
    assert result["subqueries"] == ["sick leave medical certificate rules"]


# ── A message that asks more than one thing ─────────────────────────────────


def test_a_message_asking_two_things_is_split_and_each_part_is_routed_on_its_own(
    conversation_workflow, start_turn, saved_conversation, script_understanding,
    script_decomposition, script_routing_per_part, fake_language_model,
):
    """The whole point of splitting: one message, two parts, two different sources."""
    script_understanding(is_multi_question=True)
    script_decomposition(
        "annual leave carry over limit", "who is my line manager"
    )
    script_routing_per_part(("policy", []), ("hr_data", ["line_manager"]))
    fake_language_model.reply_to_plain_call(
        "Carry-over is capped at 10 working days, and your line manager is Khalid Al Suwaidi."
    )

    result = conversation_workflow.invoke(
        start_turn("What is the carry over limit and who is my manager?"), saved_conversation
    )

    assert [plan["required_evidence"] for plan in result["subquery_plans"]] == [
        "policy",
        "hr_data",
    ]
    # Both parts were served, so the turn as a whole needed both kinds of evidence.
    assert result["required_evidence"] == "both"
    assert result["answer_status"] == AnswerStatus.VERIFIED
    assert {citation["source_type"] for citation in result["citations"]} == {"policy", "database"}


def test_every_part_of_a_split_question_is_put_in_front_of_the_model(
    conversation_workflow, start_turn, saved_conversation, script_understanding,
    script_decomposition, script_routing, fake_language_model,
):
    script_understanding(is_multi_question=True)
    script_decomposition("annual leave entitlement", "annual leave carry over limit")
    script_routing(required_evidence="policy")
    fake_language_model.reply_to_plain_call("You accrue 25 working days and may carry over 10.")

    conversation_workflow.invoke(
        start_turn("How much leave do I get, and how much can I carry over?"), saved_conversation
    )

    instructions = [
        call["messages"][0]["content"]
        for call in fake_language_model.recorded_calls
        if call["response_format"] == "AnswerWithWorking"
    ][0]
    assert 'PART 1 — "annual leave entitlement"' in instructions
    assert 'PART 2 — "annual leave carry over limit"' in instructions


def test_a_part_that_cannot_be_served_does_not_stop_the_others_being_answered(
    conversation_workflow, start_turn, saved_conversation, script_understanding,
    script_decomposition, script_routing_per_part, fake_language_model,
):
    """
    The old workflow answered one question per message. Half an answer is exactly what
    the split is for: serve the part that can be served, and say so about the rest.
    """
    script_understanding(confidence=0.4, is_multi_question=True)
    script_decomposition("annual leave carry over limit", "dispute my payroll deduction")
    script_routing_per_part(("policy", []), ("unsupported", []))
    fake_language_model.reply_to_plain_call(
        "Carry-over is capped at 10 working days. I cannot help with the payroll "
        "deduction — please contact People & Culture at people@hcservices.ae."
    )

    result = conversation_workflow.invoke(
        start_turn("What is the carry over limit, and can you dispute my payroll deduction?"),
        saved_conversation,
    )

    assert [status["has_evidence"] for status in result["subquery_statuses"]] == [True, False]
    assert result["answer_status"] == AnswerStatus.PARTIAL
    assert result["citations"], "the part that was served still shows its extracts"


def test_a_split_question_where_no_part_can_be_served_falls_back_to_a_person(
    conversation_workflow, start_turn, saved_conversation, script_understanding,
    script_decomposition, script_routing,
):
    script_understanding(confidence=0.4, is_multi_question=True)
    script_decomposition("dispute my payroll deduction", "another employee's salary")
    script_routing(required_evidence="unsupported")

    result = conversation_workflow.invoke(
        start_turn("Can you dispute my deduction and tell me what Sara earns?"),
        saved_conversation,
    )

    assert result["required_evidence"] == "unsupported"
    assert result["answer_status"] == AnswerStatus.SAFE_FALLBACK
    assert result["fallback_reason"] == "needs_human"


def test_one_turns_evidence_is_not_carried_into_the_next_question(
    conversation_workflow, start_turn, saved_conversation, script_understanding,
    script_routing, fake_language_model,
):
    """
    The parts of a turn are gathered by appending, so a turn that did not clear them
    would let the next question be answered from the last question's extracts.
    """
    script_understanding()
    script_routing(required_evidence="policy")
    fake_language_model.reply_to_plain_call("Carry-over is capped at 10 working days.")

    conversation_workflow.invoke(start_turn("What is the carry over limit?"), saved_conversation)
    second = conversation_workflow.invoke(
        start_turn("What is the carry over limit?"), saved_conversation
    )

    assert len(second["subquery_statuses"]) == 1
    assert second["subquery_evidence"] == []
