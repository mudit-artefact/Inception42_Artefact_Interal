"""
app/agents/rag_agent.py — LangGraph RAG Agent for HCS-01

Pipeline:
    1. sql_context_node    → Fetch employee data from SQLite
    2. retriever_node      → Hybrid search Qdrant (dense + BM25)
    3. prompt_builder_node → Build system prompt with SQL + chunks
    4. generator_node      → Call LLM with full context
    5. response_node       → Format citations, save history

Usage:
    from app.agents.rag_agent import run_rag_agent

    result = run_rag_agent(
        rewritten_query="Who is my current line manager?",
        employee_id="EMP001",
        target_language="en",
        conversation_id="conv-123",
    )
"""

import logging
import time
from typing import Optional
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel

import litellm
import tenacity
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage

from app.config import settings
from app.db.sql_tool import get_employee_full_sql_context
from app.mock_omni import _context_to_profile
from app.prompts import build_system_prompt, format_chunks
from app import vector_store

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# STATE SCHEMA
# ══════════════════════════════════════════════════════════════════════════════

class RAGAgentState(TypedDict):
    """State for the RAG Agent graph."""

    # Input (from Router/Orchestrator)
    rewritten_query: str
    original_query: str
    employee_id: str
    target_language: str
    conversation_id: str
    intent: str
    confidence: float

    # Timing
    start_time: float

    # SQL Context (from sql_context_node)
    sql_context: dict
    employee_profile: dict

    # Retrieved chunks (from retriever_node)
    retrieved_chunks: list
    retrieved_context_str: str

    # Prompt (from prompt_builder_node)
    system_prompt: str
    messages: list

    # Generation (from generator_node)
    answer: str
    tokens_used: int

    # Final output (from response_node)
    sources: list
    latency_ms: int


# ══════════════════════════════════════════════════════════════════════════════
# POLICY TITLE LOOKUP (for citations)
# ══════════════════════════════════════════════════════════════════════════════

DOC_TITLES = {
    "HC-PC-001": "Annual Leave Policy",
    "HC-PC-002": "Sick Leave & Medical Certificates",
    "HC-PC-003": "Probation & Onboarding Policy",
    "HC-PC-004": "Flexible & Remote Work Policy",
    "HC-PC-005": "Expense Claims & Reimbursement",
}


