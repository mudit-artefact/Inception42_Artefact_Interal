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
from app.workflow.routing_rules import LEAVE_INTENTS, ONBOARDING
from app.workflow.prompts import (
    WHAT_I_CAN_DO,
    ACKNOWLEDGMENT_MESSAGES,
    CONVERSATION_RECAP_MESSAGES,
    ESCALATION_MESSAGES,
    GRATITUDE_MESSAGES,
    GREETING_BODY,
    GREETING_MESSAGES,
    NO_EVIDENCE_MESSAGES,
    NOTHING_TO_REPHRASE_MESSAGES,
    NOT_STARTED_YET_MESSAGES,
    OUT_OF_SCOPE_MESSAGES,
    PLEASANTRY_MESSAGES,
    REPEAT_GREETING_MESSAGES,
    DOCUMENT_UPLOAD_RESPONSE,
    DOCUMENT_UPLOAD_RESPONSE_WITH_FILES,
    message_in_language,
)

logger = logging.getLogger(__name__)


def generate_document_upload_prompt(state: ConversationState) -> dict:
    """
    Open the upload window.

    This step used to do two jobs. Alongside the button it carried a second reply for
    employees asking where their claim had got to, matched by a list of thirty spellings
    of that question — "submitted successfully", "are they approved", "when will". An
    employee who wrote "successfuly" with one l matched none of them and got the button.
    One who spelled it correctly got a fixed paragraph that told them to click the button
    anyway, and promised a review in "2-3 business days" — a figure typed into this file,
    grounded in nothing.

    Neither is this step's job. Asking where a claim stands is a question about the
    employee's own record, and is answered like every other one: the claim is read from
    the school verification service, cited, and checked. This step now only does the one
    thing the button is for.
    """
    question = (state.get("employee_question") or "").lower()

    has_files_attached = any(
        indicator in question
        for indicator in ["[file", "[document", "[attached", "[uploaded", "attached file"]
    )
    response = DOCUMENT_UPLOAD_RESPONSE_WITH_FILES if has_files_attached else DOCUMENT_UPLOAD_RESPONSE

    return {
        "final_answer": response,
        "citations": [],
        "answer_status": AnswerStatus.VERIFIED.value,
    }


# Match Arabic script greetings or transliterated Islamic greetings (salam, salam e walekum, etc.)
ISLAMIC_GREETING_PATTERN = re.compile(
    r"\b(salam|salaam|salambay|assalam|assalamu|alaykum|alaikum|walekum|walaykum)\b"
    r"|[\u0600-\u06FF]*سلام[\u0600-\u06FF]*|السلام\s+عليكم",
    re.IGNORECASE,
)

ACKNOWLEDGMENT_PATTERN = re.compile(
    r"^(ok|okay|k|noted|got it|all right|alright|understood|sounds good|sure|fine|great|perfect|done|تمام|حسنا|حسناً|ماشي|اوكي|أوكي|طيب|تسلم)[\.\!\s]*$",
    re.IGNORECASE,
)

PLEASANTRY_PATTERN = re.compile(
    r"\b(how are you|how're you|how r u|how are you doing|how is it going|how's it going|how do you do|how have you been|how are things|كيف حالك|شخبارك|كيفك|شلونك|عساك بخير)\b",
    re.IGNORECASE,
)

GRATITUDE_PATTERN = re.compile(
    r"^(thank you|thanks|thank u|thx|much appreciated|many thanks|thanks a lot|شكرا|شكراً|مشكور|تسلم|يعطيك العافية|جزاك الله خير)[\.\!\s]*$",
    re.IGNORECASE,
)


def _recap_of_the_conversation(remembered_turns: list[dict] | None, lang: str) -> str:
    """
    The employee's own questions, oldest first and numbered.

    One reply serves every way of asking: the first thing they asked is number 1, what
    they have covered is the list, and what they asked about a particular subject is in
    front of them. Nothing here is generated — each line is a question they typed, already
    shortened and made safe when it was remembered — so there is no figure to ground and
    nothing to invent.
    """
    copy = message_in_language(CONVERSATION_RECAP_MESSAGES, lang)
    asked = [
        (turn.get("question") or "").strip()
        for turn in (remembered_turns or [])
        if (turn.get("question") or "").strip()
    ]
    if not asked:
        return copy["nothing_yet"]

    numbered = [f"{position}. \u201c{question}\u201d"
                for position, question in enumerate(asked, start=1)]
    return "\n".join([copy["heading"], "", *numbered, "", copy["footer"]])


