"""
Every cell of the evaluation taxonomy has a question behind it.

A taxonomy written in a document is a claim; a taxonomy checked by a test is a property.
This is what stops the grid quietly developing a hole — a new reasoning type added and
never exercised, or a case retired and the only instance of its cell going with it.
"""

import re
from pathlib import Path

import pytest

from app.domain.enums import ConversationType, Modality, ReasoningType, SourceType
from app.evaluation.benchmark_cases import GOLDEN_BENCHMARK_CASES
from app.indexing.policy_chunk_builder import build_all_policy_passages

CORPUS = Path(__file__).resolve().parents[2] / "data"


def test_every_source_and_reasoning_cell_has_a_case():
    covered = {(case.source_type, case.reasoning_type) for case in GOLDEN_BENCHMARK_CASES}
    missing = {(source, reasoning) for source in SourceType for reasoning in ReasoningType} - covered

    assert not missing, f"uncovered cells: {sorted((str(s), str(r)) for s, r in missing)}"


def test_every_conversation_type_has_a_case():
    covered = {case.conversation_type for case in GOLDEN_BENCHMARK_CASES if case.conversation_type}

    assert not set(ConversationType) - covered


def test_every_modality_has_a_case():
    covered = {case.modality for case in GOLDEN_BENCHMARK_CASES}

    assert not set(Modality) - covered


def test_case_identifiers_are_unique():
    identifiers = [case.id for case in GOLDEN_BENCHMARK_CASES]

    assert len(identifiers) == len(set(identifiers))


@pytest.mark.parametrize("case", GOLDEN_BENCHMARK_CASES, ids=lambda c: c.id)
def test_every_expected_clause_exists_in_the_index(case):
    """
    A case that expects a clause the corpus does not contain can never pass, and would
    look like a retrieval failure rather than the broken expectation it is. This also
    catches the corpus being renumbered underneath the benchmark.
    """
    indexed_clauses = {passage["clause_id"] for passage in build_all_policy_passages()}

    for clause in case.expected_clause_ids:
        assert clause in indexed_clauses, f"{case.id} expects {clause}, which is not indexed"


@pytest.mark.parametrize("case", GOLDEN_BENCHMARK_CASES, ids=lambda c: c.id)
def test_a_multi_hop_case_names_every_document_it_spans(case):
    """`minimum_hops` is what separates a real chain from a single lookup."""
    if case.minimum_hops > 1:
        assert len(case.expected_doc_sources) >= case.minimum_hops, (
            f"{case.id} claims {case.minimum_hops} hops but names "
            f"{len(case.expected_doc_sources)} documents"
        )


@pytest.mark.parametrize("case", GOLDEN_BENCHMARK_CASES, ids=lambda c: c.id)
def test_an_arabic_case_is_written_in_arabic(case):
    if case.modality in (Modality.ARABIC, Modality.CODE_SWITCH):
        assert any("؀" <= character <= "ۿ" for character in case.query), (
            f"{case.id} is tagged {case.modality} but its query contains no Arabic"
        )
        assert case.language == "ar"


def test_a_temporal_case_forbids_the_rule_that_replaced_the_one_it_asks_about():
    """
    Without this, an answer that recites both the current figure and the superseded one
    scores as correct on exactly the questions designed to tell them apart.
    """
    temporal = [c for c in GOLDEN_BENCHMARK_CASES if c.reasoning_type == ReasoningType.TEMPORAL]

    assert temporal, "the taxonomy has a temporal cell but the benchmark has no case for it"
    assert any(case.forbidden_facts for case in temporal)


def test_the_corpus_still_contains_a_superseded_provision_to_reason_about():
    superseded = [p for p in build_all_policy_passages() if p["status"] == "superseded"]

    assert superseded, "temporal cases need a rule that has actually been replaced"
    for passage in superseded:
        assert passage["effective_from"] and passage["effective_to"], (
            f"{passage['clause_id']} is marked superseded but says nothing about when "
            f"it applied, so no question about the past can be answered from it"
        )
