"""
How a ranked list of passages is scored.

One implementation, used by the retrieval script and by the benchmark endpoint. Two
copies of "what is MRR" will disagree eventually, and the disagreement will be read as a
regression in the system rather than a difference of opinion between two files.

Every function here takes the ranking as a list of clause identifiers, best first, and the
set that would have been a correct answer. Nothing here searches, embeds, or knows what a
policy is.
"""

from typing import Iterable, Optional


def rank_of_first_relevant(
    ranked_clause_ids: list[str], relevant: Iterable[str]
) -> Optional[int]:
    """
    Where the first correct clause appears, counting from 1, or None if it never does.

    The building block for everything else: recall@k is this being at most k, and the
    reciprocal rank is one over it.
    """
    wanted = set(relevant)
    for position, clause_id in enumerate(ranked_clause_ids, start=1):
        if clause_id in wanted:
            return position
    return None


def found_within(ranked_clause_ids: list[str], relevant: Iterable[str], k: int) -> bool:
    """
    Whether a correct clause is in the first k.

    Averaged over queries this is what the report calls recall@k, and what the literature
    more precisely calls **hit rate@k** or success@k: one question, one yes or no. It is
    not the textbook recall, which is the share of a question's relevant clauses that were
    found. The two agree for every question with a single right answer — 177 of 218 here —
    and differ only where several clauses each answer the same question.
    """
    rank = rank_of_first_relevant(ranked_clause_ids[:k], relevant)
    return rank is not None


def found_all_within(
    ranked_clause_ids: list[str], relevant: Iterable[str], k: int
) -> bool:
    """
    Whether *every* correct clause is in the first k.

    For a question whose answer genuinely spans several clauses, finding one of them is
    not finding the answer — "what has to happen before I can work remotely?" needs the
    eligibility rule and the role classification, and either alone gives a confident half
    answer. Recall that counts those as hits reports a system better than it is.
    """
    return set(relevant).issubset(set(ranked_clause_ids[:k]))


def share_that_was_relevant(
    ranked_clause_ids: list[str], relevant: Iterable[str], k: int
) -> float:
    """
    What fraction of the first k were actually about the question. Precision@k.

    The companion to recall, and the one that was missing. Recall asks whether the answer
    was found; this asks how much came back with it. Everything retrieved is read by the
    assistant, and everything irrelevant is something it has to recognise and ignore —
    which it does not always manage.

    Read the level against its ceiling, not on its own. Most questions here have a single
    right clause, so fetching eight caps this at one in eight however well the search
    ranks. The number that means something is how it moves when the depth changes: more
    depth always buys recall with precision, and this is the price tag.
    """
    if k <= 0:
        return 0.0
    considered = ranked_clause_ids[:k]
    if not considered:
        return 0.0
    wanted = set(relevant)
    return sum(1 for clause_id in considered if clause_id in wanted) / len(considered)


def best_possible_share(relevant: Iterable[str], k: int) -> float:
    """
    The most precision@k could be for this question, given how many answers exist.

    A question with one right clause, asked of eight, cannot score above an eighth. Without
    this the precision figure reads as a failure when it is arithmetic.
    """
    if k <= 0:
        return 0.0
    return min(len(set(relevant)), k) / k


def reciprocal_rank(ranked_clause_ids: list[str], relevant: Iterable[str]) -> float:
    """
    One over the position of the first correct clause. Zero when there is none.

    Averaged across queries this is MRR. It rewards putting the right clause first rather
    than merely somewhere, which matters here because only the top few are ever shown to
    the model.
    """
    rank = rank_of_first_relevant(ranked_clause_ids, relevant)
    return 1.0 / rank if rank else 0.0


def as_percentage(count: int, total: int) -> float:
    return round((count / total) * 100.0, 1) if total else 0.0


# What the search itself treats as "close enough to trust", from
# `app/workflow/nodes/gather_evidence.py`. Held here so the evaluation scores the rule the
# system actually applies rather than a second opinion about it.
CLOSE_ENOUGH_TO_TRUST = 0.35


def stayed_unsure(best_similarity: float, threshold: float = CLOSE_ENOUGH_TO_TRUST) -> bool:
    """
    Whether the search correctly declined to be confident about a question with no answer.

    Every other measure here asks whether the right clause was found. None of them can fail
    on the opposite mistake: returning something confidently for a question the corpus does
    not answer. A query about the parking policy will always return the ten nearest
    passages, because a vector search always returns something — what tells you it found
    nothing is that none of them is close.
    """
    return best_similarity < threshold


def margin_below(best_similarity: float, threshold: float = CLOSE_ENOUGH_TO_TRUST) -> float:
    """
    How much room a no-answer query had to spare. Negative where it had none.

    The number worth watching. A corpus can pass every no-answer query today and be one
    added policy away from failing them, and only the margin shows that coming.
    """
    return round(threshold - best_similarity, 3)
