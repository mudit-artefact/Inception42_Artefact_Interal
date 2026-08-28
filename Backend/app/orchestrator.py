"""
app/orchestrator.py — Main Query Orchestrator combining LangGraph Router + RAG Agent

Flow:
    1. Fetch employee context from SQL Database
    2. Route query through LangGraph Query Router
    3. If terminal (greeting/not_in_scope/ambiguous) → return response
    4. If in_scope → pass rewritten query to LangGraph RAG Agent
    5. Return unified RAGResponse

Usage:
    from app.orchestrator import process_query

    result = process_query(
        user_query="Who is my manager?",
        employee_id="EMP001",
        target_language="en",
    )
"""

import logging
import time
from typing import Optional

from app.agents.query_router import route_query, QueryRouterState
from app.agents.rag_agent import run_rag_agent, get_session_history  # NEW: LangGraph RAG Agent
from app.rag_engine import RAGResponse, SourceCitation
# ══════════════════════════════════════════════════════════════════════════════
# ORIGINAL IMPORT (commented out — replaced by LangGraph RAG Agent)
# ══════════════════════════════════════════════════════════════════════════════
# from app.rag_engine import rag_engine, RAGResponse, SourceCitation
# ══════════════════════════════════════════════════════════════════════════════

from app.db.sql_tool import get_employee_full_sql_context
from app.mock_omni import _context_to_profile

logger = logging.getLogger(__name__)


def process_query(
    user_query: str,
    employee_id: str = "EMP001",
    target_language: str = "en",
    conversation_id: Optional[str] = None,
    # For clarification follow-up (sent from frontend)
    original_question: Optional[str] = None,
    user_clarification: Optional[str] = None,
) -> RAGResponse:
    """
    Main orchestration function that routes queries and handles all flows.

    Args:
        user_query: The user's question
        employee_id: Employee ID (e.g., "EMP001")
        target_language: "en" or "ar"
        conversation_id: Session/conversation ID for history
        original_question: (For clarification) The original ambiguous question
        user_clarification: (For clarification) The user's clarifying response

    Returns:
        RAGResponse with answer, sources, and metadata
    """
    start_time = time.time()
    conv_id = conversation_id or f"conv-{int(time.time() * 1000)}"

    # ── Step 1: Fetch employee context from SQL Database ──────────────
    sql_context = get_employee_full_sql_context(employee_id)
    employee_profile = _context_to_profile(sql_context)

    logger.info(
        f"Orchestrator: Processing query for {sql_context['name']} ({employee_id}) | "
        f"Query: '{user_query[:50]}...'"
    )

    # ── Step 1.5: Get conversation history for context ────────────────
    conversation_history = []
    try:
        history = get_session_history(conv_id)
        for msg in history.messages[-6:]:  # Last 6 messages (3 turns)
            role = "user" if hasattr(msg, 'type') and msg.type == 'human' else "assistant"
            if hasattr(msg, 'content'):
                conversation_history.append({"role": role, "content": str(msg.content)})
    except Exception as e:
        logger.warning(f"Could not fetch conversation history: {e}")

    # ── Step 2: Route query through LangGraph Query Router ────────────
    router_result = route_query(
        user_query=user_query,
        employee_id=employee_id,
        employee_name=sql_context.get("name", "Employee"),
        employee_name_ar=sql_context.get("name_ar", "موظف"),
        target_language=target_language,
        conversation_id=conv_id,
        original_question=original_question,
        user_clarification=user_clarification,
        conversation_history=conversation_history,
    )

    intent = router_result.get("intent", "unknown")
    confidence = router_result.get("confidence", 0.0)
    is_terminal = router_result.get("is_terminal", False)
    is_awaiting = router_result.get("is_awaiting_clarification", False)

    logger.info(
        f"Router result: intent={intent}, confidence={confidence:.2f}, "
        f"terminal={is_terminal}, awaiting={is_awaiting}"
    )

    # ── Step 3: Handle terminal flows (greeting/not_in_scope/ambiguous) ──
    if is_terminal:
        latency_ms = int((time.time() - start_time) * 1000)

        # Build sources for terminal responses
        sources = []

        # Add SQL source for greeting (shows we fetched employee data)
        if intent == "greeting":
            sources.append(
                SourceCitation(
                    id="src-sql-1",
                    title="Omni HR SQL Database",
                    source="SQL Database (omni_hr.db)",
                    source_type="database",
                    table_name="employees",
                    section=f"Employee: {sql_context['user_id']}",
                    score=1.0,
                    language=target_language,
                    snippet=f"Employee: {sql_context['name']} | Department: {sql_context['department']}",
                )
            )

        return RAGResponse(
            answer=router_result.get("response", ""),
            sources=sources,
            conversation_id=conv_id,
            employee_profile=employee_profile.model_dump(),
            target_language=target_language,
            latency_ms=latency_ms,
            tokens_used=0,  # No RAG tokens used for terminal flows
            intent=intent,
            rewritten_query=None,
            confidence_score=confidence,
            # Additional fields for clarification handling
            original_question=router_result.get("original_question"),
            clarifying_question=router_result.get("clarifying_question"),
            is_awaiting_clarification=is_awaiting,
        )

    # ══════════════════════════════════════════════════════════════════════════
    # Step 4: In-scope query → Continue to LangGraph RAG Agent (NEW)
    # ══════════════════════════════════════════════════════════════════════════
    rewritten_query = router_result.get("rewritten_query") or user_query

    logger.info(f"Passing to LangGraph RAG Agent: '{rewritten_query[:60]}...'")

    # Call the LangGraph RAG Agent
    rag_result = run_rag_agent(
        rewritten_query=rewritten_query,
        employee_id=employee_id,
        target_language=target_language,
        conversation_id=conv_id,
        original_query=user_query,
        intent=intent,
        confidence=confidence,
    )

    # Convert RAG Agent result dict to SourceCitation objects
    sources = [
        SourceCitation(**src) for src in rag_result.get("sources", [])
    ]

    total_latency = int((time.time() - start_time) * 1000)

    logger.info(
        f"Orchestrator complete: intent={intent}, "
        f"sources={len(sources)}, latency={total_latency}ms"
    )

    return RAGResponse(
        answer=rag_result.get("answer", ""),
        sources=sources,
        conversation_id=conv_id,
        employee_profile=rag_result.get("employee_profile", {}),
        target_language=target_language,
        latency_ms=total_latency,
        tokens_used=rag_result.get("tokens_used", 0),
        intent=intent,
        rewritten_query=rewritten_query,
        confidence_score=confidence,
        original_question=None,
        clarifying_question=None,
        is_awaiting_clarification=False,
    )

    # ══════════════════════════════════════════════════════════════════════════
    # ORIGINAL CODE (commented out — replaced by LangGraph RAG Agent above)
    # ══════════════════════════════════════════════════════════════════════════
    # rewritten_query = router_result.get("rewritten_query") or user_query
    #
    # logger.info(f"Passing to RAG Engine: '{rewritten_query[:60]}...'")
    #
    # # Call the existing RAG engine with the rewritten query
    # rag_result = rag_engine.query(
    #     user_query=rewritten_query,
    #     employee_id=employee_id,
    #     target_language=target_language,
    #     conversation_id=conv_id,
    # )
    #
    # # Augment the RAG result with router metadata
    # rag_result.intent = intent
    # rag_result.rewritten_query = rewritten_query
    # rag_result.confidence_score = confidence
    #
    # total_latency = int((time.time() - start_time) * 1000)
    # rag_result.latency_ms = total_latency
    #
    # logger.info(
    #     f"Orchestrator complete: intent={intent}, "
    #     f"sources={len(rag_result.sources)}, latency={total_latency}ms"
    # )
    #
    # return rag_result
    # ══════════════════════════════════════════════════════════════════════════


