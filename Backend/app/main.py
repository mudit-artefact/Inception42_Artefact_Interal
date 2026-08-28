"""
app/main.py — FastAPI application: routing, CORS, startup ingestion
"""
import logging
import os
from contextlib import asynccontextmanager
from typing import Literal, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import settings
from app.mock_omni import router as omni_router
from app.rag_engine import RAGResponse
from app.orchestrator import process_query
from app import vector_store

# ── Logging ───────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Startup / Shutdown ────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Auto-seed SQLite database and auto-ingest policies on startup."""
    logger.info("🚀 HCS-01 starting up...")

    # 1. Initialize & Seed SQL Database
    try:
        from app.db.session import init_and_seed_db
        init_and_seed_db()
        logger.info("✅ Omni HR SQL Database ready")
    except Exception as e:
        logger.error(f"⚠️  SQL Database initialization failed: {e}")

    # 2. Initialize Qdrant Vector Store
    try:
        vector_store.ensure_collection()
        count = vector_store.collection_count()
        if count == 0:
            logger.info("Qdrant collection is empty — running initial policy ingestion...")
            n = vector_store.ingest_policies()
            logger.info(f"✅ Ingested {n} chunks into Qdrant")
        else:
            logger.info(f"✅ Qdrant ready — {count} vectors loaded")
    except Exception as e:
        logger.error(f"⚠️  Startup ingestion failed: {e}")
        logger.warning("The API will start but RAG queries will fail until Qdrant is available.")

    yield

    logger.info("HCS-01 shutting down — goodbye!")


# ── FastAPI App ───────────────────────────────────────────────────

