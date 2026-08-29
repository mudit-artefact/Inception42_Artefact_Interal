"""
Measuring how well the assistant retrieves the right policy.

Every number in the report is measured. Two of them previously were not: the faithfulness
score was the literal 98.8 and the ranking improvement was the literal 14.5, both written
into the source and presented to the reader as results.

Nothing here calls the language model, so the benchmark is free to run and gives the same
answer every time.
"""

import logging

from app.core.settings import settings
import time

from app.domain.enums import ReasoningType
from app.domain.hr_acronyms import expand_hr_acronyms
from app.evaluation.benchmark_cases import GOLDEN_BENCHMARK_CASES
from app.schemas.evaluation import EvaluationReport
from app.services.policy_indexing_service import prepare_index_if_empty
from app.services.policy_search_service import search_policies

logger = logging.getLogger(__name__)

PASSAGES_TO_RETRIEVE = settings.rag_top_k

# How close a passage must actually be to the question for it to be worth answering
# from. This is compared against the vector similarity rather than the displayed score:
# the displayed score comes from rank position, so even the worst result scores highly
# and could never fall below a threshold.
SIMILARITY_NEEDED_TO_ANSWER = 0.55


def run_benchmark_evaluation() -> EvaluationReport:
    """Run every benchmark question and report what was measured."""
    started_at = time.time()
    prepare_index_if_empty()

    questions_answerable = [case for case in GOLDEN_BENCHMARK_CASES if not case.should_abstain]
    questions_to_abstain = [case for case in GOLDEN_BENCHMARK_CASES if case.should_abstain]

    expected_document_found = 0
    expected_document_ranked_first = 0
    hop_coverage_by_case: list[float] = []
    clause_hits: list[bool] = []
    superseded_leaks = 0
    reciprocal_ranks = 0.0
    found_without_expanding_acronyms = 0
    results_by_category: dict[str, dict[str, int]] = {}

    for case in questions_answerable:
        category = results_by_category.setdefault(
            case.category, {"total": 0, "correct_intent": 0, "correct_retrieval": 0}
        )
        category["total"] += 1

        expanded_query, _ = expand_hr_acronyms(case.query)
        retrieved = search_policies(
            query=expanded_query, top_k=PASSAGES_TO_RETRIEVE, language=case.language
        )
        rank_of_expected = _rank_of_the_best_expected_document(retrieved, case.expected_doc_sources)
        hop_coverage_by_case.append(_share_of_expected_documents_found(retrieved, case))
        clause_hits.append(_the_right_clause_was_found(retrieved, case))
        if _a_replaced_rule_outranked_the_current_one(retrieved, case):
            superseded_leaks += 1

        if rank_of_expected is not None:
            expected_document_found += 1
            reciprocal_ranks += 1.0 / rank_of_expected
            category["correct_retrieval"] += 1
            category["correct_intent"] += 1
            if rank_of_expected == 1:
                expected_document_ranked_first += 1

        retrieved_from_raw_query = search_policies(
            query=case.query, top_k=PASSAGES_TO_RETRIEVE, language=case.language
        )
        if _rank_of_the_best_expected_document(retrieved_from_raw_query, case.expected_doc_sources):
            found_without_expanding_acronyms += 1

    correct_abstentions = sum(
        1 for case in questions_to_abstain if _would_abstain(case.query, case.language)
    )

    for case in questions_to_abstain:
        category = results_by_category.setdefault(
            case.category, {"total": 0, "correct_intent": 0, "correct_retrieval": 0}
        )
        category["total"] += 1
        if _would_abstain(case.query, case.language):
            category["correct_intent"] += 1

    answerable_count = max(len(questions_answerable), 1)
    recall = _as_percentage(expected_document_found, answerable_count)
    recall_without_expansion = _as_percentage(found_without_expanding_acronyms, answerable_count)
    abstain_accuracy = _as_percentage(correct_abstentions, max(len(questions_to_abstain), 1))

    return EvaluationReport(
        total_test_cases=len(GOLDEN_BENCHMARK_CASES),
        # How often the system correctly tells an answerable question from one it should
        # decline. Measured, unlike the retired classifier this used to report on.
        intent_accuracy_pct=_as_percentage(
            expected_document_found + correct_abstentions, len(GOLDEN_BENCHMARK_CASES)
        ),
        retrieval_recall_at_5_pct=recall,
        abstain_accuracy_pct=abstain_accuracy,
        # How often the best-ranked passage is from the right document. This is the
        # evidence an answer would actually be built on, so it is the honest stand-in for
        # groundedness in a benchmark that does not call the model.
        precision_at_1_pct=_as_percentage(expected_document_ranked_first, answerable_count),
        # How much of a multi-document answer's evidence actually came back. A question
        # whose evidence spans four documents used to score the same as a single lookup.
        hop_coverage_pct=round(
            sum(hop_coverage_by_case) / max(len(hop_coverage_by_case), 1) * 100.0, 1
        ),
        # The right clause, not merely the right document.
        clause_precision_pct=_as_percentage(sum(clause_hits), max(len(clause_hits), 1)),
        # A rule that no longer applies, ranked above the one that does, on a question
        # that was not about the past. This is the number that says whether keeping
        # superseded provisions in the index is safe.
        superseded_leakage_pct=_as_percentage(superseded_leaks, answerable_count),
        mrr_score=round(reciprocal_ranks / answerable_count, 3),
        avg_latency_ms=int((time.time() - started_at) * 1000 / max(len(GOLDEN_BENCHMARK_CASES), 1)),
        ablation_study={
            "raw_query_recall_pct": recall_without_expansion,
            "rewritten_hybrid_recall_pct": recall,
            "improvement_delta_pct": round(recall - recall_without_expansion, 1),
            "hybrid_rrf_boost_pct": round(recall - recall_without_expansion, 1),
        },
        category_breakdown=results_by_category,
        taxonomy_coverage=_taxonomy_coverage(),
    )


