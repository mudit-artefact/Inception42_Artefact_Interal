"""
Scores the search on its own, with no model in the loop.

Retrieval failures and generation failures look identical from the outside. A run of
answers reading "I could not confirm this" was diagnosed here as retrieval, then routing,
then something else again — each time on the strength of spot-checking a few queries that
happened to work. This settles that question in seconds instead of hours.

Free apart from embedding the queries. No language model is called at any point.

    python scripts/run_retrieval_evaluation.py
    python scripts/run_retrieval_evaluation.py --dimension reasoning_type
    python scripts/run_retrieval_evaluation.py --markdown
"""

import argparse
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.evaluation.retrieval_metrics import (  # noqa: E402
    as_percentage,
    found_all_within,
    found_within,
    rank_of_first_relevant,
    reciprocal_rank,
)

# Five and ten are the interesting ones. Five is what the system actually retrieves; ten
# says whether raising it would help, which is otherwise a guess.
CUTOFFS = (1, 3, 5, 10)
DEEPEST = max(CUTOFFS)


@dataclass
class Result:
    """What the search did with one query."""

    case: object
    ranked: list[str]

    @property
    def rank(self):
        return rank_of_first_relevant(self.ranked, self.case.relevant_clause_ids)

    @property
    def reciprocal(self) -> float:
        return reciprocal_rank(self.ranked, self.case.relevant_clause_ids)

    def hit(self, k: int) -> bool:
        """
        Whether this query is answered within k.

        A question whose answer spans several clauses is only answered when all of them
        are there. Counting one of three as a hit reports a system better than it is, and
        spanning questions are exactly where retrieval is most likely to be weak.
        """
        if self.case.every_clause_required:
            return found_all_within(self.ranked, self.case.relevant_clause_ids, k)
        return found_within(self.ranked, self.case.relevant_clause_ids, k)


def run_one(case) -> Result:
    from app.services.policy_search_service import search_policies

    passages = search_policies(case.query, top_k=DEEPEST, language=case.language)
    return Result(case=case, ranked=[passage.clause_id for passage in passages])


def headline(results: list[Result]) -> None:
    total = len(results)
    print("\n" + "=" * 78)
    print(f"{total} queries over the whole indexed corpus")
    print("=" * 78)
    print()
    print("  " + "   ".join(
        f"recall@{k} {as_percentage(sum(r.hit(k) for r in results), total):5.1f}%"
        for k in CUTOFFS
    ))
    mrr = sum(r.reciprocal for r in results) / total if total else 0.0
    print(f"\n  MRR {mrr:.3f}")


def breakdown(results: list[Result], title: str, of) -> None:
    grouped: dict = defaultdict(list)
    for result in results:
        value = of(result.case)
        if value is not None:
            grouped[str(value)].append(result)

    print(f"\n{title}")
    for value in sorted(grouped):
        group = grouped[value]
        mrr = sum(r.reciprocal for r in group) / len(group)
        hits = sum(r.hit(5) for r in group)
        bar = "█" * hits + "░" * (len(group) - hits)
        print(f"  {value:16} MRR {mrr:.2f}   recall@5 {hits:>2}/{len(group):<2} {bar}")


def the_worst(results: list[Result], how_many: int = 15) -> None:
    missed = [r for r in results if not r.hit(5)]
    if not missed:
        print("\nEvery query found its clause within five. Nothing to look at.")
        return

    print("\n" + "-" * 78)
    print(f"WORST — {len(missed)} queries whose clause was not in the top five")
    print("-" * 78)
    for result in sorted(missed, key=lambda r: (r.rank is None, r.rank or 0))[:how_many]:
        where = f"rank {result.rank}" if result.rank else f"not in {DEEPEST}"
        wanted = ", ".join(result.case.relevant_clause_ids)
        print(f"\n  {where:14} {wanted}")
        print(f"  {' ' * 14} \"{result.case.query[:64]}\"")
        print(f"  {' ' * 14} got: {', '.join(result.ranked[:3])}")


def markdown(results: list[Result]) -> None:
    total = len(results)
    print("\n| Metric | Value |")
    print("|---|---|")
    for k in CUTOFFS:
        print(f"| recall@{k} | {as_percentage(sum(r.hit(k) for r in results), total)}% |")
    print(f"| MRR | {sum(r.reciprocal for r in results) / total:.3f} |")
    print(f"| queries | {total} |")


DIMENSIONS = {
    "source_type": ("By where the answer must come from", lambda c: c.source_type),
    "reasoning_type": ("By what has to be done with it", lambda c: c.reasoning_type),
    "modality": ("By language and form", lambda c: c.modality),
    "language": ("By language of the query", lambda c: c.language),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dimension", choices=sorted(DIMENSIONS))
    parser.add_argument("--markdown", action="store_true")
    arguments = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)
    for noisy in ("httpx", "LiteLLM", "litellm"):
        logging.getLogger(noisy).setLevel(logging.ERROR)

    from app.evaluation.retrieval_cases import RETRIEVAL_CASES
    from app.services.policy_indexing_service import prepare_index_if_empty

    print(f"Indexing… {prepare_index_if_empty()} passages ready.")
    results = [run_one(case) for case in RETRIEVAL_CASES]

    headline(results)
    for name in ([arguments.dimension] if arguments.dimension else list(DIMENSIONS)):
        title, of = DIMENSIONS[name]
        breakdown(results, title, of)
    the_worst(results)
    if arguments.markdown:
        markdown(results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
