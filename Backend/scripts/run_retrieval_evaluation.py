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

from app.core.settings import settings  # noqa: E402

from app.evaluation.retrieval_metrics import (  # noqa: E402
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

# Eight is what the system actually retrieves — `rag_top_k` — so that is the operational
# number and the one to quote. One says how often the very first result is right; three is
# what a person would read before giving up; ten says whether retrieving deeper would help,
# which is otherwise a guess.
#
# This said five until `rag_top_k` was raised, at which point the headline quietly stopped
# describing the running system. Read it from settings so it cannot drift again.
LIVE_DEPTH = settings.rag_top_k
CUTOFFS = tuple(sorted({1, 3, 5, LIVE_DEPTH, 10}))
DEEPEST = max(CUTOFFS)


@dataclass
class Result:
    """What the search did with one query."""

    case: object
    ranked: list[str]
    best_similarity: float = 0.0

    @property
    def rank(self):
        return rank_of_first_relevant(self.ranked, self.case.relevant_clause_ids)

    @property
    def reciprocal(self) -> float:
        return reciprocal_rank(self.ranked, self.case.relevant_clause_ids)

    def precision(self, k: int) -> float:
        """How much of the first k was worth reading."""
        return share_that_was_relevant(self.ranked, self.case.relevant_clause_ids, k)

    def ceiling(self, k: int) -> float:
        """The most precision@k could have been, given how many answers this question has."""
        return best_possible_share(self.case.relevant_clause_ids, k)

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
    return Result(
        case=case,
        ranked=[passage.clause_id for passage in passages],
        best_similarity=max((p.semantic_similarity for p in passages), default=0.0),
    )


def headline(results: list[Result]) -> None:
    """
    Recall and MRR, over the queries that have an answer to find.

    Queries with nothing to find are reported separately by `nothing_to_find`. A query with
    no right answer has no reciprocal rank, and averaging a zero in for it would report a
    ranking failure that never happened.
    """
    total = len(results)
    print("\n" + "=" * 78)
    print(f"{total} queries with an answer in the corpus")
    print("=" * 78)
    print()
    print("  " + "   ".join(
        f"recall@{k}{'*' if k == LIVE_DEPTH else ' '} "
        f"{as_percentage(sum(r.hit(k) for r in results), total):5.1f}%"
        for k in CUTOFFS
    ))
    mrr = sum(r.reciprocal for r in results) / total if total else 0.0
    print(f"\n  MRR {mrr:.3f}")
    print(f"\n  * the depth the system actually retrieves at (rag_top_k = {LIVE_DEPTH})")
    precision = sum(r.precision(LIVE_DEPTH) for r in results) / total if total else 0.0
    ceiling = sum(r.ceiling(LIVE_DEPTH) for r in results) / total if total else 0.0
    print(
        f"\n  precision@{LIVE_DEPTH} {precision:.1%}   "
        f"(the most it could be is {ceiling:.1%} — most questions have one answer,\n"
        f"{'':22}so {1 - precision:.0%} of what the assistant reads is noise it must ignore)"
    )
    print(
        "\n  recall@k here is hit rate: a question counts once if any clause that answers\n"
        "  it came back, not as the fraction of its clauses that did. The two are the same\n"
        "  for the 177 questions with a single answer. The spanning questions are the\n"
        "  exception and are scored strictly — all of their clauses, or none."
    )


def nothing_to_find(results: list[Result]) -> None:
    """
    How the search behaves on questions the corpus does not answer.

    Every other figure here asks whether the right clause was found, so none of them can
    fail on the opposite mistake — coming back confident about a question with no answer. A
    vector search always returns its ten nearest passages; what says it found nothing is
    that none of them is close.

    The margin is the number to watch. Passing every one of these today and being one added
    policy away from failing them look identical without it.
    """
    if not results:
        return

    unsure = [r for r in results if stayed_unsure(r.best_similarity)]
    margins = sorted(results, key=lambda r: margin_below(r.best_similarity))

    print("\n" + "-" * 78)
    print(f"NOTHING TO FIND — {len(results)} questions the Code does not answer")
    print("-" * 78)
    print(
        f"\n  {len(unsure)} of {len(results)} correctly unsure   "
        f"(nothing scored above {CLOSE_ENOUGH_TO_TRUST})"
    )
    print(f"  narrowest margin {margin_below(margins[0].best_similarity):+.3f}\n")
    for result in margins[:6]:
        room = margin_below(result.best_similarity)
        verdict = "unsure" if stayed_unsure(result.best_similarity) else "** CONFIDENT **"
        print(f"  {room:+.3f}  {result.best_similarity:.3f}  {verdict:16} {result.case.query[:44]}")
        if not stayed_unsure(result.best_similarity):
            print(f"{'':34}reached for {result.ranked[0]}")


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
        hits = sum(r.hit(LIVE_DEPTH) for r in group)
        precision = sum(r.precision(LIVE_DEPTH) for r in group) / len(group)
        bar = "█" * hits + "░" * (len(group) - hits)
        print(
            f"  {value:16} MRR {mrr:.2f}   P@{LIVE_DEPTH} {precision:5.1%}   "
            f"recall@{LIVE_DEPTH} {hits:>3}/{len(group):<3} {bar}"
        )


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


def write_figures(
    results: list[Result], unanswerable: list[Result], passages: int, directory: str
) -> Path:
    """
    Every figure from this run, as JSON, named by the date.

    Printing to the screen answers "how is it doing"; it cannot answer "is it better than
    last month", which is the question anybody looking at these numbers asks second.
    """
    import json
    from datetime import date

    total = len(results)
    figures = {
        "run_on": date.today().isoformat(),
        "passages_indexed": passages,
        "retrieval_depth_in_use": LIVE_DEPTH,
        "queries_with_an_answer": total,
        "mrr": round(sum(r.reciprocal for r in results) / total, 3) if total else 0.0,
        # Named for both, because the two are read differently by anybody technical: this
        # is a hit rate, one per question, not the share of a question's clauses found.
        "recall_at_k_hit_rate": {
            f"at_{k}": as_percentage(sum(r.hit(k) for r in results), total) for k in CUTOFFS
        },
        "precision_at_k": {
            f"at_{k}": round(sum(r.precision(k) for r in results) / total, 3) if total else 0.0
            for k in CUTOFFS
        },
        "precision_ceiling_at_k": {
            f"at_{k}": round(sum(r.ceiling(k) for r in results) / total, 3) if total else 0.0
            for k in CUTOFFS
        },
        "precision_definition": (
            "Of the k clauses retrieved for a question, the share that answer it, averaged "
            "over questions. Read against the ceiling: most questions have one answer, so "
            "fetching k caps precision at 1/k however well the search ranks."
        ),
        "recall_definition": (
            "A question scores 1 if any clause that answers it is within k. Questions "
            "marked spanning score 1 only if every clause is. Also called hit rate@k "
            "or success@k."
        ),
        "by_dimension": {
            name: {
                str(value): {
                    "queries": len(group),
                    "mrr": round(sum(r.reciprocal for r in group) / len(group), 3),
                    f"hit_rate_at_{LIVE_DEPTH}": as_percentage(
                        sum(r.hit(LIVE_DEPTH) for r in group), len(group)
                    ),
                    f"precision_at_{LIVE_DEPTH}": round(
                        sum(r.precision(LIVE_DEPTH) for r in group) / len(group), 3
                    ),
                }
                for value, group in _grouped(results, of).items()
            }
            for name, (_, of) in DIMENSIONS.items()
        },
        "nothing_to_find": {
            "queries": len(unanswerable),
            "correctly_unsure": sum(
                stayed_unsure(r.best_similarity) for r in unanswerable
            ),
            "threshold": CLOSE_ENOUGH_TO_TRUST,
            "narrowest_margin": min(
                (margin_below(r.best_similarity) for r in unanswerable), default=None
            ),
            "came_back_confident": [
                {"query": r.case.query, "similarity": round(r.best_similarity, 3),
                 "reached_for": r.ranked[0] if r.ranked else None}
                for r in unanswerable
                if not stayed_unsure(r.best_similarity)
            ],
        },
    }

    written = Path(directory)
    written.mkdir(parents=True, exist_ok=True)
    written = written / f"retrieval-{figures['run_on']}.json"
    written.write_text(json.dumps(figures, indent=2, ensure_ascii=False), encoding="utf-8")
    return written


def _grouped(results: list[Result], of) -> dict:
    grouped: dict = defaultdict(list)
    for result in results:
        value = of(result.case)
        if value is not None:
            grouped[str(value)].append(result)
    return dict(grouped)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dimension", choices=sorted(DIMENSIONS))
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument(
        "--out",
        nargs="?",
        const="evaluation",
        metavar="DIR",
        help="also write the figures as JSON, so a run can be quoted and compared later",
    )
    arguments = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)
    for noisy in ("httpx", "LiteLLM", "litellm"):
        logging.getLogger(noisy).setLevel(logging.ERROR)

    from app.evaluation.retrieval_cases import RETRIEVAL_CASES
    from app.services.policy_indexing_service import prepare_index_if_empty

    passages = prepare_index_if_empty()
    print(f"Indexing… {passages} passages ready.")
    every = [run_one(case) for case in RETRIEVAL_CASES]

    # Split before anything is averaged. A question with no answer has no rank, and mixing
    # the two would report a ranking failure that did not happen.
    results = [r for r in every if r.case.relevant_clause_ids]
    unanswerable = [r for r in every if not r.case.relevant_clause_ids]

    headline(results)
    for name in ([arguments.dimension] if arguments.dimension else list(DIMENSIONS)):
        title, of = DIMENSIONS[name]
        breakdown(results, title, of)
    nothing_to_find(unanswerable)
    the_worst(results)
    if arguments.markdown:
        markdown(results)
    if arguments.out:
        print(f"\n  written to {write_figures(results, unanswerable, passages, arguments.out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