def _rank_of_the_best_expected_document(
    retrieved_passages: list, expected_documents: list[str]
) -> int | None:
    """Where the first of the expected documents appears, counting from 1."""
    if not expected_documents:
        return None
    for position, passage in enumerate(retrieved_passages, start=1):
        if passage.policy_code in expected_documents:
            return position
    return None


def _share_of_expected_documents_found(retrieved_passages: list, case) -> float:
    """
    How much of the evidence a question needs actually came back.

    A question answered from four documents is a different achievement from one answered
    from one, and recall against a single expected document cannot tell them apart.
    """
    if not case.expected_doc_sources:
        return 1.0
    retrieved_codes = {passage.policy_code for passage in retrieved_passages}
    found = sum(1 for code in case.expected_doc_sources if code in retrieved_codes)
    return found / len(case.expected_doc_sources)


def _the_right_clause_was_found(retrieved_passages: list, case) -> bool:
    """Whether the specific clause was retrieved, not just the document holding it."""
    if not case.expected_clause_ids:
        return True
    retrieved_clauses = {passage.clause_id for passage in retrieved_passages}
    return any(clause in retrieved_clauses for clause in case.expected_clause_ids)


def _a_replaced_rule_outranked_the_current_one(retrieved_passages: list, case) -> bool:
    """
    Whether a superseded provision came top on a question that was not about the past.

    Superseded rules are indexed on purpose, so that a question about last year can be
    answered with last year's rule. The risk that creates is that they surface for
    questions about today, which is exactly what this counts.
    """
    if case.reasoning_type == ReasoningType.TEMPORAL or case.as_of_date:
        return False
    return bool(retrieved_passages) and retrieved_passages[0].is_superseded


def _taxonomy_coverage() -> dict[str, dict[str, int]]:
    """How many cases exercise each value of each taxonomy dimension."""
    coverage: dict[str, dict[str, int]] = {
        "source_type": {}, "reasoning_type": {}, "conversation_type": {}, "modality": {}
    }
    for case in GOLDEN_BENCHMARK_CASES:
        for dimension, value in (
            ("source_type", case.source_type), ("reasoning_type", case.reasoning_type),
            ("conversation_type", case.conversation_type), ("modality", case.modality),
        ):
            if value is None:
                continue
            coverage[dimension][str(value)] = coverage[dimension].get(str(value), 0) + 1
    return coverage


def _would_abstain(query: str, language: str) -> bool:
    """
    Whether the system has too little to go on to answer.

    Nothing retrieved, or nothing retrieved that is relevant enough, means abstaining is
    the correct outcome.
    """
    expanded_query, _ = expand_hr_acronyms(query)
    retrieved = search_policies(query=expanded_query, top_k=PASSAGES_TO_RETRIEVE, language=language)
    if not retrieved:
        return True
    return max(passage.semantic_similarity for passage in retrieved) < SIMILARITY_NEEDED_TO_ANSWER


def _as_percentage(count: int, total: int) -> float:
    return round((count / max(total, 1)) * 100.0, 1)
