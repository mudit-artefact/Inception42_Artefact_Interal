"""Browsing the policy catalogue and rebuilding the search index."""

import logging

from fastapi import APIRouter, HTTPException

from app.schemas.policy import PolicySummary, ReindexPoliciesResponse
from app.services.policy_catalog_service import list_policy_summaries
from app.services.policy_indexing_service import reindex_policies

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/hcs01", tags=["Policy & Leave Concierge"])


@router.get(
    "/policies",
    response_model=list[PolicySummary],
    summary="List the policies, with links to their official PDFs",
)
async def list_policies() -> list[PolicySummary]:
    return list_policy_summaries()


@router.post(
    "/policies/reindex",
    response_model=ReindexPoliciesResponse,
    summary="Rebuild the policy search index",
)
async def rebuild_policy_index(force: bool = False) -> ReindexPoliciesResponse:
    """Pass force=true to rebuild an index that already holds passages."""
    try:
        indexed_count = reindex_policies(force=force)
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    if indexed_count == 0 and not force:
        return ReindexPoliciesResponse(
            status="skipped",
            chunks_indexed=0,
            message="The index already holds passages. Pass force=true to rebuild it.",
        )
    return ReindexPoliciesResponse(
        status="success",
        chunks_indexed=indexed_count,
        message=f"Indexed {indexed_count} policy passages.",
    )