app = FastAPI(
    title="HCS-01 Policy & Leave Concierge API",
    description=(
        "Bilingual (English/Arabic) RAG-powered HR assistant for HC Services. "
        "Retrieves policy context from Qdrant and generates answers via GPT-4o."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow Vite dev server, Streamlit, and any localhost origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8501",
        "http://127.0.0.1:8501",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Mock Omni routes
app.include_router(omni_router)


# ── Request / Response Models ─────────────────────────────────────

class QueryRequest(BaseModel):
    query: Optional[str] = None
    message: Optional[str] = None
    employee_id: str = "EMP001"
    conversation_id: Optional[str] = None
    target_language: Optional[Literal["en", "ar"]] = None
    # For clarification follow-up (ambiguous query handling)
    original_question: Optional[str] = None
    user_clarification: Optional[str] = None


class IngestResponse(BaseModel):
    status: str
    chunks_indexed: int
    message: str


def _detect_language(text: str) -> Literal["en", "ar"]:
    """Detect if text contains Arabic characters."""
    import re
    if re.search(r"[\u0600-\u06FF]", text):
        return "ar"
    return "en"


# ── Core Endpoints ────────────────────────────────────────────────

@app.post(
    "/api/v1/hcs01/query",
    response_model=RAGResponse,
    summary="HCS-01 RAG Query (consumable by HCS-02 & React UI)",
    tags=["HCS-01 RAG"],
)
@app.post(
    "/chat",
    response_model=RAGResponse,
    summary="Chat endpoint (Frontend compatible)",
    tags=["HCS-01 RAG"],
)
@app.post(
    "/api/chat",
    response_model=RAGResponse,
    summary="Chat endpoint (API prefixed)",
    tags=["HCS-01 RAG"],
)
async def hcs01_query(request: QueryRequest) -> RAGResponse:
    """
    Main RAG endpoint for both Frontend UI and external orchestrators.

    Flow:
    1. Route query through LangGraph Query Router (classify intent)
    2. Terminal flows (greeting/not_in_scope/ambiguous) return immediately
    3. In-scope queries are rewritten and passed to RAG Engine

    Supports clarification follow-up for ambiguous queries:
    - If previous response had is_awaiting_clarification=True
    - Frontend sends original_question + user_clarification in next request
    """
    text = (request.query or request.message or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="Query or message cannot be empty.")

    target_lang = request.target_language or _detect_language(text)
    emp_id = request.employee_id or "EMP001"

    try:
        result = process_query(
            user_query=text,
            employee_id=emp_id,
            target_language=target_lang,
            conversation_id=request.conversation_id,
            original_question=request.original_question,
            user_clarification=request.user_clarification,
        )
        return result
    except RuntimeError as e:
        # E.g., missing API key
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Query processing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


from pathlib import Path
from fastapi.staticfiles import StaticFiles

# ── Static File Mount for Official Policy PDFs ─────────────────────
base_data_dir = Path(__file__).resolve().parent.parent / "data"
pdfs_path = base_data_dir / "policies_pdf"
pdfs_path.mkdir(parents=True, exist_ok=True)

app.mount("/api/v1/hcs01/policies/pdf", StaticFiles(directory=str(pdfs_path)), name="policies_pdf")


@app.get(
    "/api/v1/hcs01/policies",
    summary="List available HR policies with official PDF links",
    tags=["HCS-01 RAG"],
)
async def list_policies():
    """Returns official policy metadata and downloadable PDF URLs."""
    return [
        {
            "id": "HC-PC-001",
            "title": "Annual Leave Policy",
            "section": "HC-PC-001",
            "topics": ["Entitlement", "Notice period", "Carry-over rules", "Approval Flowchart"],
            "pdf_url": "/api/v1/hcs01/policies/pdf/01_annual_leave_policy.pdf",
            "url": "/api/v1/hcs01/policies/pdf/01_annual_leave_policy.pdf",
            "diagram_page": 2,
        },
        {
            "id": "HC-PC-002",
            "title": "Sick Leave & Medical Certificates",
            "section": "HC-PC-002",
            "topics": ["Allowance", "Certificates", "Bradford Factor Formula", "Decision Tree"],
            "pdf_url": "/api/v1/hcs01/policies/pdf/02_sick_leave_policy.pdf",
            "url": "/api/v1/hcs01/policies/pdf/02_sick_leave_policy.pdf",
            "diagram_page": 2,
        },
        {
            "id": "HC-PC-003",
            "title": "Probation & Onboarding Policy",
            "section": "HC-PC-003",
            "topics": ["Duration", "Reviews", "Probation Milestones", "Evaluation Schedule"],
            "pdf_url": "/api/v1/hcs01/policies/pdf/03_probation_policy.pdf",
            "url": "/api/v1/hcs01/policies/pdf/03_probation_policy.pdf",
            "diagram_page": 1,
        },
        {
            "id": "HC-PC-004",
            "title": "Flexible & Remote Work Policy",
            "section": "HC-PC-004",
            "topics": ["Hybrid schedule", "Eligibility Matrix", "Core Hours", "Security"],
            "pdf_url": "/api/v1/hcs01/policies/pdf/04_remote_work_policy.pdf",
            "url": "/api/v1/hcs01/policies/pdf/04_remote_work_policy.pdf",
            "diagram_page": 1,
        },
        {
            "id": "HC-PC-005",
            "title": "Expense Claims & Reimbursement",
            "section": "HC-PC-005",
            "topics": ["Travel", "Per diem", "Authorization Tiers", "Approval Thresholds"],
            "pdf_url": "/api/v1/hcs01/policies/pdf/05_expense_claims_policy.pdf",
            "url": "/api/v1/hcs01/policies/pdf/05_expense_claims_policy.pdf",
            "diagram_page": 1,
        },
    ]


@app.get(
    "/api/v1/hcs01/ingest",
    response_model=IngestResponse,
    summary="Trigger policy re-ingestion",
    tags=["HCS-01 RAG"],
)
async def trigger_ingest(force: bool = False) -> IngestResponse:
    """
    Re-ingest all policy documents into Qdrant.
    Set `force=true` to overwrite existing vectors.
    """
    try:
        n = vector_store.ingest_policies(force=force)
        if n == 0 and not force:
            return IngestResponse(
                status="skipped",
                chunks_indexed=0,
                message="Collection already has vectors. Use ?force=true to re-ingest.",
            )
        return IngestResponse(
            status="success",
            chunks_indexed=n,
            message=f"Successfully indexed {n} policy chunks into Qdrant.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/v1/hcs01/eval",
    summary="Run automated technical benchmarks evaluation",
    tags=["HCS-01 RAG"],
)
async def get_eval_benchmarks():
    """Executes the automated benchmark evaluation suite and returns precision & recall metrics."""
    try:
        from app.evaluator import run_benchmark_evaluation
        report = run_benchmark_evaluation()
        return report.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/v1/hcs01/health",
    summary="Health check",
    tags=["HCS-01 RAG"],
)
async def health_check():
    """Check API, Qdrant connectivity, and vector count."""
    try:
        count = vector_store.collection_count()
        qdrant_ok = True
    except Exception:
        count = 0
        qdrant_ok = False

    return {
        "status": "ok" if qdrant_ok else "degraded",
        "service": "HCS-01 Policy & Leave Concierge",
        "version": "1.0.0",
        "qdrant_connected": qdrant_ok,
        "vectors_indexed": count,
        "llm_model": settings.llm_model,
        "embedding_model": settings.embedding_model,
    }


@app.get("/", include_in_schema=False)
async def root():
    return {
        "service": "HCS-01 Policy & Leave Concierge",
        "docs": "/docs",
        "health": "/api/v1/hcs01/health",
        "chat": "/chat",
    }


# ── Entry Point ───────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level="info",
    )
