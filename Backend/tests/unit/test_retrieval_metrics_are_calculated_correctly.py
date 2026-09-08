"""
The arithmetic behind the numbers we quote.

Nothing tested this. The integration tests assert only that the figures fall between 0 and
100, which is satisfied by returning zero, and by returning anything plausible and wrong.
If MRR is going into a report, "the function ran" is not the same as "the number is right".

Every case here states a ranking and the answer by hand, so a failure means the arithmetic
changed rather than that retrieval got worse.
"""

import pytest

from app.evaluation.retrieval_metrics import (
    CLOSE_ENOUGH_TO_TRUST,
    as_percentage,
    best_possible_share,
    found_all_within,
    found_within,
    margin_below,
    rank_of_first_relevant,
    reciprocal_rank,
    share_that_was_relevant,
    stayed_unsure,
)

RANKED = ["A", "B", "C", "D", "E"]


# ── where the first right answer is ──────────────────────────────────────────


@pytest.mark.parametrize(
    "relevant,expected",
    [
        (["A"], 1),
        (["C"], 3),
        (["E"], 5),
        (["Z"], None),
        (["C", "A"], 1),        # the earliest of several, not the first named
        (["Z", "D"], 4),
        ([], None),
    ],
)
def test_the_rank_is_one_based_and_finds_the_earliest(relevant, expected):
    assert rank_of_first_relevant(RANKED, relevant) == expected


def test_an_empty_ranking_finds_nothing():
    assert rank_of_first_relevant([], ["A"]) is None


# ── reciprocal rank ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "relevant,expected",
    [(["A"], 1.0), (["B"], 0.5), (["C"], pytest.approx(1 / 3)), (["D"], 0.25), (["E"], 0.2)],
)
def test_reciprocal_rank_is_one_over_the_position(relevant, expected):
    assert reciprocal_rank(RANKED, relevant) == expected


def test_a_miss_scores_zero_not_none():
    """
    Zero, because MRR averages it. Returning None would raise, and returning 1.0 would
    score a total miss as a perfect hit — the two mistakes worth guarding against.
    """
    assert reciprocal_rank(RANKED, ["Z"]) == 0.0


def test_mrr_is_the_mean_of_the_reciprocals():
    """The definition, worked by hand: first, third and missing → (1 + 1/3 + 0) / 3."""
    scores = [
        reciprocal_rank(RANKED, ["A"]),
        reciprocal_rank(RANKED, ["C"]),
        reciprocal_rank(RANKED, ["Z"]),
    ]

    assert sum(scores) / len(scores) == pytest.approx(0.4444, abs=1e-4)


# ── recall at k ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("k,expected", [(1, False), (2, False), (3, True), (5, True), (10, True)])
def test_recall_at_k_is_inclusive_of_position_k(k, expected):
    """A clause at position 3 is found at k=3, not only at k=4. Off by one here would
    misreport every figure we publish."""
    assert found_within(RANKED, ["C"], k) is expected


def test_recall_needs_only_one_of_several(): 
    assert found_within(RANKED, ["Z", "D"], 5) is True


def test_recall_at_zero_finds_nothing():
    assert found_within(RANKED, ["A"], 0) is False


# ── all of them, for a question that spans clauses ───────────────────────────


def test_finding_one_of_two_is_not_finding_the_answer():
    """
    The distinction the spanning cases exist for. A question needing the eligibility rule
    and the role classification is not answered by either alone, and counting it as a hit
    reports a system better than it is.
    """
    assert found_within(RANKED, ["A", "D"], 2) is True
    assert found_all_within(RANKED, ["A", "D"], 2) is False
    assert found_all_within(RANKED, ["A", "D"], 4) is True


def test_all_within_ignores_the_order_they_arrive_in():
    assert found_all_within(RANKED, ["D", "A"], 4) is True


def test_all_within_is_false_when_one_is_absent_entirely():
    assert found_all_within(RANKED, ["A", "Z"], 5) is False


# ── a question with no answer ────────────────────────────────────────────────


def test_below_the_threshold_is_correctly_unsure():
    assert stayed_unsure(0.340) is True
    assert stayed_unsure(0.349) is True


def test_at_or_above_the_threshold_is_confident():
    """
    The boundary matters: the search trusts a result at exactly the threshold, so the
    evaluation must count that as confident or the two disagree about the same number.
    """
    assert stayed_unsure(CLOSE_ENOUGH_TO_TRUST) is False
    assert stayed_unsure(0.483) is False


def test_the_margin_is_positive_when_there_was_room_to_spare():
    assert margin_below(0.340) == 0.010
    assert margin_below(0.250) == 0.100


def test_the_margin_is_negative_when_the_search_was_confident():
    """A negative margin is the failure, and how far past the line it went."""
    assert margin_below(0.499) == -0.149


# ── the percentage ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "count,total,expected",
    [(1, 4, 25.0), (0, 10, 0.0), (10, 10, 100.0), (1, 3, 33.3), (2, 3, 66.7)],
)
def test_percentages_round_to_one_place(count, total, expected):
    assert as_percentage(count, total) == expected


def test_nothing_out_of_nothing_is_zero_rather_than_an_error():
    assert as_percentage(0, 0) == 0.0


# ── how much of what came back was worth reading ─────────────────────────────


@pytest.mark.parametrize(
    "relevant,k,expected",
    [
        (["A"], 5, 0.2),            # one right out of five
        (["A", "B"], 5, 0.4),
        (["A", "B", "C", "D", "E"], 5, 1.0),
        (["Z"], 5, 0.0),
        (["A"], 1, 1.0),            # the one fetched was the right one
        (["B"], 1, 0.0),
        (["A", "D"], 2, 0.5),       # D is outside the first two
    ],
)
def test_precision_counts_only_the_first_k(relevant, k, expected):
    assert share_that_was_relevant(RANKED, relevant, k) == pytest.approx(expected)


def test_precision_divides_by_what_came_back_not_by_k():
    """
    Asking for ten and getting three back is three-thirds if all three were right, not
    three-tenths. Dividing by k would score a short result as though it were padded with
    misses.
    """
    assert share_that_was_relevant(["A", "B", "C"], ["A", "B", "C"], 10) == 1.0


def test_precision_of_nothing_is_zero_rather_than_an_error():
    assert share_that_was_relevant([], ["A"], 5) == 0.0
    assert share_that_was_relevant(RANKED, ["A"], 0) == 0.0


@pytest.mark.parametrize(
    "relevant,k,expected",
    [
        (["A"], 8, 0.125),           # one answer, eight fetched — an eighth is the most
        (["A"], 5, 0.2),
        (["A", "B"], 8, 0.25),
        (["A", "B"], 1, 1.0),        # fetching one, one right answer is achievable
        (["A"], 1, 1.0),
    ],
)
def test_the_ceiling_is_set_by_how_many_answers_exist(relevant, k, expected):
    """
    Without this the precision figure reads as a failure when it is arithmetic. A question
    with one right clause, asked of eight, cannot score above an eighth however perfect
    the ranking.
    """
    assert best_possible_share(relevant, k) == pytest.approx(expected)


def test_a_perfect_search_scores_exactly_its_ceiling():
    """The property that makes the pair meaningful: at the top, the two numbers meet."""
    for relevant, k in ((["A"], 5), (["A", "B"], 5), (["A", "B", "C"], 3)):
        assert share_that_was_relevant(RANKED, relevant, k) == best_possible_share(relevant, k)
