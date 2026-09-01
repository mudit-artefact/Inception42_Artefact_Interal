"""
How a turn ends: with a verified answer, a greeting, or a safe fallback.

Every path leads through `record_conversation_turn`, so what the conversation remembers
is written in exactly one place rather than the three places it used to be written in.
"""

import logging
import time

from app.domain.employee_facts import EmployeeFacts
from app.domain.enums import AnswerStatus, FallbackReason, QuestionIntent
from app.services.citation_builder import build_employee_record_citation, build_policy_citations
from app.workflow.conversation_memory import remember_turn
from app.workflow.conversation_state import ConversationState
import re
from app.workflow.prompts import (
    ESCALATION_MESSAGES,
    GREETING_BODY,
    GREETING_MESSAGES,
    NO_EVIDENCE_MESSAGES,
    NOTHING_TO_REPHRASE_MESSAGES,
    OUT_OF_SCOPE_MESSAGES,
    message_in_language,
)

logger = logging.getLogger(__name__)

# Match Arabic script greetings or transliterated Islamic greetings (salam, salam e walekum, etc.)
ISLAMIC_GREETING_PATTERN = re.compile(
    r"\b(salam|salaam|salambay|assalam|assalamu|alaykum|alaikum|walekum|walaykum)\b"
    r"|[\u0600-\u06FF]*سلام[\u0600-\u06FF]*|السلام\s+عليكم",
    re.IGNORECASE,
)


def generate_greeting(state: ConversationState) -> dict:
    """Greet the employee by name with appropriate English/Arabic/Islamic response."""
    requested_language = state.get("requested_language", "en")
    facts = state.get("employee_facts") or {}
    question = (state.get("employee_question") or "").strip().lower()

    is_arabic_script = bool(re.search(r"[\u0600-\u06FF]", question))
    is_islamic_greeting = bool(ISLAMIC_GREETING_PATTERN.search(question))

    if is_arabic_script or is_islamic_greeting:
        if is_arabic_script or requested_language == "ar":
            employee_name = facts.get("name_ar") or facts.get("name") or ""
            opening = f"وعليكم السلام {employee_name}! 👋".strip()
            body_lang = "ar"
        else:
            employee_name = facts.get("name") or "there"
            opening = f"Wa 'alaykum as-salam {employee_name}! 👋"
            body_lang = "en"
    else:
        if requested_language == "ar":
            employee_name = facts.get("name_ar") or facts.get("name") or ""
            opening = f"مرحباً {employee_name}! 👋".strip()
            body_lang = "ar"
        else:
            employee_name = facts.get("name") or "there"
            opening = f"Hello {employee_name}! 👋"
            body_lang = "en"

    greeting_body = GREETING_BODY.get(body_lang, GREETING_BODY["en"])
    full_greeting = f"{opening}\n\n{greeting_body}"

    return {
        "final_answer": _clean_and_format_markdown(full_greeting),
        "citations": [],
        "answer_status": AnswerStatus.VERIFIED.value,
    }


def _clean_and_format_markdown(text: str) -> str:
    """Format and normalize markdown to ensure clean lists (numbered & bulleted), spacing, and headings."""
    if not text:
        return ""

    import re
    # 1. Convert inline bullet points (• or ● or ▪) into clean multi-line markdown bullets (* )
    formatted = re.sub(r'([:\.]\s*)[•●▪]\s*', r'\1\n\n* ', text)
    formatted = re.sub(r'(?<!\n)\s*[•●▪]\s*', r'\n* ', formatted)
    formatted = re.sub(r'^[•●▪]\s*', r'* ', formatted, flags=re.MULTILINE)

    # 2. Convert inline numbered lists (e.g. "... reply: 1. Item 2. Item 3. Item") into multi-line numbered lists
    formatted = re.sub(r'([:\.]\s*)(1[\.\)]\s+)', r'\1\n\n\2', formatted)
    formatted = re.sub(r'(?<!\n)\s*(\d+[\.\)]\s+)', r'\n\1', formatted)

    # 3. Ensure a blank line before any list block starting right after paragraph text
    formatted = re.sub(r'([^\n])\n(\d+[\.\)]\s+|\*\s+|-\s+)', r'\1\n\n\2', formatted)

    # 4. Ensure headings (### Heading) have clean line breaks before and after
    formatted = re.sub(r'([^\n])\n(#{1,4}\s+)', r'\1\n\n\2', formatted)

    # 5. Normalize excess blank lines (3+ consecutive newlines -> 2 newlines)
    formatted = re.sub(r'\n{3,}', r'\n\n', formatted)
    return formatted.strip()


def finalize_verified_answer(state: ConversationState) -> dict:
    """
    The answer passed every check, so it is shown with its sources.

    A turn where some part of the question found nothing is marked partial rather than
    verified. The answer still goes out — the parts that were served are worth having —
    but the record of the turn says plainly that not all of it was.
    """
    statuses = state.get("subquery_statuses") or []
    unanswered = [status["question"] for status in statuses if not status["has_evidence"]]

    if unanswered:
        logger.info(
            f"Answered {len(statuses) - len(unanswered)} of {len(statuses)} parts; "
            f"nothing was found for: {unanswered}"
        )

    clean_answer = _clean_and_format_markdown(state.get("draft_answer", ""))

    return {
        "final_answer": clean_answer,
        "citations": _citations_for(state),
        "answer_status": (
            AnswerStatus.PARTIAL if unanswered else AnswerStatus.VERIFIED
        ).value,
    }


