"""
The benchmark report.

Two of its numbers used to be literals written into the source and presented as results:
a faithfulness score of 98.8 and a ranking improvement of 14.5. Everything reported now
comes from an actual measurement.
"""

from app.evaluation.benchmark_cases import GOLDEN_BENCHMARK_CASES
from app.services.evaluation_service import run_benchmark_evaluation


def test_the_benchmark_runs_over_every_question(isolated_policy_index):
    report = run_benchmark_evaluation()

    assert report.total_test_cases == len(GOLDEN_BENCHMARK_CASES)


def test_every_reported_figure_is_within_range(isolated_policy_index):
    report = run_benchmark_evaluation()

    for name, value in (
        ("intent accuracy", report.intent_accuracy_pct),
        ("recall@5", report.retrieval_recall_at_5_pct),
        ("abstain accuracy", report.abstain_accuracy_pct),
        ("precision@1", report.precision_at_1_pct),
        ("hop coverage", report.hop_coverage_pct),
        ("clause precision", report.clause_precision_pct),
        ("superseded leakage", report.superseded_leakage_pct),
    ):
        assert 0.0 <= value <= 100.0, f"{name} is out of range: {value}"
    assert 0.0 <= report.mrr_score <= 1.0


def test_the_groundedness_figure_is_no_longer_a_constant(isolated_policy_index):
    """It was hardcoded to 98.8 regardless of how retrieval actually performed."""
    report = run_benchmark_evaluation()

    assert report.precision_at_1_pct != 98.8 or report.retrieval_recall_at_5_pct == 100.0


def test_the_ablation_compares_two_real_measurements(isolated_policy_index):
    """The improvement figure must be the difference between the two recalls it reports."""
    ablation = run_benchmark_evaluation().ablation_study

    expected_difference = round(
        ablation["rewritten_hybrid_recall_pct"] - ablation["raw_query_recall_pct"], 1
    )
    assert ablation["improvement_delta_pct"] == expected_difference


def test_the_report_breaks_results_down_by_category(isolated_policy_index):
    report = run_benchmark_evaluation()

    assert report.category_breakdown
    for category, counts in report.category_breakdown.items():
        assert counts["total"] > 0, category
        assert counts["correct_retrieval"] <= counts["total"]
