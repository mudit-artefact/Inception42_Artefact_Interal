"""
A rule that has been replaced must not be handed over as though it still applied.

Every passage has always known whether it was current or superseded, and the evidence text
has always been stamped with it. None of that reached the ranking, so the two competed on
equal footing and the model chose — and it chose wrong: an employee was told the internet
allowance is AED 150, four months after it became 200.

The fix has to work in both directions, which is what makes it worth a test rather than a
line of code. A retired rule is the right answer to a question about the period it
governed, so demoting it there would be the same bug pointing the other way.

The candidates here are stubbed rather than retrieved. Real vectors cost money and the
test suite forbids them; fake ones rank arbitrarily, so asserting on which clause comes
back would be asserting on a hash. What is worth pinning is the penalty itself: given the
same two candidates, which one ends up on top.
"""

import pytest

from app.services import policy_search_service
from app.services.policy_search_service import _asks_about_a_past_period, search_policies


class Candidate:
    """One hit from the vector store, as the search service reads it."""

    def __init__(self, clause_id: str, status: str, text: str, score: float):
        self.score = score
        self.payload = {
            "clause_id": clause_id,
            "status": status,
            "text": text,
            "source": clause_id.split("§")[0],
            "section": clause_id.split("§")[-1],
        }


# The retired rule is deliberately given the better vector score and the better wording
# match, because that is the situation the penalty exists for. Left alone, it wins.
RETIRED_WINS_ON_MERIT = [
    Candidate("HC-PC-004§4.9", "superseded",
              "internet allowance of AED 150 for more than 8 remote days per month", 0.95),
    Candidate("HC-PC-004§4.6", "current",
              "internet allowance of AED 200 for more than 6 remote days per month", 0.90),
]


@pytest.fixture
def two_candidates(monkeypatch):
    monkeypatch.setattr(
        policy_search_service.policy_vector_repository,
        "ensure_collection_exists", lambda: None)
    monkeypatch.setattr(
        policy_search_service.policy_vector_repository,
        "count_indexed_passages", lambda: 2)
    monkeypatch.setattr(
        policy_search_service.policy_vector_repository,
        "search_by_vector", lambda **_: RETIRED_WINS_ON_MERIT)
    monkeypatch.setattr(policy_search_service, "embed_one_text", lambda _: [0.0])


def test_a_question_about_today_puts_the_current_rule_first(two_candidates):
    """The failure this was written for, with the retired rule holding every advantage."""
    found = search_policies("What is the internet allowance?", top_k=2)

    assert found[0].clause_id == "HC-PC-004§4.6"
    assert found[0].status == "current"


def test_a_question_about_the_past_leaves_the_retired_rule_where_it_was(two_candidates):
    """
    The other direction, and the reason this is a penalty and not a filter.

    Leave earned last year is governed by last year's rule. An answer quoting today's cap
    would be wrong in a way that costs the employee days.
    """
    found = search_policies("What was the allowance last year?", top_k=2)

    assert found[0].clause_id == "HC-PC-004§4.9"
    assert found[0].status == "superseded"


def test_the_retired_rule_is_demoted_and_not_removed(two_candidates):
    """
    It still has to be reachable, or "what changed?" stops working.
    """
    found = search_policies("What is the internet allowance?", top_k=2)

    assert {passage.clause_id for passage in found} == {
        "HC-PC-004§4.6", "HC-PC-004§4.9",
    }


# ── Which questions count as being about the past ────────────────────────────


@pytest.mark.parametrize("query", [
    "What was the cap on the days from last year?",
    "Who approved my AED 1,200 claim from November 2025?",
    "What was the rule before the change?",
    "ما هو الحد الأقصى في العام الماضي؟",
])
def test_these_ask_about_the_past(query):
    assert _asks_about_a_past_period(query)


@pytest.mark.parametrize("query", [
    "What is the internet allowance?",
    "What is the carry-over limit for annual leave?",
    "What is the expense threshold for 2026?",
    "هل الـ internet allowance ينطبق علي؟ وكم قيمته؟",
])
def test_these_do_not(query):
    """
    The 2026 case is not hypothetical. A capture group returning "20" rather than "2026"
    made every year look like a past one, which would have disabled the whole thing while
    every other test still passed.
    """
    assert not _asks_about_a_past_period(query)