def build_safe_fallback(state: ConversationState) -> dict:
    """
    Decline gracefully rather than guess.

    The citations found along the way are still attached whenever there were any, so an
    over-cautious check leaves the employee with the policy extracts to read rather than
    with nothing at all.
    """
    requested_language = state.get("requested_language", "en")
    reason = state.get("fallback_reason") or _infer_fallback_reason(state)

    if reason == FallbackReason.OUT_OF_SCOPE.value:
        message = message_in_language(OUT_OF_SCOPE_MESSAGES, requested_language)
        citations: list[dict] = []
        status = AnswerStatus.REFUSED.value
    elif reason == FallbackReason.NOTHING_TO_REPHRASE.value:
        message = message_in_language(NOTHING_TO_REPHRASE_MESSAGES, requested_language)
        citations = []
        status = AnswerStatus.SAFE_FALLBACK.value
    elif reason == FallbackReason.NEEDS_HUMAN.value:
        facts = state.get("employee_facts") or {}
        message = message_in_language(ESCALATION_MESSAGES, requested_language).format(
            manager_name=facts.get("manager_name", "your line manager")
        )
        citations = _citations_for(state)
        status = AnswerStatus.SAFE_FALLBACK.value
    else:
        message = message_in_language(NO_EVIDENCE_MESSAGES, requested_language)
        citations = _citations_for(state)
        status = AnswerStatus.SAFE_FALLBACK.value

    logger.info(
        f"Falling back safely: {reason} ({state.get('validation_reason', '')}) "
        f"— parts: {state.get('subquery_statuses') or 'not routed'}"
    )

    return {
        "final_answer": message,
        "citations": citations,
        "answer_status": status,
        "fallback_reason": reason,
    }


def record_conversation_turn(state: ConversationState) -> dict:
    """
    Save the turn and work out how long it took.

    The gathered evidence is cleared before the turn is saved. Keeping every retrieved
    passage in the saved state would grow it with each turn and slow every resume down,
    for text that has already served its purpose.
    """
    final_answer = state.get("final_answer", "")

    started_at = state.get("started_at_seconds") or time.time()

    finished_turn = {
        "latency_milliseconds": int((time.time() - started_at) * 1000),
        "evidence_summary": "",
        "policy_passages": [],
        "draft_answer": "",
        # None, not an empty list: this field is gathered from the parallel branches by
        # appending, so an empty list would add nothing and leave this turn's findings in
        # place for the next question in the conversation to be answered from.
        "subquery_evidence": None,
    }

    if _is_worth_remembering(state, final_answer):
        # The question as it finally stood, so a turn that was clarified is remembered
        # with the employee's reply folded in — that reply is usually the very detail a
        # later follow-up refers back to.
        finished_turn["remembered_turns"] = remember_turn(
            state.get("remembered_turns"), state["employee_question"], final_answer
        )
        # And the reply itself, kept whole. The remembered copy above is clipped short
        # and flattened onto one line, which is all that resolving a follow-up needs and
        # nothing like enough to rework a reply from: you cannot shorten what you can
        # only see the first 300 characters of.
        finished_turn["previous_reply"] = {
            "text": final_answer,
            "citations": state.get("citations") or [],
            "language": state.get("requested_language", "en"),
        }

    return finished_turn


def _is_worth_remembering(state: ConversationState, final_answer: str) -> bool:
    """
    Whether this turn is worth carrying into the next question.

    A refusal is: "can you sort out my payroll?" followed by "what about expenses?" only
    makes sense if the first one is remembered. A greeting is not — it refers to nothing,
    and its fixed reply is a menu of the topics this assistant covers, which would sit in
    the next question's prompt reading like a list of things to talk about.
    """
    if not final_answer:
        return False
    # The pause never reaches this step; the graph stops inside the waiting step and
    # clears this flag on the way back out. Kept for a path that one day routes here.
    if state.get("is_awaiting_clarification"):
        return False
    return state.get("question_intent") != QuestionIntent.GREETING


def _citations_for(state: ConversationState) -> list[dict]:
    """
    The employee's own record first, then each policy extract that was used.

    When nothing was retrieved this turn, whatever the state already carries is kept.
    That is the reworked-reply path: it searches for nothing, and brings forward the
    sources of the reply it reworked. Rebuilding from an empty search would strip them,
    and the employee would be shown a reply with no sources where a moment ago the same
    content had several.
    """
    citations = []

    hr_data = state.get("hr_data_facts") or {}
    if hr_data.get("fields"):
        facts = EmployeeFacts.from_dictionary(state["employee_facts"])
        citations.append(
            build_employee_record_citation(
                facts, language=state.get("requested_language", "en")
            ).model_dump()
        )

    citations.extend(
        citation.model_dump()
        for citation in build_policy_citations(state.get("policy_passages") or [])
    )
    return citations or list(state.get("citations") or [])


def _infer_fallback_reason(state: ConversationState) -> str:
    """Work out why we are falling back, when nothing set it explicitly."""
    if state.get("question_intent") == "out_of_scope":
        return FallbackReason.OUT_OF_SCOPE.value
    if state.get("question_intent") == QuestionIntent.ABOUT_THE_LAST_ANSWER:
        return FallbackReason.NOTHING_TO_REPHRASE.value
    if state.get("required_evidence") == "unsupported":
        return FallbackReason.NEEDS_HUMAN.value
    if state.get("unsupported_claims"):
        return FallbackReason.UNSUPPORTED_CLAIMS.value
    return FallbackReason.NO_EVIDENCE.value
