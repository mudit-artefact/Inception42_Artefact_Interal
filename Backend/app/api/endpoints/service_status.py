"""The service's own status, and the benchmark report."""

import logging

from fastapi import APIRouter, HTTPException

from app.core.settings import settings
from app.repositories.policy_vector_repository import count_indexed_passages
from app.schemas.evaluation import EvaluationReport
from app.schemas.health import HealthStatusResponse, ServiceBannerResponse
from app.services.evaluation_service import run_benchmark_evaluation

logger = logging.getLogger(__name__)

SERVICE_NAME = "Bayan HR — Policy & Leave Concierge"
SERVICE_VERSION = "1.0.0"

router = APIRouter(tags=["Bayan HR"])


@router.get(
    "/api/v1/hcs01/health",
    response_model=HealthStatusResponse,
    summary="Check the service and its search index",
)
async def check_health() -> HealthStatusResponse:
    try:
        indexed_passages = count_indexed_passages()
        search_index_reachable = True
    except Exception:
        indexed_passages = 0
        search_index_reachable = False

    return HealthStatusResponse(
        status="ok" if search_index_reachable else "degraded",
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
        qdrant_connected=search_index_reachable,
        vectors_indexed=indexed_passages,
        llm_model=settings.llm_model,
        embedding_model=settings.embedding_model,
    )


@router.get(
    "/api/v1/hcs01/eval",
    response_model=EvaluationReport,
    summary="Run the retrieval benchmark",
)
async def run_evaluation() -> EvaluationReport:
    try:
        return run_benchmark_evaluation()
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@router.get("/", include_in_schema=False, response_model=ServiceBannerResponse)
async def show_service_banner() -> ServiceBannerResponse:
    return ServiceBannerResponse(
        service=SERVICE_NAME,
        docs="/docs",
        health="/api/v1/hcs01/health",
        chat="/api/v1/hcs01/query",
    )
