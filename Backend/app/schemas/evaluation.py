"""The benchmark report shown in the web interface's evaluation panel."""

from typing import Any, Optional

from pydantic import BaseModel, Field

from app.domain.enums import ConversationType, Modality, ReasoningType, SourceType


class BenchmarkTurn(BaseModel):
    """One turn of a multi-turn benchmark case."""

    query: str
    expected_facts: list[str] = Field(default_factory=list)


class BenchmarkTestCase(BaseModel):
    """
    One question in the benchmark, and what a correct response to it looks like.

    The four taxonomy dimensions are fields rather than a free-text category, so a gap in
    coverage is something a test can find. `category` is kept because the evaluation panel
    groups by it.

    Two fields that used to be here are gone. `expected_intent` and `expected_page` were
    read by nothing, and `expected_page` was worse than unused: it pinned PDF pagination,
    which moves whenever the documents are re-rendered. `expected_clause_ids` replaces it
    and survives renumbering.
    """

    id: str
    category: str
    query: str

    # What kind of question this is.
    source_type: SourceType
    reasoning_type: ReasoningType
    conversation_type: Optional[ConversationType] = None
    modality: Modality = Modality.ENGLISH

    # What should be retrieved. Plural, because a question whose evidence spans four
    # documents used to score identically to one answered by a single lookup.
    expected_doc_sources: list[str] = Field(default_factory=list)
    expected_clause_ids: list[str] = Field(default_factory=list)
    minimum_hops: int = 1

    # What the answer should and should not contain. Checkable by matching, with no
    # model in the loop. `forbidden_facts` is what stops an answer that recites both the
    # current and the superseded figure from scoring as correct.
    expected_facts: list[str] = Field(default_factory=list)
    forbidden_facts: list[str] = Field(default_factory=list)

    # How the exchange should go.
    should_abstain: bool = False
    should_ask_clarification: bool = False
    language: str = "en"
    as_of_date: Optional[str] = None
    # Which employee is asking. Without this every case ran as nobody, so no question
    # about somebody's own record could be evaluated at all.
    employee_id: str = "EMP001"
    turns: list[BenchmarkTurn] = Field(default_factory=list)


class EvaluationReport(BaseModel):
    """The body of GET /api/v1/hcs01/eval."""

    total_test_cases: int
    intent_accuracy_pct: float
    retrieval_recall_at_5_pct: float
    abstain_accuracy_pct: float
    # Was called faithfulness_score_pct, which it never was. It is precision@1: how often
    # the best-ranked passage comes from the right document.
    precision_at_1_pct: float
    mrr_score: float
    # How much of a multi-document answer's evidence was actually retrieved. This is what
    # makes spanning reasoning measurable rather than assumed.
    hop_coverage_pct: float
    # Whether the right clause was found, not merely the right document.
    clause_precision_pct: float
    # How often a rule that no longer applies outranks the one that does, on questions
    # that are not about the past. The single best signal that versioning works.
    superseded_leakage_pct: float
    avg_latency_ms: int
    ablation_study: dict[str, Any]
    category_breakdown: dict[str, dict[str, Any]]
    taxonomy_coverage: dict[str, dict[str, int]] = Field(default_factory=dict)
