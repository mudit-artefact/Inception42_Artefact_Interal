"""
Indexing and searching, exercised against a real in-memory vector database using
deterministic fake vectors. No network, no cost.

Defect 8: results were ordered by the fused ranking score but reported a different
number — the cosine similarity multiplied by 1.1 and capped at 1.0. The web interface
renders that number as a "% match", so it could show a lower percentage above a higher
one, and the inflation meant the figure was not a similarity at all.
"""

import pytest

from app.core.errors import PolicyIndexEmptyError
from app.services.policy_indexing_service import reindex_policies
from app.services.policy_search_service import search_policies

# Nine English policies and five Arabic editions, indexed from their Markdown sources.
EXPECTED_PASSAGE_COUNT = 121


def test_searching_an_empty_index_says_so_rather_than_indexing_mid_question(
    isolated_policy_index,
):
    """
    Indexing used to happen inside the search call, so the first person to ask a question
    after a restart silently waited for the whole catalogue to be embedded.
    """
    with pytest.raises(PolicyIndexEmptyError):
        search_policies(query="how much annual leave do I get", top_k=5)


def test_the_whole_catalogue_can_be_indexed(isolated_policy_index):
    indexed_count = reindex_policies(force=True)

    # Nine English policies and five Arabic editions, indexed from Markdown. The old
    # count of 63 included six Arabic passages that held no Arabic at all.
    assert indexed_count == EXPECTED_PASSAGE_COUNT
    assert isolated_policy_index.count_indexed_passages() == EXPECTED_PASSAGE_COUNT


def test_indexing_is_skipped_when_the_index_is_already_built(isolated_policy_index):
    reindex_policies(force=True)

    assert reindex_policies(force=False) == 0


def test_forcing_a_rebuild_does_not_duplicate_passages(isolated_policy_index):
    reindex_policies(force=True)
    reindex_policies(force=True)

    assert isolated_policy_index.count_indexed_passages() == EXPECTED_PASSAGE_COUNT


def test_results_are_ordered_by_the_score_they_report(isolated_policy_index):
    reindex_policies(force=True)

    passages = search_policies(query="annual leave carry over limit", top_k=5)

    reported_scores = [passage.relevance_score for passage in passages]
    assert reported_scores == sorted(reported_scores, reverse=True), (
        f"the list must be ordered by the same number it shows: {reported_scores}"
    )


def test_every_reported_score_is_a_real_proportion(isolated_policy_index):
    """The web interface multiplies this by 100 to render a percentage."""
    reindex_policies(force=True)

    passages = search_policies(query="sick leave medical certificate", top_k=5)

    assert passages
    for passage in passages:
        assert 0.0 <= passage.relevance_score <= 1.0, passage.relevance_score


def test_a_language_filter_only_returns_that_language(isolated_policy_index):
    reindex_policies(force=True)

    arabic_passages = search_policies(query="رصيد الإجازة السنوية", top_k=5, language="ar")

    assert arabic_passages
    assert {passage.language for passage in arabic_passages} == {"ar"}


def test_retrieved_passages_carry_the_details_a_citation_needs(isolated_policy_index):
    reindex_policies(force=True)

    passage = search_policies(query="annual leave entitlement", top_k=1)[0]

    assert passage.policy_code.startswith("HC-PC-")
    assert passage.title
    assert passage.pdf_url.startswith("/api/v1/hcs01/policies/pdf/")
    assert passage.page_number >= 1


def test_a_passage_reports_its_rank_score_and_its_true_closeness_separately(
    isolated_policy_index,
):
    """
    The displayed score comes from rank position, so even a poor result scores highly.
    Deciding whether anything relevant was found needs the real similarity instead, which
    is why a passage carries both.
    """
    reindex_policies(force=True)

    passages = search_policies(query="annual leave carry over limit", top_k=5)

    assert passages
    for passage in passages:
        assert 0.0 <= passage.semantic_similarity <= 1.0

    # The two numbers measure different things and must not be the same field.
    assert any(
        passage.semantic_similarity != passage.relevance_score for passage in passages
    ), "the display score and the true closeness should not be identical"
