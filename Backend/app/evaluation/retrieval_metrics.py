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
    """Whether a correct clause is in the first k. This is recall@k for one query."""
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