def process_query_stream(
    user_query: str,
    employee_id: str = "EMP001",
    target_language: str = "en",
    conversation_id: Optional[str] = None,
):
    """
    Streaming version of process_query for SSE/WebSocket endpoints.

    NOTE: Currently uses the old rag_engine for streaming.
    TODO: Implement streaming in LangGraph RAG Agent.

    Yields:
        For terminal flows: Single chunk with complete response
        For in_scope: Streamed chunks from RAG engine
    """
    # Import here to avoid circular import and keep streaming working
    from app.rag_engine import rag_engine

    conv_id = conversation_id or f"conv-{int(time.time() * 1000)}"

    # Fetch employee context
    sql_context = get_employee_full_sql_context(employee_id)

    # Route query
    router_result = route_query(
        user_query=user_query,
        employee_id=employee_id,
        employee_name=sql_context.get("name", "Employee"),
        employee_name_ar=sql_context.get("name_ar", "موظف"),
        target_language=target_language,
        conversation_id=conv_id,
    )

    # Terminal flow — yield complete response
    if router_result.get("is_terminal"):
        yield router_result.get("response", "")
        return

    # In-scope — stream from RAG engine (still uses old engine for streaming)
    rewritten_query = router_result.get("rewritten_query") or user_query

    for chunk in rag_engine.stream_query(
        user_query=rewritten_query,
        employee_id=employee_id,
        target_language=target_language,
        conversation_id=conv_id,
    ):
        yield chunk
