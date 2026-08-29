"""
The parts of a split question gather at the same time, not one after another.

This is the reason each part is sent off with `Send` rather than looped over inside one
step. Searching is the only real waiting in a turn, so a message asking three things
should cost one search's worth of it — otherwise splitting a question would make the
employee wait three times as long for the same answer.
"""

import time

import pytest

ONE_SEARCH_TAKES = 0.3


@pytest.fixture(autouse=True)
def _needs_an_employee_record(temporary_database):
    pass


@pytest.fixture
def slow_policy_search(monkeypatch):
    """A search that takes long enough for running three of them in series to show."""
    from app.domain.policy_passage import PolicyPassage
    from app.workflow.nodes import gather_evidence

    def search(query, top_k=5, language=None):
        time.sleep(ONE_SEARCH_TAKES)
        # Two passages, so the thin-results retry in another language never fires and
        # this fixture times exactly one search per part.
        return [
            PolicyPassage(
                text=f"Carry-over is capped at 10 working days. (extract {number})",
                policy_code="HC-PC-001",
                title="Annual Leave Policy",
                section=f"Section 1.{number}",
                page_number=1,
                pdf_url="/api/v1/hcs01/policies/pdf/01_annual_leave_policy.pdf",
                language="en",
                has_image=False,
                relevance_score=0.9,
                semantic_similarity=0.78,
            )
            for number in (1, 2)
        ]

    monkeypatch.setattr(gather_evidence, "search_policies", search)


def test_three_parts_cost_one_search_worth_of_waiting(
    slow_policy_search, conversation_workflow, start_turn, saved_conversation,
    script_understanding, script_decomposition, script_routing, fake_language_model,
):
    script_understanding(is_multi_question=True)
    script_decomposition(
        "annual leave entitlement",
        "annual leave carry over limit",
        "annual leave notice period",
    )
    script_routing(required_evidence="policy")
    fake_language_model.reply_to_plain_call("Carry-over is capped at 10 working days.")

    started_at = time.time()
    result = conversation_workflow.invoke(
        start_turn("What do I get, how much carries over, and how much notice do I give?"),
        saved_conversation,
    )
    elapsed = time.time() - started_at

    assert len(result["subquery_statuses"]) == 3
    assert elapsed < ONE_SEARCH_TAKES * 2, (
        f"three parts took {elapsed:.2f}s, which is long enough that they ran one after "
        f"another rather than together"
    )


def test_an_extract_found_for_two_parts_is_only_cited_once(
    slow_policy_search, conversation_workflow, start_turn, saved_conversation,
    script_understanding, script_decomposition, script_routing, fake_language_model,
):
    """Both parts search the same policy here, so both find the same two extracts."""
    script_understanding(is_multi_question=True)
    script_decomposition("annual leave entitlement", "annual leave carry over limit")
    script_routing(required_evidence="policy")
    fake_language_model.reply_to_plain_call("Carry-over is capped at 10 working days.")

    result = conversation_workflow.invoke(
        start_turn("What do I get, and how much carries over?"), saved_conversation
    )

    sections = [citation["section"] for citation in result["citations"]]
    assert sections == ["Section 1.1", "Section 1.2"], "each extract is worth citing once"