def generate_greeting(state: ConversationState) -> dict:
    """Greet the employee by name or respond naturally to pleasantries, gratitude, and acknowledgments."""
    requested_language = state.get("requested_language", "en")
    facts = state.get("employee_facts") or {}
    question = (state.get("employee_question") or "").strip().lower()

    is_arabic_script = bool(re.search(r"[\u0600-\u06FF]", question))
    lang = "ar" if (is_arabic_script or requested_language == "ar") else "en"
    employee_name = (facts.get("name_ar") if lang == "ar" else facts.get("name")) or (facts.get("name") or "there")

    # 0a. A question about this conversation. Everything it needs is already in the
    # state — nothing is retrieved, nothing is worked out, and nothing is written that
    # the employee did not type themselves.
    if state.get("question_intent") == QuestionIntent.ABOUT_THIS_CONVERSATION.value:
        return {
            "final_answer": _clean_and_format_markdown(
                _recap_of_the_conversation(state.get("remembered_turns"), lang)
            ),
            "citations": [],
            "answer_status": AnswerStatus.VERIFIED.value,
        }

    # 0b. A question about the assistant itself, rather than about HR.
    if state.get("question_intent") == QuestionIntent.WHAT_CAN_YOU_DO.value:
        return {
            "final_answer": _clean_and_format_markdown(message_in_language(WHAT_I_CAN_DO, lang)),
            "citations": [],
            "answer_status": AnswerStatus.VERIFIED.value,
        }

    # 1. Acknowledgment (e.g. "ok", "got it", "noted")
    if ACKNOWLEDGMENT_PATTERN.match(question):
        answer = message_in_language(ACKNOWLEDGMENT_MESSAGES, lang)
        return {
            "final_answer": _clean_and_format_markdown(answer),
            "citations": [],
            "answer_status": AnswerStatus.VERIFIED.value,
        }

    # 2. Gratitude (e.g. "thank you", "thanks", "شكراً")
    if GRATITUDE_PATTERN.match(question):
        answer = message_in_language(GRATITUDE_MESSAGES, lang)
        return {
            "final_answer": _clean_and_format_markdown(answer),
            "citations": [],
            "answer_status": AnswerStatus.VERIFIED.value,
        }

    # 3. Conversational pleasantry (e.g. "how are you?", "كيف حالك")
    if PLEASANTRY_PATTERN.search(question):
        answer = message_in_language(PLEASANTRY_MESSAGES, lang)
        return {
            "final_answer": _clean_and_format_markdown(answer),
            "citations": [],
            "answer_status": AnswerStatus.VERIFIED.value,
        }

    # 4. Mid-conversation repeat greeting (if conversation already has remembered turns)
    remembered = state.get("remembered_turns") or []
    if remembered:
        answer_tmpl = message_in_language(REPEAT_GREETING_MESSAGES, lang)
        answer = answer_tmpl.format(employee_name=employee_name)
        return {
            "final_answer": _clean_and_format_markdown(answer),
            "citations": [],
            "answer_status": AnswerStatus.VERIFIED.value,
        }

    # 5. First-turn standard welcome greeting
    is_islamic_greeting = bool(ISLAMIC_GREETING_PATTERN.search(question))
    if is_islamic_greeting:
        if lang == "ar":
            full_greeting = f"وعليكم السلام {employee_name}! أنا دليل. كيف يمكنني مساعدتك اليوم؟"
        else:
            full_greeting = f"Wa 'alaykum as-salam {employee_name}! Hi, I am Dalil. How can I help you today?"
    else:
        if lang == "ar":
            full_greeting = f"مرحباً {employee_name}! أنا دليل. كيف يمكنني مساعدتك اليوم؟"
        else:
            full_greeting = f"Hello {employee_name}! Hi, I am Dalil. How can I help you today?"

    return {
        "final_answer": _clean_and_format_markdown(full_greeting),
        "citations": [],
        "answer_status": AnswerStatus.VERIFIED.value,
    }


