"""
Every cell of the taxonomy is reached by a turn of some conversation.

The benchmark has the same property proved next door, one question per cell. This proves
it again over conversations, which is a different claim: a cell can be answerable from a
cold start and unreachable once five turns of context are in the way, and only the second
of those is what an employee experiences.

These tests run free and deterministically. They check that the scenarios are internally
sound — that every clause they expect exists, that every employee they name is seeded,
that the grid has no hole — not whether the assistant answers them, which needs a model
and lives in `scripts/run_conversation_scenarios.py`.
"""

import pytest

from app.database.seed_employees import build_seed_employees
from app.domain.enums import ConversationType, Modality, ReasoningType, SourceType
from app.evaluation.scenario_cases import CONVERSATION_SCENARIOS
from app.indexing.policy_chunk_builder import build_all_policy_passages

ALL_TURNS = [(scenario, turn)
             for scenario in CONVERSATION_SCENARIOS
             for turn in scenario.turns]


def test_every_source_and_reasoning_cell_has_a_turn():
    covered = {(turn.source_type, turn.reasoning_type) for _, turn in ALL_TURNS}
    missing = {(source, reasoning)
               for source in SourceType for reasoning in ReasoningType} - covered

    assert not missing, f"uncovered cells: {sorted((str(s), str(r)) for s, r in missing)}"


def test_every_conversation_type_has_a_turn():
    covered = {turn.conversation_type for _, turn in ALL_TURNS if turn.conversation_type}

    assert not set(ConversationType) - covered


def test_every_modality_has_a_turn():
    covered = {turn.modality for _, turn in ALL_TURNS}

    assert not set(Modality) - covered


def test_scenario_identifiers_are_unique():
    identifiers = [scenario.id for scenario in CONVERSATION_SCENARIOS]

    assert len(identifiers) == len(set(identifiers))


def test_a_scenario_holding_a_known_gap_is_not_marked_demo_safe():
    """
    A scenario cannot be marked safe to demonstrate and then quietly acquire a turn the
    system cannot serve. The flag is what the run-of-show in CONVERSATION_SCENARIOS.md is
    written against, so it has to follow the turns rather than the other way round.
    """
    for scenario in CONVERSATION_SCENARIOS:
        has_a_gap = any(turn.known_gap for turn in scenario.turns)

        assert scenario.demo_safe is not has_a_gap, (
            f"{scenario.id} is marked demo_safe={scenario.demo_safe} "
            f"but {'has' if has_a_gap else 'has no'} known-gap turn"
        )


def test_the_scan_gap_is_still_recorded_somewhere():
    """
    Reading evidence off an image is the one thing in the taxonomy nothing here can do —
    policy pages go through a text extractor only. It is deliberately represented by a
    turn rather than a comment, so it appears in every run's report instead of being
    forgotten. If image reading is ever added, this test is where the news arrives.
    """
    gaps = [turn for _, turn in ALL_TURNS if turn.known_gap]

    assert gaps, "the scan gap has been dropped; either it was fixed or it was forgotten"
    assert all("image" in turn.known_gap for turn in gaps)


def test_every_turn_that_expects_hops_names_enough_documents():
    """
    A turn asking for two hops out of one named document can never pass, and would look
    like a retrieval failure rather than the broken expectation it is.
    """
    for scenario, turn in ALL_TURNS:
        if turn.minimum_hops > 1:
            assert len(turn.expected_doc_sources) >= turn.minimum_hops, (
                f"{scenario.id} wants {turn.minimum_hops} hops from "
                f"{turn.expected_doc_sources}: {turn.query[:60]}"
            )


def test_a_turn_does_not_both_abstain_and_expect_facts():
    """Declining and stating a fact are different outcomes; a turn asking for both cannot pass."""
    for scenario, turn in ALL_TURNS:
        if turn.should_abstain:
            assert not turn.expected_facts, f"{scenario.id}: {turn.query[:60]}"
        if turn.should_ask_clarification:
            assert not turn.expected_facts, f"{scenario.id}: {turn.query[:60]}"


@pytest.mark.parametrize("scenario", CONVERSATION_SCENARIOS, ids=lambda s: s.id)
def test_every_expected_clause_exists_in_the_index(scenario):
    """Catches the corpus being renumbered underneath the scenarios."""
    indexed_clauses = {passage["clause_id"] for passage in build_all_policy_passages()}

    for turn in scenario.turns:
        for clause in turn.expected_clause_ids:
            assert clause in indexed_clauses, (
                f"{scenario.id} expects {clause}, which is not indexed"
            )


def test_every_scenario_names_a_seeded_employee():
    seeded = {row["employee"].user_id for row in build_seed_employees()}

    for scenario in CONVERSATION_SCENARIOS:
        assert scenario.employee_id in seeded, (
            f"{scenario.id} runs as {scenario.employee_id}, who is not seeded"
        )


@pytest.mark.parametrize("scenario", CONVERSATION_SCENARIOS, ids=lambda s: s.id)
def test_every_turn_can_actually_fail(scenario):
    """
    A turn with no expectation of any kind is a question that is asked and never checked.
    Those are what the benchmark runner's discarded context turns already were, and the
    whole point of this suite is that there are none of them.
    """
    for position, turn in enumerate(scenario.turns, start=1):
        checked = (turn.expected_facts or turn.forbidden_facts or turn.should_abstain
                   or turn.should_ask_clarification)

        assert checked, f"{scenario.id}.{position} is graded on nothing: {turn.query[:60]}"