def clean_snippet(raw_text: str) -> str:
    """Strip raw markdown headers and formatting for a clean, concise snippet."""
    import re
    if not raw_text:
        return ""
    text = re.sub(r"^#+\s*", "", raw_text, flags=re.MULTILINE)
    text = re.sub(r"[*_]{1,3}", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > 160:
        text = text[:155].rstrip() + "…"
    return text


# ══════════════════════════════════════════════════════════════════════════════
# LANGCHAIN SESSION HISTORY (shared with existing rag_engine)
# ══════════════════════════════════════════════════════════════════════════════

_session_histories: dict[str, InMemoryChatMessageHistory] = {}


def get_session_history(session_id: str) -> InMemoryChatMessageHistory:
    """Retrieve or create a LangChain InMemoryChatMessageHistory for a given session ID."""
    if session_id not in _session_histories:
        _session_histories[session_id] = InMemoryChatMessageHistory()
    return _session_histories[session_id]


# ══════════════════════════════════════════════════════════════════════════════
# LLM CALL WITH RETRY
# ══════════════════════════════════════════════════════════════════════════════

@tenacity.retry(
    stop=tenacity.stop_after_attempt(3),
    wait=tenacity.wait_exponential(multiplier=1, min=1, max=4),
    reraise=True,
)
def _call_llm_with_retry(**kwargs):
    return litellm.completion(**kwargs)


# ══════════════════════════════════════════════════════════════════════════════
# NODE 1: SQL CONTEXT
# ══════════════════════════════════════════════════════════════════════════════

def sql_context_node(state: RAGAgentState) -> dict:
    """Fetch employee profile, balances, manager history from SQL database."""

    employee_id = state["employee_id"]

    logger.info(f"[RAG Agent] sql_context_node: Fetching data for {employee_id}")

    sql_context = get_employee_full_sql_context(employee_id)
    employee_profile = _context_to_profile(sql_context)

    logger.info(
        f"[RAG Agent] sql_context_node: {sql_context['name']} | "
        f"Manager: {sql_context['manager_name']} | "
        f"AL: {sql_context['annual_leave_balance']} days"
    )

    return {
        "sql_context": sql_context,
        "employee_profile": employee_profile.model_dump(),
    }


# ══════════════════════════════════════════════════════════════════════════════
# NODE 2: RETRIEVER
# ══════════════════════════════════════════════════════════════════════════════

def retriever_node(state: RAGAgentState) -> dict:
    """Hybrid search Qdrant for relevant policy chunks."""

    query = state["rewritten_query"]
    target_lang = state["target_language"]

    logger.info(f"[RAG Agent] retriever_node: Searching for '{query[:50]}...'")

    chunks = vector_store.search(
        query=query,
        top_k=settings.rag_top_k,
        language_filter=target_lang,
    )

    logger.info(f"[RAG Agent] retriever_node: Retrieved {len(chunks)} chunks")

    # Format chunks for prompt
    retrieved_context_str = format_chunks(chunks)

    return {
        "retrieved_chunks": chunks,
        "retrieved_context_str": retrieved_context_str,
    }


# ══════════════════════════════════════════════════════════════════════════════
# NODE 3: PROMPT BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def prompt_builder_node(state: RAGAgentState) -> dict:
    """Build system prompt with SQL context + retrieved chunks."""

    sql_context = state["sql_context"]
    retrieved_context_str = state["retrieved_context_str"]
    target_lang = state["target_language"]
    conv_id = state["conversation_id"]
    user_query = state["original_query"] or state["rewritten_query"]

    logger.info(f"[RAG Agent] prompt_builder_node: Building prompt for {conv_id}")

    # Build system prompt
    system_prompt = build_system_prompt(
        target_language=target_lang,
        sql_context=sql_context,
        retrieved_chunks=retrieved_context_str,
    )

    # Load conversation history
    history = get_session_history(conv_id)

    # Build messages: System + History (last 6 turns) + Current query
    langchain_messages: list[BaseMessage] = [SystemMessage(content=system_prompt)]
    prior_messages = history.messages[-6:] if history.messages else []
    langchain_messages.extend(prior_messages)
    langchain_messages.append(HumanMessage(content=user_query))

    # Convert to dict format for LiteLLM
    messages = []
    for msg in langchain_messages:
        if isinstance(msg, SystemMessage):
            messages.append({"role": "system", "content": str(msg.content)})
        elif isinstance(msg, HumanMessage):
            messages.append({"role": "user", "content": str(msg.content)})
        elif isinstance(msg, AIMessage):
            messages.append({"role": "assistant", "content": str(msg.content)})

    return {
        "system_prompt": system_prompt,
        "messages": messages,
    }


# ══════════════════════════════════════════════════════════════════════════════
# NODE 4: GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

def generator_node(state: RAGAgentState) -> dict:
    """Call LLM with full context to generate answer."""

    messages = state["messages"]

    logger.info(f"[RAG Agent] generator_node: Calling LLM ({settings.llm_model})")

    completion_kwargs = {
        "model": settings.llm_model,
        "messages": messages,
        "max_tokens": settings.max_tokens,
    }
    if "gemini" not in settings.llm_model.lower():
        completion_kwargs["temperature"] = 0.1

    response = _call_llm_with_retry(**completion_kwargs)

    answer = response.choices[0].message.content or ""
    tokens_used = response.usage.total_tokens if response.usage else 0

    logger.info(f"[RAG Agent] generator_node: Generated {len(answer)} chars, {tokens_used} tokens")

    return {
        "answer": answer,
        "tokens_used": tokens_used,
    }


# ══════════════════════════════════════════════════════════════════════════════
# NODE 5: RESPONSE
# ══════════════════════════════════════════════════════════════════════════════

def response_node(state: RAGAgentState) -> dict:
    """Format final response with citations and save to history."""

    sql_context = state["sql_context"]
    chunks = state["retrieved_chunks"]
    target_lang = state["target_language"]
    conv_id = state["conversation_id"]
    user_query = state["original_query"] or state["rewritten_query"]
    answer = state["answer"]
    start_time = state["start_time"]

    logger.info(f"[RAG Agent] response_node: Building citations")

    # Save turn to LangChain history
    history = get_session_history(conv_id)
    history.add_user_message(user_query)
    history.add_ai_message(answer)

    # Build sources list
    # 1. SQL Database citation
    sql_snippet = (
        f"Employee: {sql_context['name']} ({sql_context['user_id']}) | "
        f"Department: {sql_context['department']} | "
        f"Annual Leave: {sql_context['annual_leave_balance']} days remaining | "
        f"Sick Leave: {sql_context['sick_leave_balance']} days remaining | "
        f"Line Manager: {sql_context['manager_name']}"
    )

    sources = [
        {
            "id": "src-sql-1",
            "title": "Omni HR SQL Database (omni_hr.db)",
            "source": "SQL Database (omni_hr.db)",
            "source_type": "database",
            "table_name": "employees, leave_balances",
            "section": f"Record: {sql_context['user_id']} ({sql_context['name']})",
            "page_number": None,
            "score": 1.0,
            "language": target_lang,
            "snippet": sql_snippet,
            "url": "#",
            "pdf_url": None,
            "has_image": False,
        }
    ]

    # 2. Policy document citations
    for idx, c in enumerate(chunks):
        doc_title = c.get("title") or DOC_TITLES.get(c["source"], c["source"])
        snippet_text = clean_snippet(c.get("text", ""))
        pdf_url = c.get("pdf_url") or "#"
        page_no = c.get("page_number", 1)

        sources.append({
            "id": f"src-policy-{idx+1}",
            "title": doc_title,
            "source": c["source"],
            "source_type": "policy",
            "table_name": None,
            "section": c.get("section", f"Page {page_no}"),
            "page_number": page_no,
            "score": c["score"],
            "language": c.get("language", target_lang),
            "snippet": snippet_text,
            "url": pdf_url,
            "pdf_url": pdf_url,
            "has_image": c.get("has_image", False),
        })

    # Calculate latency
    latency_ms = int((time.time() - start_time) * 1000)

    logger.info(
        f"[RAG Agent] response_node: Complete | "
        f"{len(sources)} sources | {latency_ms}ms"
    )

    return {
        "sources": sources,
        "latency_ms": latency_ms,
    }


# ══════════════════════════════════════════════════════════════════════════════
# BUILD THE GRAPH
# ══════════════════════════════════════════════════════════════════════════════

def build_rag_agent_graph() -> StateGraph:
    """Build and compile the RAG Agent LangGraph."""

    graph = StateGraph(RAGAgentState)

    # Add nodes
    graph.add_node("sql_context_node", sql_context_node)
    graph.add_node("retriever_node", retriever_node)
    graph.add_node("prompt_builder_node", prompt_builder_node)
    graph.add_node("generator_node", generator_node)
    graph.add_node("response_node", response_node)

    # Linear flow: START → sql → retriever → prompt → generator → response → END
    graph.add_edge(START, "sql_context_node")
    graph.add_edge("sql_context_node", "retriever_node")
    graph.add_edge("retriever_node", "prompt_builder_node")
    graph.add_edge("prompt_builder_node", "generator_node")
    graph.add_edge("generator_node", "response_node")
    graph.add_edge("response_node", END)

    return graph.compile()


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON GRAPH INSTANCE
# ══════════════════════════════════════════════════════════════════════════════

rag_agent_graph = build_rag_agent_graph()


# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTION FOR EASY INVOCATION
# ══════════════════════════════════════════════════════════════════════════════

def run_rag_agent(
    rewritten_query: str,
    employee_id: str = "EMP001",
    target_language: str = "en",
    conversation_id: str = "",
    original_query: Optional[str] = None,
    intent: str = "in_scope",
    confidence: float = 1.0,
) -> dict:
    """
    Run the RAG Agent pipeline.

    Args:
        rewritten_query: The query (rewritten by Router) for retrieval
        employee_id: Employee ID (e.g., "EMP001")
        target_language: "en" or "ar"
        conversation_id: Session ID for history
        original_query: Original user query (before rewriting)
        intent: Intent from Router
        confidence: Confidence from Router

    Returns:
        dict with: answer, sources, tokens_used, latency_ms, employee_profile, etc.
    """

    initial_state: RAGAgentState = {
        "rewritten_query": rewritten_query,
        "original_query": original_query or rewritten_query,
        "employee_id": employee_id,
        "target_language": target_language,
        "conversation_id": conversation_id or f"conv-{int(time.time() * 1000)}",
        "intent": intent,
        "confidence": confidence,
        "start_time": time.time(),
        "sql_context": {},
        "employee_profile": {},
        "retrieved_chunks": [],
        "retrieved_context_str": "",
        "system_prompt": "",
        "messages": [],
        "answer": "",
        "tokens_used": 0,
        "sources": [],
        "latency_ms": 0,
    }

    # Run the graph
    result = rag_agent_graph.invoke(initial_state)

    return result


# ══════════════════════════════════════════════════════════════════════════════
# CLI TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(__file__).replace("app/agents/rag_agent.py", ""))

    from dotenv import load_dotenv
    load_dotenv()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")

    test_queries = [
        "Who is my current line manager?",
        "How many annual leave days do I have remaining?",
        "What is the sick leave policy?",
    ]

    print("\n" + "=" * 70)
    print("RAG AGENT TEST")
    print("=" * 70)

    for query in test_queries:
        print(f"\n{'─' * 70}")
        print(f"Query: \"{query}\"")
        print(f"{'─' * 70}")

        result = run_rag_agent(
            rewritten_query=query,
            employee_id="EMP001",
            target_language="en",
        )

        print(f"Latency: {result['latency_ms']}ms")
        print(f"Tokens: {result['tokens_used']}")
        print(f"Sources: {len(result['sources'])}")
        print(f"Answer:\n{result['answer'][:300]}...")

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)
