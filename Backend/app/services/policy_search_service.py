"""
Finding the policy passages that answer a question.

Combines dense vector similarity with lexical word matching, then fuses the two rankings.
"""

import logging
from typing import Optional

from app.core.errors import PolicyIndexEmptyError
from app.domain.policy_passage import PolicyPassage
from app.indexing.ranking import fuse_rankings, score_lexical_match, tokenize
from app.indexing.text_embedder import embed_one_text
from app.repositories import policy_vector_repository

logger = logging.getLogger(__name__)

MINIMUM_CANDIDATE_POOL_SIZE = 15


def search_policies(
    query: str,
    top_k: int = 5,
    language: Optional[str] = None,
) -> list[PolicyPassage]:
    """
    The most relevant policy passages for a query, best first.

    Raises PolicyIndexEmptyError when the index has not been built.
    """
    policy_vector_repository.ensure_collection_exists()
    if policy_vector_repository.count_indexed_passages() == 0:
        raise PolicyIndexEmptyError()

    candidates = policy_vector_repository.search_by_vector(
        query_vector=embed_one_text(query),
        limit=max(top_k * 3, MINIMUM_CANDIDATE_POOL_SIZE),
        language=language,
    )
    if not candidates:
        return []

    query_tokens = tokenize(query)
    scored_candidates = [
        {
            "payload": candidate.payload or {},
            "dense_rank": position + 1,
            "semantic_similarity": max(0.0, min(float(candidate.score), 1.0)),
            "lexical_score": score_lexical_match(
                query_tokens, tokenize((candidate.payload or {}).get("text", ""))
            ),
        }
        for position, candidate in enumerate(candidates)
    ]

    ranked_by_lexical_score = sorted(
        scored_candidates, key=lambda candidate: candidate["lexical_score"], reverse=True
    )
    for position, candidate in enumerate(ranked_by_lexical_score):
        candidate["lexical_rank"] = position + 1

    for candidate in scored_candidates:
        candidate["relevance_score"] = fuse_rankings(
            dense_rank=candidate["dense_rank"], lexical_rank=candidate["lexical_rank"]
        )

    best_first = sorted(
        scored_candidates, key=lambda candidate: candidate["relevance_score"], reverse=True
    )[:top_k]

    return [_to_policy_passage(candidate) for candidate in best_first]


def _to_policy_passage(candidate: dict) -> PolicyPassage:
    payload = candidate["payload"]
    return PolicyPassage(
        text=payload.get("text", ""),
        policy_code=payload.get("source", ""),
        title=payload.get("title", ""),
        section=payload.get("section", ""),
        page_number=payload.get("page_number", 1),
        pdf_url=payload.get("pdf_url", ""),
        language=payload.get("language", "en"),
        has_image=payload.get("has_image", False),
        relevance_score=round(candidate["relevance_score"], 4),
        semantic_similarity=round(candidate["semantic_similarity"], 4),
        clause_id=payload.get("clause_id", ""),
        policy_version=payload.get("policy_version", ""),
        effective_from=payload.get("effective_from", ""),
        effective_to=payload.get("effective_to", ""),
        status=payload.get("status", "current"),
    )
