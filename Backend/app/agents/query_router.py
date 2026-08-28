"""
app/agents/query_router.py — LangGraph Query Router for HCS-01

Routes user queries into 4 categories:
  1. greeting       → Greet user by name, end flow
  2. not_in_scope   → Return refusal message, end flow
  3. ambiguous      → Store question, ask clarification, wait for user
  4. in_scope       → Rewrite query if needed, continue to RAG

Flow:
  START → classifier_node → [greeting|not_in_scope|ambiguous|in_scope]

  - greeting       → greeting_node → END
  - not_in_scope   → not_in_scope_node → END
  - ambiguous      → ambiguous_node → WAIT → merge_node → in_scope_node → output_node → END
  - in_scope       → in_scope_node → output_node → END
"""

import logging
from typing import Literal, Annotated
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

import litellm
from app.config import settings

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# STATE SCHEMA
# ══════════════════════════════════════════════════════════════════════════════

class QueryRouterState(TypedDict):
    """State for the Query Router graph."""

    # Input
    user_query: str
    employee_id: str
    employee_name: str
    employee_name_ar: str
    target_language: str  # "en" | "ar"
    conversation_id: str
    conversation_history: list  # Recent conversation turns for context

    # Classification result
    intent: str  # "greeting" | "not_in_scope" | "ambiguous" | "in_scope"
    confidence: float

    # Ambiguous handling
    original_question: str | None
    clarifying_question: str | None
    user_clarification: str | None
    is_awaiting_clarification: bool

    # Output
    rewritten_query: str | None
    response: str | None
    is_terminal: bool  # True = end flow, False = continue to RAG


# ══════════════════════════════════════════════════════════════════════════════
# LLM STRUCTURED OUTPUTS
# ══════════════════════════════════════════════════════════════════════════════

class ClassifierOutput(BaseModel):
    """Structured output from the classifier LLM."""
    intent: Literal["greeting", "not_in_scope", "ambiguous", "in_scope"] = Field(
        description="The classified intent of the user query"
    )
    confidence: float = Field(
        description="Confidence score between 0.0 and 1.0",
        ge=0.0,
        le=1.0
    )
    reasoning: str = Field(
        description="Brief explanation for the classification"
    )


class ClarifyingQuestionOutput(BaseModel):
    """Structured output for generating clarifying questions."""
    clarifying_question: str = Field(
        description="The question to ask the user for clarification"
    )
    missing_info: str = Field(
        description="What information is missing from the original query"
    )


class RewrittenQueryOutput(BaseModel):
    """Structured output for query rewriting."""
    rewritten_query: str = Field(
        description="The rewritten, improved query for RAG retrieval"
    )
    needs_rewrite: bool = Field(
        description="Whether the query actually needed rewriting"
    )


# ══════════════════════════════════════════════════════════════════════════════
# CLASSIFIER NODE
# ══════════════════════════════════════════════════════════════════════════════

CLASSIFIER_SYSTEM_PROMPT = """\
You are an intent classifier for an HR Policy & Leave Concierge system at HC Services (UAE).

Classify the user's query into ONE of these 4 categories:

1. **greeting** — Pure greetings with no actionable question
   Examples: "Hi", "Hello", "Good morning", "مرحبا", "السلام عليكم"

2. **not_in_scope** — Questions outside HR/workplace policies
   Examples: "What's the capital of UAE?", "How to cook biryani?", "Tell me a joke"

3. **ambiguous** — HR-related but missing critical details to answer AND no conversation context
   Examples (as first message):
   - "How many leaves can I take?" (which type? annual/sick?)
   - "What's the approval process?" (for what? leave/expense?)
   - "Can I work remotely?" (for how long? which days?)

4. **in_scope** — Clear HR/workplace question that can be answered
   Examples:
   - "Who is my manager?"
   - "How many annual leave days do I have?"
   - "What is the sick leave policy?"
   - "How do I submit an expense claim?"

HR Topics in scope: Leave policies, sick leave, annual leave, carry-over, probation,
remote work, flexible work, expense claims, manager reporting, employee benefits,
work from home, notice periods, medical certificates.

IMPORTANT FOR FOLLOW-UP QUESTIONS:
- If conversation history is provided, consider the context when classifying.
- Follow-up questions like "how to apply for it?", "what's the process?", "tell me more"
  should be classified as **in_scope** if the previous context makes the topic clear.
- Pronouns like "it", "this", "that" referring to HR topics from conversation history
  should be treated as in_scope, NOT ambiguous.
- Only classify as ambiguous if there's truly no way to understand what the user is asking about.

Be strict: If the query is clearly about something other than HR/workplace policies,
classify as not_in_scope. If it's HR-related but vague WITH NO CONTEXT, classify as ambiguous.
"""


