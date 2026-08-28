"""
app/rag_engine.py — Core Hybrid RAG & SQL Pipeline: SQL Database → Vector Store → LangChain History → LLM
"""
import logging
import re
import time
from typing import Iterator, Optional

import litellm
import tenacity
from pydantic import BaseModel
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage

from app.config import settings
from app.db.sql_tool import get_employee_full_sql_context, execute_employee_sql
from app.mock_omni import _context_to_profile, EmployeeProfile
from app.prompts import build_system_prompt, format_chunks
from app import vector_store

logger = logging.getLogger(__name__)


# ── Policy Title Lookup ───────────────────────────────────────────
DOC_TITLES = {
    "HC-PC-001": "Annual Leave Policy",
    "HC-PC-002": "Sick Leave & Medical Certificates",
    "HC-PC-003": "Probation & Onboarding Policy",
    "HC-PC-004": "Flexible & Remote Work Policy",
    "HC-PC-005": "Expense Claims & Reimbursement",
}


def clean_snippet(raw_text: str) -> str:
    """Strip raw markdown headers and formatting for a clean, concise snippet."""
    if not raw_text:
        return ""
    text = re.sub(r"^#+\s*", "", raw_text, flags=re.MULTILINE)
    text = re.sub(r"[*_]{1,3}", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > 160:
        text = text[:155].rstrip() + "…"
    return text


# ── Response Models ───────────────────────────────────────────────

class SourceCitation(BaseModel):
    id: Optional[str] = None
    title: str = ""
    source: str
    source_type: Optional[str] = "policy"  # "policy" | "database"
    table_name: Optional[str] = None
    section: str
    page_number: Optional[int] = 1
    score: float
    language: str = "en"
    snippet: Optional[str] = None
    url: Optional[str] = "#"
    pdf_url: Optional[str] = None
    has_image: Optional[bool] = False


class RAGResponse(BaseModel):
    answer: str
    sources: list[SourceCitation] = []
    conversation_id: str
    employee_profile: dict = {}
    target_language: str = "en"
    latency_ms: int = 0
    tokens_used: int = 0
    intent: Optional[str] = "policy_inquiry"
    rewritten_query: Optional[str] = None
    confidence_score: Optional[float] = 1.0
    # Clarification handling (for ambiguous queries)
    original_question: Optional[str] = None
    clarifying_question: Optional[str] = None
    is_awaiting_clarification: bool = False


# ── LangChain Session Chat Message History ───────────────────────
_session_histories: dict[str, InMemoryChatMessageHistory] = {}


def get_session_history(session_id: str) -> InMemoryChatMessageHistory:
    """Retrieve or create a LangChain InMemoryChatMessageHistory for a given session ID."""
    if session_id not in _session_histories:
        _session_histories[session_id] = InMemoryChatMessageHistory()
    return _session_histories[session_id]


def get_langchain_history(session_id: str) -> list[dict]:
    """Retrieve formatted message history from LangChain memory."""
    history = get_session_history(session_id)
    return [
        {
            "role": "user" if isinstance(m, HumanMessage) else "assistant" if isinstance(m, AIMessage) else "system",
            "content": str(m.content),
        }
        for m in history.messages
    ]


def clear_langchain_history(session_id: str) -> None:
    """Clear LangChain message history for a session."""
    if session_id in _session_histories:
        _session_histories[session_id].clear()


@tenacity.retry(
    stop=tenacity.stop_after_attempt(3),
    wait=tenacity.wait_exponential(multiplier=1, min=1, max=4),
    reraise=True,
)
def _call_llm_with_retry(**kwargs):
    return litellm.completion(**kwargs)


# ── Hybrid RAG & SQL Engine ───────────────────────────────────────

class RAGEngine:
    """
    Hybrid RAG & SQL Engine for HCS-01.

    Flow:
      1. Fetch live employee profile, balances, manager history, and requests from SQLite omni_hr.db.
      2. Embed user query (multilingual — works for EN & AR).
      3. Retrieve top-K relevant policy chunks from Qdrant vector store.
      4. Assemble system prompt with ground-truth SQL facts + multimodal diagram context.
      5. Load LangChain conversation history for the session.
      6. Generate answer via LLM (Gemini Flash) with full multi-turn context.
      7. Save user turn and AI response to LangChain ChatMessageHistory.
      8. Return structured RAGResponse with rich multimodal sources.
    """

    def query(
        self,
        user_query: str,
        employee_id: str = "EMP001",
        target_language: str = "en",
        conversation_id: Optional[str] = None,
    ) -> RAGResponse:
        """
        Synchronous RAG query combining SQL Database facts, Hybrid Qdrant search, Query Rewriting, and LangChain memory.
        """
        from app.query_transform import QueryTransformer

        start_time = time.time()
        conv_id = conversation_id or f"conv-{int(time.time() * 1000)}"

        # ── Step 1: Query Transformation & Intent Classification ──
        t_res = QueryTransformer.transform(user_query, target_language)
        effective_lang = t_res.target_language or target_language

        # ── Step 2: Fetch live relational context from SQL Database ──
        sql_context = get_employee_full_sql_context(employee_id)
        employee_profile = _context_to_profile(sql_context)
        logger.info(
            f"Employee from SQL DB: {sql_context['name']} ({employee_id}) | "
            f"Intent: {t_res.intent} | Manager: {sql_context['manager_name']}"
        )

        history = get_session_history(conv_id)

        # ── Step 3: Handle Proactive Greeting / Onboarding Intent ──
        if t_res.is_greeting:
            latency_ms = int((time.time() - start_time) * 1000)
            if effective_lang == "ar":
                answer = (
                    f"👋 **أهلاً بك يا {sql_context['name_ar']} في منصة إتش سي سيرفيسز للموارد البشرية!**\n\n"
                    f"إليك ملخص سريع لحالتك الوظيفية الحالية من قاعدة البيانات:\n"
                    f"* 🌴 **رصيد الإجازة السنوية:** **{sql_context['annual_leave_balance']} يوماً متبقياً** (+{sql_context['carry_over_days']} أيام مرحلة)\n"
                    f"* 🤒 **رصيد الإجازة المرضية:** **{sql_context['sick_leave_balance']} يوماً متاحاً**\n"
                    f"* 👔 **المدير المباشر:** **{sql_context['manager_name']}** ({sql_context.get('manager_role', 'المدير المباشر')})\n"
                    f"* 💼 **القسم والمسمى:** {sql_context['department']} — {sql_context['role']}\n\n"
                    f"كيف يمكنني مساعدتك في استفسارات سياسات العمل أو طلبات الإجازات اليوم؟"
                )
            else:
                answer = (
                    f"👋 **Welcome to HC Services Policy & Leave Concierge, {sql_context['name']}!**\n\n"
                    f"Here is your real-time HR overview:\n"
                    f"* 🌴 **Annual Leave:** **{sql_context['annual_leave_balance']} days remaining** (+{sql_context['carry_over_days']} days carry-over)\n"
                    f"* 🤒 **Sick Leave:** **{sql_context['sick_leave_balance']} days available**\n"
                    f"* 👔 **Current Line Manager:** **{sql_context['manager_name']}** ({sql_context.get('manager_role', 'Line Manager')})\n"
                    f"* 💼 **Department & Role:** {sql_context['department']} — {sql_context['role']}\n\n"
                    f"How can I assist you with company policies, leave requests, or expense claims today?"
                )

            history.add_user_message(user_query)
            history.add_ai_message(answer)

            sql_source = SourceCitation(
                id="src-sql-1",
                title="Omni HR SQL Database (omni_hr.db)",
                source="SQL Database (omni_hr.db)",
                source_type="database",
                table_name="employees, leave_balances",
                section=f"Record: {sql_context['user_id']} ({sql_context['name']})",
                page_number=None,
                score=1.0,
                language=effective_lang,
                snippet=f"Live SQL State: {sql_context['name']} | Leaves: {sql_context['annual_leave_balance']}d remaining | Manager: {sql_context['manager_name']}",
                url="#",
                pdf_url=None,
                has_image=False,
            )

            return RAGResponse(
                answer=answer,
                sources=[sql_source],
                conversation_id=conv_id,
                employee_profile=employee_profile.model_dump(),
                target_language=effective_lang,
                latency_ms=latency_ms,
                tokens_used=180,
                intent=t_res.intent,
                rewritten_query=t_res.rewritten_query,
                confidence_score=t_res.confidence_score,
            )

        # ── Step 4: Handle Out-of-Domain Guardrail (Grounded Abstain) ──
        if t_res.is_out_of_domain:
            latency_ms = int((time.time() - start_time) * 1000)
            if effective_lang == "ar":
                answer = (
                    "عذراً، أنا مخصص حصرياً للمساعدة في سياسات الموارد البشرية ولوائح الإجازات وبدلات العمل الخاصة بشركة إتش سي سيرفيسز. "
                    "لا يمكنني الإجابة على موضوعات خارج نطاق سياسات الشركة. كيف يمكنني مساعدتك في استفساراتك الوظيفية؟"
                )
            else:
                answer = (
                    "I am dedicated strictly to assisting with HC Services internal HR policies, leave balances, manager reporting, and employee benefits. "
                    "I cannot assist with questions outside our company HR policies. How can I help with your workplace questions today?"
                )

            history.add_user_message(user_query)
            history.add_ai_message(answer)

            return RAGResponse(
                answer=answer,
                sources=[],
                conversation_id=conv_id,
                employee_profile=employee_profile.model_dump(),
                target_language=effective_lang,
                latency_ms=latency_ms,
                tokens_used=120,
                intent=t_res.intent,
                rewritten_query=t_res.rewritten_query,
                confidence_score=0.99,
            )

        # ── Step 5: Hybrid Retrieval from Vector Store using Rewritten Query ──
        chunks = vector_store.search(
            query=t_res.rewritten_query,
            top_k=settings.rag_top_k,
            language_filter=effective_lang,
        )
        logger.info(f"Retrieved {len(chunks)} chunks using rewritten query: '{t_res.rewritten_query[:60]}...'")

        # ── Step 6: Assemble prompt with full SQL Relational context ──
        retrieved_context = format_chunks(chunks)
        system_prompt = build_system_prompt(
            target_language=effective_lang,
            sql_context=sql_context,
            retrieved_chunks=retrieved_context,
        )

        # Build LangChain messages: SystemMessage + prior History (last 6 turns) + current HumanMessage
        langchain_messages: list[BaseMessage] = [SystemMessage(content=system_prompt)]
        prior_messages = history.messages[-6:] if history.messages else []
        langchain_messages.extend(prior_messages)
        langchain_messages.append(HumanMessage(content=user_query))

        # Convert LangChain messages to standard dict format for LiteLLM execution
        messages = []
        for msg in langchain_messages:
            if isinstance(msg, SystemMessage):
                messages.append({"role": "system", "content": str(msg.content)})
            elif isinstance(msg, HumanMessage):
                messages.append({"role": "user", "content": str(msg.content)})
            elif isinstance(msg, AIMessage):
                messages.append({"role": "assistant", "content": str(msg.content)})

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

        # Save turn to LangChain ChatMessageHistory
        history.add_user_message(user_query)
        history.add_ai_message(answer)

        # ── Step 7: Build structured response with SQL DB + PDF Policy Citations ──
        latency_ms = int((time.time() - start_time) * 1000)

        # 1. SQL Database Record Citation
        sql_snippet = (
            f"Employee: {sql_context['name']} ({sql_context['user_id']}) | "
            f"Department: {sql_context['department']} | "
            f"Annual Leave: {sql_context['annual_leave_balance']} days remaining | "
            f"Sick Leave: {sql_context['sick_leave_balance']} days remaining | "
            f"Carry-Over: {sql_context['carry_over_days']} days | "
            f"Line Manager: {sql_context['manager_name']}"
        )

        sources = [
            SourceCitation(
                id="src-sql-1",
                title="Omni HR SQL Database (omni_hr.db)",
                source="SQL Database (omni_hr.db)",
                source_type="database",
                table_name="employees, leave_balances",
                section=f"Record: {sql_context['user_id']} ({sql_context['name']})",
                page_number=None,
                score=1.0,
                language=effective_lang,
                snippet=sql_snippet,
                url="#",
                pdf_url=None,
                has_image=False,
            )
        ]

        # 2. PDF Policy Document Citations
        for idx, c in enumerate(chunks):
            doc_title = c.get("title") or DOC_TITLES.get(c["source"], c["source"])
            snippet_text = clean_snippet(c.get("text", ""))
            pdf_url = c.get("pdf_url") or "#"
            page_no = c.get("page_number", 1)
            sources.append(
                SourceCitation(
                    id=f"src-policy-{idx+1}",
                    title=doc_title,
                    source=c["source"],
                    source_type="policy",
                    table_name=None,
                    section=c.get("section", f"Page {page_no}"),
                    page_number=page_no,
                    score=c["score"],
                    language=c.get("language", effective_lang),
                    snippet=snippet_text,
                    url=pdf_url,
                    pdf_url=pdf_url,
                    has_image=c.get("has_image", False),
                )
            )

        logger.info(f"Hybrid RAG complete [LangChain Session: {conv_id}] | intent={t_res.intent} | lang={effective_lang} | {latency_ms}ms | {tokens_used} tokens")

        return RAGResponse(
            answer=answer,
            sources=sources,
            conversation_id=conv_id,
            employee_profile=employee_profile.model_dump(),
            target_language=effective_lang,
            latency_ms=latency_ms,
            tokens_used=tokens_used,
            intent=t_res.intent,
            rewritten_query=t_res.rewritten_query,
            confidence_score=t_res.confidence_score,
        )

    def stream_query(
        self,
        user_query: str,
        employee_id: str = "EMP001",
        target_language: str = "en",
        conversation_id: Optional[str] = None,
    ) -> Iterator[str]:
        """
        Streaming Hybrid RAG query with SQL database facts and LangChain message history.
        """
        conv_id = conversation_id or f"conv-{int(time.time() * 1000)}"
        sql_context = get_employee_full_sql_context(employee_id)

        chunks = vector_store.search(
            query=user_query,
            top_k=settings.rag_top_k,
        )

        retrieved_context = format_chunks(chunks)
        system_prompt = build_system_prompt(
            target_language=target_language,
            sql_context=sql_context,
            retrieved_chunks=retrieved_context,
        )

        history = get_session_history(conv_id)
        langchain_messages: list[BaseMessage] = [SystemMessage(content=system_prompt)]
        prior_messages = history.messages[-6:] if history.messages else []
        langchain_messages.extend(prior_messages)
        langchain_messages.append(HumanMessage(content=user_query))

        messages = []
        for msg in langchain_messages:
            if isinstance(msg, SystemMessage):
                messages.append({"role": "system", "content": str(msg.content)})
            elif isinstance(msg, HumanMessage):
                messages.append({"role": "user", "content": str(msg.content)})
            elif isinstance(msg, AIMessage):
                messages.append({"role": "assistant", "content": str(msg.content)})

        stream_kwargs = {
            "model": settings.llm_model,
            "messages": messages,
            "max_tokens": settings.max_tokens,
            "stream": True,
        }
        if "gemini" not in settings.llm_model.lower():
            stream_kwargs["temperature"] = 0.1

        stream = litellm.completion(**stream_kwargs)

        collected = []
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                collected.append(delta)
                yield delta

        # Record turn in LangChain history after stream completes
        history.add_user_message(user_query)
        history.add_ai_message("".join(collected))


# ── Singleton instance ────────────────────────────────────────────
rag_engine = RAGEngine()
