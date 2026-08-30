"""
The retrieval test set covers the corpus, and does not cheat.

Two failure modes, both silent. A clause nobody wrote a query for is a clause whose
retrieval can break without anyone noticing — before this set existed, 39 of 119 clauses
were ever a target, so two thirds of the corpus was untested. And a query written in its
clause's own words retrieves that clause on wording alone, which measures nothing while
producing a reassuring number.
"""

import re

import pytest

from app.evaluation.retrieval_cases import RETRIEVAL_CASES
from app.indexing.policy_chunk_builder import build_all_policy_passages

# The two passages carrying no clause number at all are an indexing artefact rather than
# rules, and are excluded here rather than given meaningless questions.
INDEXED = {
    passage["clause_id"]: passage
    for passage in build_all_policy_passages()
    if re.search(r"§\d", passage["clause_id"] or "")
}

# Long enough that sharing it is copying rather than coincidence. Three words of policy
# English — "the line manager" — is a phrase anybody might write; six is the clause.
LONGEST_SHARED_RUN = 5


def test_every_indexed_clause_is_asked_about():
    targeted = {clause for case in RETRIEVAL_CASES for clause in case.relevant_clause_ids}
    untested = sorted(set(INDEXED) - targeted)

    assert not untested, f"{len(untested)} clauses no query targets: {untested[:8]}"


def test_no_query_targets_a_clause_that_does_not_exist():
    """
    Catches the corpus being renumbered underneath the test set, which would otherwise
    read as retrieval falling over rather than as labels gone stale.
    """
    for case in RETRIEVAL_CASES:
        for clause in case.relevant_clause_ids:
            assert clause in INDEXED, f"{clause} is a target but is not indexed"


@pytest.mark.parametrize("case", RETRIEVAL_CASES, ids=lambda c: c.query[:40])
def test_a_query_does_not_borrow_its_clause_wording(case):
    """
    A query lifted from its own clause retrieves it on the words alone.

    "What is the maximum carry-over of unused annual leave?" is the clause with a question
    mark on it, and scores well while proving nothing. "Do my leftover days roll into next
    year?" is the same question and actually tests the search. This keeps the set honest
    as it grows, which matters most when somebody adds to it in a hurry.
    """
    words = _words(case.query)
    if len(words) <= LONGEST_SHARED_RUN:
        return

    runs = {
        " ".join(words[start:start + LONGEST_SHARED_RUN])
        for start in range(len(words) - LONGEST_SHARED_RUN + 1)
    }

    for clause in case.relevant_clause_ids:
        clause_text = " ".join(_words(INDEXED[clause]["text"]))
        borrowed = sorted(run for run in runs if run in clause_text)

        assert not borrowed, (
            f"{case.query!r} shares {LONGEST_SHARED_RUN} consecutive words with "
            f"{clause}: {borrowed[0]!r}. Ask it the way an employee would instead."
        )


def test_a_spanning_case_names_more_than_one_clause():
    """Requiring every clause is meaningless where there is only one of them."""
    for case in RETRIEVAL_CASES:
        if case.every_clause_required:
            assert len(case.relevant_clause_ids) > 1, case.query


def _words(text: str) -> list[str]:
    return re.findall(r"\w+", (text or "").lower())