def classifier_node(state: QueryRouterState) -> dict:
    """Classify the user query into one of 4 intents using LLM."""

    user_query = state["user_query"]
    target_lang = state.get("target_language", "en")
    conversation_history = state.get("conversation_history", [])

    # Build context from conversation history
    context_str = ""
    if conversation_history:
        recent_turns = conversation_history[-4:]  # Last 4 messages (2 turns)
        context_lines = []
        for turn in recent_turns:
            role = turn.get("role", "user")
            content = turn.get("content", "")[:200]  # Truncate long messages
            context_lines.append(f"{role.upper()}: {content}")
        context_str = "\n".join(context_lines)

    # Build the classification prompt
    if context_str:
        user_prompt = f"""Conversation context:
{context_str}

Current query to classify: "{user_query}"

Consider the conversation context when classifying. If the current query is a follow-up
to the previous discussion (e.g., "how to apply for it?", "what's the process?"),
classify it as in_scope, not ambiguous."""
    else:
        user_prompt = f"Classify this query: \"{user_query}\""

    messages = [
        {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]

    try:
        response = litellm.completion(
            model=settings.llm_model,
            messages=messages,
            response_format=ClassifierOutput,
        )

        result = ClassifierOutput.model_validate_json(
            response.choices[0].message.content
        )

        logger.info(f"Classifier: '{user_query[:50]}...' → {result.intent} ({result.confidence:.2f})")

        return {
            "intent": result.intent,
            "confidence": result.confidence,
        }

    except Exception as e:
        logger.error(f"Classifier error: {e}")
        # Fallback to in_scope on error (let RAG handle it)
        return {
            "intent": "in_scope",
            "confidence": 0.5,
        }


# ══════════════════════════════════════════════════════════════════════════════
# GREETING NODE
# ══════════════════════════════════════════════════════════════════════════════

def greeting_node(state: QueryRouterState) -> dict:
    """Handle greeting queries — return personalized greeting."""

    target_lang = state.get("target_language", "en")
    name = state.get("employee_name_ar") if target_lang == "ar" else state.get("employee_name")
    name = name or "there"

    if target_lang == "ar":
        response = (
            f"مرحباً {name}! 👋\n\n"
            f"أنا مساعد سياسات الموارد البشرية في إتش سي سيرفيسز. "
            f"كيف يمكنني مساعدتك اليوم؟ يمكنني الإجابة على أسئلتك حول:\n"
            f"• الإجازات السنوية والمرضية\n"
            f"• سياسات العمل عن بُعد\n"
            f"• استرداد المصروفات\n"
            f"• فترة التجربة والتقييم"
        )
    else:
        response = (
            f"Hello {name}! 👋\n\n"
            f"I'm your HC Services Policy & Leave Concierge. "
            f"How can I assist you today? I can help with:\n"
            f"• Annual and sick leave policies\n"
            f"• Remote work guidelines\n"
            f"• Expense claims and reimbursements\n"
            f"• Probation and performance reviews"
        )

    logger.info(f"Greeting node: Responded to {state.get('employee_id')}")

    return {
        "response": response,
        "is_terminal": True,
        "is_awaiting_clarification": False,
    }


# ══════════════════════════════════════════════════════════════════════════════
# NOT IN SCOPE NODE
# ══════════════════════════════════════════════════════════════════════════════

def not_in_scope_node(state: QueryRouterState) -> dict:
    """Handle out-of-scope queries — return polite refusal."""

    target_lang = state.get("target_language", "en")

    if target_lang == "ar":
        response = (
            "عذراً، أنا مخصص حصرياً للمساعدة في سياسات الموارد البشرية "
            "ولوائح الإجازات وبدلات العمل الخاصة بشركة إتش سي سيرفيسز. "
            "لا يمكنني الإجابة على موضوعات خارج نطاق سياسات الشركة.\n\n"
            "كيف يمكنني مساعدتك في استفساراتك الوظيفية؟"
        )
    else:
        response = (
            "I am dedicated strictly to assisting with HC Services internal HR policies, "
            "leave balances, manager reporting, and employee benefits. "
            "I cannot assist with questions outside our company HR policies.\n\n"
            "How can I help with your workplace questions today?"
        )

    logger.info(f"Not in scope: Query '{state['user_query'][:30]}...' refused")

    return {
        "response": response,
        "is_terminal": True,
        "is_awaiting_clarification": False,
    }


# ══════════════════════════════════════════════════════════════════════════════
# AMBIGUOUS NODE
# ══════════════════════════════════════════════════════════════════════════════

CLARIFY_SYSTEM_PROMPT = """\
You are an HR assistant that needs to ask a clarifying question.

The user asked an HR-related question but it's missing critical details needed to provide
an accurate answer. Generate a helpful, concise clarifying question.

Keep the question short and specific. Offer options when applicable.

Examples:
- "How many leaves can I take?" → "Could you specify which type of leave? (Annual, Sick, or Carry-over)"
- "What's the approval process?" → "What would you like to know the approval process for? (Leave requests, Expense claims, or Remote work)"
- "Can I work from home?" → "Are you asking about the regular hybrid work policy (2 days/week) or the Work From Anywhere program (international)?"
"""


def ambiguous_node(state: QueryRouterState) -> dict:
    """Handle ambiguous queries — store question and ask for clarification."""

    user_query = state["user_query"]
    target_lang = state.get("target_language", "en")

    messages = [
        {"role": "system", "content": CLARIFY_SYSTEM_PROMPT},
        {"role": "user", "content": f"Generate a clarifying question for: \"{user_query}\"\n\nRespond in: {'Arabic' if target_lang == 'ar' else 'English'}"}
    ]

    try:
        response = litellm.completion(
            model=settings.llm_model,
            messages=messages,
            response_format=ClarifyingQuestionOutput,
        )

        result = ClarifyingQuestionOutput.model_validate_json(
            response.choices[0].message.content
        )

        clarifying_q = result.clarifying_question

    except Exception as e:
        logger.error(f"Clarify generation error: {e}")
        # Fallback clarifying question
        if target_lang == "ar":
            clarifying_q = "هل يمكنك توضيح سؤالك بمزيد من التفاصيل؟"
        else:
            clarifying_q = "Could you please provide more details about your question?"

    logger.info(f"Ambiguous node: Asking for clarification on '{user_query[:30]}...'")

    return {
        "original_question": user_query,
        "clarifying_question": clarifying_q,
        "response": clarifying_q,
        "is_terminal": True,  # End this turn, wait for user
        "is_awaiting_clarification": True,
    }


# ══════════════════════════════════════════════════════════════════════════════
# MERGE NODE (combines original question + user clarification)
# ══════════════════════════════════════════════════════════════════════════════

def merge_node(state: QueryRouterState) -> dict:
    """Merge original question with user's clarification."""

    original = state.get("original_question", "")
    clarification = state.get("user_clarification", "")

    # Combine into a single coherent query
    merged_query = f"{original} — Clarification: {clarification}"

    logger.info(f"Merge node: Combined query → '{merged_query[:50]}...'")

    return {
        "user_query": merged_query,
        "is_awaiting_clarification": False,
    }


# ══════════════════════════════════════════════════════════════════════════════
# IN SCOPE NODE (rewrite query if needed)
# ══════════════════════════════════════════════════════════════════════════════

REWRITE_SYSTEM_PROMPT = """\
You are a query rewriter for an HR Policy RAG system.

Your job is to rewrite user queries to be more effective for semantic search retrieval.

Guidelines:
1. Expand abbreviations: AL → Annual Leave, SL → Sick Leave, WFH → Work From Home
2. Add context for vague terms: "balance" → "leave balance", "policy" → "HR policy"
3. Make implicit questions explicit: "manager?" → "Who is my current line manager?"
4. Keep the query concise but complete
5. Preserve the original intent

If the query is already clear and specific, return it unchanged with needs_rewrite=false.

Examples:
- "AL balance" → "What is my annual leave balance and remaining days?"
- "who manager" → "Who is my current line manager and their contact details?"
- "sick leave rules" → "What are the sick leave policy rules and medical certificate requirements?"
- "How many annual leave days do I have?" → No rewrite needed (already clear)
"""


def in_scope_node(state: QueryRouterState) -> dict:
    """Handle in-scope queries — rewrite if needed for better retrieval."""

    user_query = state["user_query"]
    target_lang = state.get("target_language", "en")

    messages = [
        {"role": "system", "content": REWRITE_SYSTEM_PROMPT},
        {"role": "user", "content": f"Rewrite this query for RAG retrieval: \"{user_query}\"\n\nKeep response in: {'Arabic' if target_lang == 'ar' else 'English'}"}
    ]

    try:
        response = litellm.completion(
            model=settings.llm_model,
            messages=messages,
            response_format=RewrittenQueryOutput,
        )

        result = RewrittenQueryOutput.model_validate_json(
            response.choices[0].message.content
        )

        rewritten = result.rewritten_query if result.needs_rewrite else user_query

        logger.info(f"In-scope node: '{user_query[:30]}...' → '{rewritten[:30]}...' (rewritten={result.needs_rewrite})")

    except Exception as e:
        logger.error(f"Rewrite error: {e}")
        rewritten = user_query  # Fallback to original

    return {
        "rewritten_query": rewritten,
        "is_terminal": False,  # Continue to RAG
        "is_awaiting_clarification": False,
    }


# ══════════════════════════════════════════════════════════════════════════════
# OUTPUT NODE
# ══════════════════════════════════════════════════════════════════════════════

def output_node(state: QueryRouterState) -> dict:
    """Final output node — prepares state for RAG pipeline."""

    logger.info(f"Output node: Ready for RAG with query '{state.get('rewritten_query', '')[:50]}...'")

    return {
        "is_terminal": False,
    }


# ══════════════════════════════════════════════════════════════════════════════
# ROUTING LOGIC
# ══════════════════════════════════════════════════════════════════════════════

def route_by_intent(state: QueryRouterState) -> str:
    """Route to appropriate node based on classified intent."""

    intent = state.get("intent", "in_scope")

    if intent == "greeting":
        return "greeting_node"
    elif intent == "not_in_scope":
        return "not_in_scope_node"
    elif intent == "ambiguous":
        return "ambiguous_node"
    else:  # in_scope
        return "in_scope_node"


def check_awaiting_clarification(state: QueryRouterState) -> str:
    """Check if we're processing a clarification response."""

    if state.get("is_awaiting_clarification") and state.get("user_clarification"):
        return "merge_node"
    else:
        return "classifier_node"


# ══════════════════════════════════════════════════════════════════════════════
# BUILD THE GRAPH
# ══════════════════════════════════════════════════════════════════════════════

def build_query_router_graph() -> StateGraph:
    """Build and compile the Query Router LangGraph."""

    # Create the graph
    graph = StateGraph(QueryRouterState)

    # Add nodes
    graph.add_node("classifier_node", classifier_node)
    graph.add_node("greeting_node", greeting_node)
    graph.add_node("not_in_scope_node", not_in_scope_node)
    graph.add_node("ambiguous_node", ambiguous_node)
    graph.add_node("merge_node", merge_node)
    graph.add_node("in_scope_node", in_scope_node)
    graph.add_node("output_node", output_node)

    # Entry point: Check if this is a clarification follow-up or new query
    graph.add_conditional_edges(
        START,
        check_awaiting_clarification,
        {
            "classifier_node": "classifier_node",
            "merge_node": "merge_node",
        }
    )

    # Classifier routes to one of 4 intent nodes
    graph.add_conditional_edges(
        "classifier_node",
        route_by_intent,
        {
            "greeting_node": "greeting_node",
            "not_in_scope_node": "not_in_scope_node",
            "ambiguous_node": "ambiguous_node",
            "in_scope_node": "in_scope_node",
        }
    )

    # Terminal nodes → END
    graph.add_edge("greeting_node", END)
    graph.add_edge("not_in_scope_node", END)
    graph.add_edge("ambiguous_node", END)  # Waits for user clarification

    # Merge → In-scope → Output → END
    graph.add_edge("merge_node", "in_scope_node")
    graph.add_edge("in_scope_node", "output_node")
    graph.add_edge("output_node", END)

    return graph.compile()


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON GRAPH INSTANCE
# ══════════════════════════════════════════════════════════════════════════════

query_router_graph = build_query_router_graph()


# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTION FOR EASY INVOCATION
# ══════════════════════════════════════════════════════════════════════════════

def route_query(
    user_query: str,
    employee_id: str = "EMP001",
    employee_name: str = "Employee",
    employee_name_ar: str = "موظف",
    target_language: str = "en",
    conversation_id: str = "",
    # For clarification follow-up
    original_question: str | None = None,
    user_clarification: str | None = None,
    # Conversation history for context
    conversation_history: list | None = None,
) -> QueryRouterState:
    """
    Route a user query through the Query Router graph.

    Args:
        user_query: The user's question
        employee_id: Employee ID (e.g., "EMP001")
        employee_name: Employee name in English
        employee_name_ar: Employee name in Arabic
        target_language: "en" or "ar"
        conversation_id: Conversation session ID
        original_question: (For clarification) The original ambiguous question
        user_clarification: (For clarification) The user's clarifying response
        conversation_history: List of recent messages for context

    Returns:
        QueryRouterState with:
        - response: The response text (for terminal flows)
        - rewritten_query: The rewritten query (for in_scope, ready for RAG)
        - is_terminal: True if flow ends here, False if should continue to RAG
        - is_awaiting_clarification: True if waiting for user clarification
    """

    initial_state: QueryRouterState = {
        "user_query": user_query,
        "employee_id": employee_id,
        "employee_name": employee_name,
        "employee_name_ar": employee_name_ar,
        "target_language": target_language,
        "conversation_id": conversation_id or f"conv-{employee_id}",
        "conversation_history": conversation_history or [],
        "intent": "",
        "confidence": 0.0,
        "original_question": original_question,
        "clarifying_question": None,
        "user_clarification": user_clarification,
        "is_awaiting_clarification": bool(original_question and user_clarification),
        "rewritten_query": None,
        "response": None,
        "is_terminal": False,
    }

    # Run the graph
    result = query_router_graph.invoke(initial_state)

    return result


# ══════════════════════════════════════════════════════════════════════════════
# CLI TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(__file__).replace("app/agents/query_router.py", ""))

    from dotenv import load_dotenv
    load_dotenv()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")

    test_queries = [
        "Hi",
        "Good Morning",
        "What's the capital of UAE?",
        "How many leaves can I take?",
        "Who is my manager?",
        "How many AL days do I have left?",
    ]

    print("\n" + "=" * 70)
    print("QUERY ROUTER TEST")
    print("=" * 70)

    for query in test_queries:
        print(f"\n{'─' * 70}")
        print(f"Query: \"{query}\"")
        print(f"{'─' * 70}")

        result = route_query(
            user_query=query,
            employee_id="EMP001",
            employee_name="Ahmed Al Mansoori",
            employee_name_ar="أحمد المنصوري",
            target_language="en",
        )

        print(f"Intent: {result['intent']} (confidence: {result['confidence']:.2f})")
        print(f"Is Terminal: {result['is_terminal']}")
        print(f"Awaiting Clarification: {result['is_awaiting_clarification']}")

        if result.get("response"):
            print(f"Response:\n{result['response'][:200]}...")

        if result.get("rewritten_query"):
            print(f"Rewritten Query: {result['rewritten_query']}")

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)
