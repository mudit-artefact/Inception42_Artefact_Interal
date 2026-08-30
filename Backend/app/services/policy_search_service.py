"""
Finding the policy passages that answer a question.

Combines dense vector similarity with lexical word matching, then fuses the two rankings.
"""

import logging
import re
from datetime import date
from typing import Optional

from app.core.errors import PolicyIndexEmptyError
from app.domain.policy_passage import PolicyPassage
from app.indexing.ranking import fuse_rankings, score_lexical_match, tokenize
from app.indexing.text_embedder import embed_one_text
from app.repositories import policy_vector_repository

logger = logging.getLogger(__name__)

MINIMUM_CANDIDATE_POOL_SIZE = 15

# How far a retired rule drops when the question is about today. A penalty and not a
# filter, deliberately: a superseded provision still has to be reachable, or "what
# changed?" and "which rule applied when I claimed that?" stop working. It simply must not
# outrank the rule in force, which is what it was doing — an employee was told the internet
# allowance is AED 150 four months after it became 200.
SUPERSEDED_PENALTY = 0.4

# Words that mean the question is about a past period, in which case the retired rule is
# exactly what was asked for and nothing is demoted. A four-digit year is handled
# separately, against the current one.
ASKS_ABOUT_THE_PAST = re.compile(
    # Past-tense auxiliaries carry most of the signal, and carry it in both languages.
    # Somebody asking about the rule in force today writes "what IS the cap"; somebody
    # asking about the rule that governed their claim writes "what WAS the cap". The
    # first pattern here was built from a handful of phrases and matched "before the
    # change" but not "before the rules changed", and no Arabic past tense at all — so
    # five of eight questions about a retired rule were treated as questions about today
    # and had that rule pushed down the ranking, which is the opposite of what they asked
    # for. The retrieval test set is what made that visible.
    r"\b(was|were|had|used\s+to|did)\b"
    r"|\b(last year|previous(?:ly)?|prior|former(?:ly)?|back then|at the time"
    r"|old rule|earlier|then-current|superseded|replaced)\b"
    r"|before\s+(?:the\s+)?\w*\s*chang"
    r"|\bكان(?:ت)?\b|العام\s*الماضي|السنة\s*الماضية|سابق|السابق|في\s*حينه"
    r"|قبل\s*(?:ال)?(?:تغيير|تعديل|رفع)",
    re.IGNORECASE,
)


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

    about_the_past = _asks_about_a_past_period(query)
    for candidate in scored_candidates:
        candidate["relevance_score"] = fuse_rankings(
            dense_rank=candidate["dense_rank"], lexical_rank=candidate["lexical_rank"]
        )
        if not about_the_past and candidate["payload"].get("status") == "superseded":
            candidate["relevance_score"] *= SUPERSEDED_PENALTY

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


def _asks_about_a_past_period(query: str) -> bool:
    """
    Whether this question is about how things were, rather than how they are.

    Both readings are legitimate and the system holds both rules, so the question decides
    which one should win. "What is the internet allowance?" wants the rule in force.
    "What was the cap on the days from last year?" wants the one that has been retired,
    and demoting it there would be the same bug in the other direction.

    A year earlier than this one counts, because "my claim from November 2025" names its
    period without any of the words below.
    """
    if ASKS_ABOUT_THE_PAST.search(query or ""):
        return True

    this_year = date.today().year
    return any(
        int(year) < this_year
        for year in re.findall(r"\b(?:19|20)\d{2}\b", query or "")
    )