def _clean_and_format_markdown(text: str) -> str:
    """Format and normalize markdown to ensure clean lists, spacing, and headings."""
    if not text:
        return ""

    import re
    # 1. Reconnect broken headings or dangling parentheses like "Annual Leave (\n2026." -> "### Annual Leave (2026)"
    formatted = re.sub(
        r'(#{1,4}\s+[^\n(]+|\*\*[^\n*()]+\*\*|[A-Za-z\s]+)\(\s*\n+(\d{4})\.?\)?',
        r'\1 (\2)',
        text,
    )
    formatted = re.sub(r'\(\s*\n+(\d{2,4})\.?\)?', r'(\1)', formatted)
    formatted = re.sub(r'^(\d{4})\.\s*$', r'**Year \1**', formatted, flags=re.MULTILINE)

    # 2. Convert inline bullet points (• or ● or ▪) into clean multi-line markdown bullets (* )
    formatted = re.sub(r'^[•●▪]\s*', r'* ', formatted, flags=re.MULTILINE)
    formatted = re.sub(r'([:\.]\s*)[•●▪]\s*', r'\1\n\n* ', formatted)
    formatted = re.sub(r'(?<=[^\n])\s+[•●▪]\s*', r'\n* ', formatted)

    # 3. Ensure a blank line before any markdown list block starting right after paragraph text
    formatted = re.sub(r'([^\n])\n(\*\s+|-\s+)', r'\1\n\n\2', formatted)

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

    # An action branch has already said what became of the request, and "verified" is not
    # that. Whether the answer is true to its evidence is what the check just settled;
    # whether the leave was booked is a different fact and the only one that can report it
    # is the step that did it.
    already_reported = state.get("answer_status")
    reports_an_action = already_reported in {
        AnswerStatus.ACTION_EXECUTED.value,
        AnswerStatus.ACTION_REJECTED.value,
    }

    result = {
        "final_answer": clean_answer,
        "citations": _citations_for(state),
        "answer_status": (
            already_reported
            if reports_an_action
            else (AnswerStatus.PARTIAL if unanswered else AnswerStatus.VERIFIED).value
        ),
    }

    # Include chart visualization if one was generated
    chart_data = state.get("chart_data")
    if chart_data:
        result["chart_data"] = chart_data

    return result


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
    elif reason == FallbackReason.NOT_STARTED_YET.value:
        message = message_in_language(NOT_STARTED_YET_MESSAGES, requested_language)
        citations = []
        status = AnswerStatus.REFUSED.value
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
        # The card goes with the answer it belonged to. Now that action branches are
        # checked like everything else, one of them can end up here — and "I could not
        # find that" under a leave confirmation card the employee is invited to approve
        # is worse than either half on its own.
        "action_payload": None,
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

    When nothing was retrieved this turn, whatever the state already carries is kept only
    for the reworked-reply path (ABOUT_THE_LAST_ANSWER).
    Action-based queries (leave requests, approvals, school document verifications, uploads)
    do not show citations.
    """
    intent = state.get("question_intent")
    action_intents = {
        QuestionIntent.APPLY_LEAVE,
        QuestionIntent.CANCEL_LEAVE,
        QuestionIntent.CHECK_LEAVE_STATUS,
        QuestionIntent.APPROVE_LEAVE,
        QuestionIntent.REJECT_LEAVE,
        QuestionIntent.CHECK_SCHOOL_VERIFICATION,
        QuestionIntent.SUBMIT_SCHOOL_VERIFICATION,
        QuestionIntent.REVIEW_SCHOOL_CASES,
        QuestionIntent.DOCUMENT_UPLOAD,
        QuestionIntent.GREETING,
        QuestionIntent.OUT_OF_SCOPE,
    }
    if intent in action_intents or state.get("action_payload"):
        return []

    policy_citations = [
        citation.model_dump()
        for citation in build_policy_citations(state.get("policy_passages") or [])
    ]

    if not policy_citations and intent == QuestionIntent.ABOUT_THE_LAST_ANSWER:
        return list(state.get("citations") or [])

    citations = []
    hr_data = state.get("hr_data_facts") or {}
    if hr_data.get("fields"):
        facts = EmployeeFacts.from_dictionary(state["employee_facts"])
        citations.append(
            build_employee_record_citation(
                facts, language=state.get("requested_language", "en")
            ).model_dump()
        )

    citations.extend(policy_citations)
    return citations


def _infer_fallback_reason(state: ConversationState) -> str:
    """Work out why we are falling back, when nothing set it explicitly."""
    if state.get("question_intent") == "out_of_scope":
        return FallbackReason.OUT_OF_SCOPE.value
    # Routed here by `decide_after_understanding` before any leave step ran, so the state
    # carries the intent and nothing else that would explain the refusal.
    if (
        state.get("question_intent") in LEAVE_INTENTS
        and (state.get("employee_facts") or {}).get("employment_status") == ONBOARDING
    ):
        return FallbackReason.NOT_STARTED_YET.value
    if state.get("question_intent") == QuestionIntent.ABOUT_THE_LAST_ANSWER:
        return FallbackReason.NOTHING_TO_REPHRASE.value
    if state.get("required_evidence") == "unsupported":
        return FallbackReason.NEEDS_HUMAN.value
    if state.get("unsupported_claims"):
        return FallbackReason.UNSUPPORTED_CLAIMS.value
    return FallbackReason.NO_EVIDENCE.value
