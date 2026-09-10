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
from app.integrations.hcs11_client import read_school_claims, read_visa_case
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
    NOTHING_TO_UPLOAD_NO_CASE_MESSAGES,
    NO_SCHOOL_CLAIM_AND_VISA_DONE_MESSAGES,
    NO_SCHOOL_CLAIM_BUT_VISA_MESSAGES,
    NOTHING_TO_UPLOAD_NO_PLAN_MESSAGES,
    VISA_ALL_IN_MESSAGES,
    VISA_UPLOAD_MESSAGES,
    CONTRACT_SIGN_MESSAGES,
    CONTRACT_ALREADY_SIGNED_MESSAGES,
    CONTRACT_NEEDS_A_CORRECT_COPY_MESSAGES,
    CONTRACT_NO_CASE_MESSAGES,
    NO_VISA_CASE_MESSAGES,
    NO_VISA_CASE_BUT_SCHOOL_MESSAGES,
    OUT_OF_SCOPE_MESSAGES,
    PLEASANTRY_MESSAGES,
    REPEAT_GREETING_MESSAGES,
    GREETING_BODY,
    GREETING_OPENINGS,
    ISLAMIC_GREETING_OPENINGS,
    DOCUMENT_UPLOAD_RESPONSE,
    DOCUMENT_UPLOAD_RESPONSE_WITH_FILES,
    message_in_language,
)

logger = logging.getLogger(__name__)


# A claim that has been paid out is closed, and the upload window filters it out too. The
# chat must promise exactly what the window will show.
CLOSED_PAYMENT_STATUSES = {"Sent", "Paid"}


def generate_document_upload_prompt(state: ConversationState) -> dict:
    """
    Open the upload window — but only when there is something to open it against.

    This used to offer the button to anybody who asked. An employee with no education
    allowance was told "the window lists what your claim still needs" about a claim that
    did not exist; so was a leaver whose record still carried a plan he was no longer
    eligible for; and so, once they were added, were the new joiners, who need the visa
    window rather than this one.

    Checking the plan on the record would have caught the first and missed the second: a
    leaver's plan is a leftover, and only HCS-11 knows the claim is gone. So the question
    put to HCS-11 is what cases this person actually has, which answers both "is there
    anything to send?" and "which window?" at once.

    Asked here rather than at the start of the turn, so no other question pays for it.
    Fails open: if HCS-11 cannot be reached we offer the window anyway and let it report
    the failure itself, because blocking somebody who does have a claim is worse than a
    window that opens onto an error.
    """
    employee_id = state["employee_id"]
    language = state.get("requested_language", "en")
    question = (state.get("employee_question") or "").lower()

    school_claims = read_school_claims(employee_id)
    visa_cases = read_visa_case(employee_id)
    could_not_ask = school_claims is None and visa_cases is None

    open_claims = [
        claim for claim in (school_claims or [])
        if claim.get("payment_status") not in CLOSED_PAYMENT_STATUSES
    ]

    # What they asked for, when they said. `understand_query` reads it off their words;
    # nothing else in the turn can, because by here only the record is in hand.
    asked_for = state.get("document_kind")

    if asked_for == "contract":
        # Ahead of the two below and of the school fallthrough. A contract lives on a visa
        # case, so somebody who has one always has the other — but they asked to sign, not
        # to send, and answering with an upload window would be the wrong-window mistake
        # again in a new costume.
        return _open_the_contract_window(state, language, visa_cases)

    if asked_for == "visa":
        if visa_cases:
            return _open_the_visa_window(state, language, visa_cases)
        # The mirror of the school branch below, and it was missing: this used to fall into
        # `_nothing_to_upload`, whose two messages are both about an education allowance. So
        # somebody already working who asked to send visa documents was told about their
        # schooling claim and never told the one thing they had asked — that there is no
        # visa case. A refusal has to refuse the question that was put.
        return _no_visa_case_but_a_school_claim(state, language, open_claims, could_not_ask)

    if not open_claims and not could_not_ask:
        # Somebody who asked for schooling and has no claim is told that, and offered the
        # visa window as a separate sentence rather than handed it instead. This used to
        # open the visa window silently on the reasoning that a new joiner's case is a
        # visa case — true of the person, and no answer at all to the question they
        # asked. They were left believing they had submitted for schooling.
        if asked_for == "school":
            return _no_school_claim_but_a_visa_case(state, language, visa_cases)
        if visa_cases:
            return _open_the_visa_window(state, language, visa_cases)
        return _nothing_to_upload(state, language)

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


def _anything_left_to_send(cases: list | None) -> bool:
    """
    Is there actually something outstanding on the visa case?

    Asked because the messages say there is. Before this, "you do have employment visa
    documents outstanding" was sent to anybody who had a case at all — including somebody
    who had sent every one of them and whose case was already with HC Services. A document
    that came back with a problem also counts: it has to be sent again.
    """
    for case in cases or []:
        if case.get("missing_documents") or case.get("problems"):
            return True
    return False


def _no_school_claim_but_a_visa_case(
    state: ConversationState, language: str, visa_cases: list | None
) -> dict:
    """
    They asked for schooling and have none. Say so, then say what they do have.

    Order matters more than either half. Offering the visa window first, or instead, is
    how somebody comes away thinking they have submitted for schooling. The refusal is the
    answer to their question; the offer is a separate, useful sentence after it.
    """
    if not visa_cases:
        return _nothing_to_upload(state, language)

    # Nothing outstanding is not the same as having a case. Saying "you do have documents
    # outstanding" to somebody who has sent all of them, and offering a button to send
    # them again, is the reason this check exists.
    if not _anything_left_to_send(visa_cases):
        logger.info(
            f"{state['employee_id']} asked to send school documents and has none; "
            f"their visa documents are all in, so nothing is offered"
        )
        return {
            "final_answer": _clean_and_format_markdown(
                message_in_language(NO_SCHOOL_CLAIM_AND_VISA_DONE_MESSAGES, language)
            ),
            "citations": [],
            "answer_status": AnswerStatus.VERIFIED.value,
            "question_intent": QuestionIntent.HR_QUESTION.value,
            "action_payload": None,
        }

    case_id = next((case.get("case_id") for case in visa_cases if case.get("case_id")), None)
    logger.info(
        f"{state['employee_id']} asked to send school documents and has none; "
        f"saying so and offering the visa window ({case_id})"
    )

    return {
        "final_answer": _clean_and_format_markdown(
            message_in_language(NO_SCHOOL_CLAIM_BUT_VISA_MESSAGES, language)
        ),
        "citations": [],
        "answer_status": AnswerStatus.VERIFIED.value,
        "question_intent": QuestionIntent.HR_QUESTION.value,
        "action_payload": {"action_type": "VISA_DOCUMENT_UPLOAD", "case_id": case_id},
    }


def _no_visa_case_but_a_school_claim(
    state: ConversationState,
    language: str,
    open_claims: list,
    could_not_ask: bool,
) -> dict:
    """
    They asked for the visa and have no case. Say so, then say what they do have.

    The exact shape of `_no_school_claim_but_a_visa_case` above, pointing the other way.
    The asymmetry it removes was visible on screen: asking for schooling with no claim
    named the schooling and then offered the visa, while asking for the visa with no case
    named neither and explained an education allowance instead.

    A visa case that could not be read is not a visa case that does not exist, so an
    unreachable HCS-11 keeps the window rather than denying the case — the same rule the
    rest of this file follows.
    """
    if could_not_ask:
        logger.info(
            f"Could not reach HCS-11 for {state['employee_id']}; offering the visa "
            f"window anyway rather than denying a case that may exist"
        )
        return {
            "final_answer": _clean_and_format_markdown(
                message_in_language(VISA_UPLOAD_MESSAGES, language)
            ),
            "citations": [],
            "answer_status": AnswerStatus.VERIFIED.value,
            "question_intent": QuestionIntent.HR_QUESTION.value,
            "action_payload": {"action_type": "VISA_DOCUMENT_UPLOAD", "case_id": None},
        }

    if not open_claims:
        logger.info(f"{state['employee_id']} asked to send visa documents and has no case")
        return {
            "final_answer": _clean_and_format_markdown(
                message_in_language(NO_VISA_CASE_MESSAGES, language)
            ),
            "citations": [],
            "answer_status": AnswerStatus.VERIFIED.value,
            "question_intent": QuestionIntent.HR_QUESTION.value,
            "action_payload": None,
        }

    logger.info(
        f"{state['employee_id']} asked to send visa documents and has no case; "
        f"saying so and offering their school claim instead"
    )
    return {
        "final_answer": _clean_and_format_markdown(
            message_in_language(NO_VISA_CASE_BUT_SCHOOL_MESSAGES, language)
        ),
        "citations": [],
        "answer_status": AnswerStatus.VERIFIED.value,
        # The school button is the one card drawn from the intent rather than the payload,
        # so this is the one refusal that has to carry the upload label to show it.
        "question_intent": QuestionIntent.DOCUMENT_UPLOAD.value,
        "action_payload": None,
    }


def _open_the_visa_window(state: ConversationState, language: str, cases: list) -> dict:
    """
    Hand over to the visa document window.

    Carried on `action_payload` rather than on the intent label. Five of the six cards the
    interface can draw are chosen by `action_type`; only the school upload button is chosen
    by the intent, and it is the odd one out. Following the majority leaves the school path
    untouched and adds nothing to the published intent vocabulary.
    """
    # The same check as above, for the same reason: this message says the window "lists
    # what your route still needs", which is not true of somebody whose route needs
    # nothing. Offering them a button to send documents they have already sent is how a
    # finished application is made to look unfinished.
    if not _anything_left_to_send(cases):
        logger.info(f"{state['employee_id']} has sent every visa document; nothing offered")
        return {
            "final_answer": _clean_and_format_markdown(
                message_in_language(VISA_ALL_IN_MESSAGES, language)
            ),
            "citations": [],
            "answer_status": AnswerStatus.VERIFIED.value,
            "question_intent": QuestionIntent.HR_QUESTION.value,
            "action_payload": None,
        }

    case_id = next((case.get("case_id") for case in cases if case.get("case_id")), None)
    logger.info(f"Opening the visa document window for {state['employee_id']} ({case_id})")

    return {
        "final_answer": _clean_and_format_markdown(
            message_in_language(VISA_UPLOAD_MESSAGES, language)
        ),
        "citations": [],
        "answer_status": AnswerStatus.VERIFIED.value,
        # An ordinary question as far as the intent label goes, so the *school* button is
        # not drawn alongside the visa one.
        "question_intent": QuestionIntent.HR_QUESTION.value,
        "action_payload": {"action_type": "VISA_DOCUMENT_UPLOAD", "case_id": case_id},
    }


def _open_the_contract_window(
    state: ConversationState, language: str, cases: list | None
) -> dict:
    """
    Hand over to the contract window, and say honestly which of three states it is in.

    The one that matters is the middle one. A case can carry a job-offer form that HCS-11
    has not accepted — an unsigned copy the joiner uploaded themselves — and HCS-11 stamps
    a date on it regardless, so the date alone cannot be read as a signature. The reader
    has already consulted HCS-11's own OFFER_SIGNED check and settled it into
    `contract_is_signed`; that is the field consulted here, and nothing else.

    The window still opens when it is already signed, because reading a contract you have
    signed is a reasonable thing to want and the panel shows the filed copy.
    """
    if cases is None:
        # HCS-11 could not be reached. The window reports that itself, and the alternative
        # — refusing on the grounds that no case was seen — is the answer that tells
        # somebody with a contract that they have none.
        logger.info(f"Opening the contract window for {state['employee_id']} unverified")
        return _contract_reply(state, language, CONTRACT_SIGN_MESSAGES, None)

    with_a_contract = next(
        (case for case in cases if case.get("contract_prepared_on")
         or case.get("contract_signed_on")),
        None,
    )
    if with_a_contract is None:
        logger.info(f"No employment contract for {state['employee_id']}")
        return {
            "final_answer": _clean_and_format_markdown(
                message_in_language(CONTRACT_NO_CASE_MESSAGES, language)
            ),
            "citations": [],
            "answer_status": AnswerStatus.VERIFIED.value,
            "question_intent": QuestionIntent.HR_QUESTION.value,
            "action_payload": None,
        }

    case_id = with_a_contract.get("case_id")
    if with_a_contract.get("contract_is_signed"):
        message = CONTRACT_ALREADY_SIGNED_MESSAGES
    elif with_a_contract.get("contract_signed_on"):
        message = CONTRACT_NEEDS_A_CORRECT_COPY_MESSAGES
    else:
        message = CONTRACT_SIGN_MESSAGES

    logger.info(f"Opening the contract window for {state['employee_id']} ({case_id})")
    return _contract_reply(state, language, message, case_id)


def _contract_reply(
    state: ConversationState, language: str, message: dict, case_id: str | None
) -> dict:
    """The contract window's answer, whichever of its states produced it."""
    return {
        "final_answer": _clean_and_format_markdown(message_in_language(message, language)),
        "citations": [],
        "answer_status": AnswerStatus.VERIFIED.value,
        # An ordinary question as far as the label goes, so the school button is not drawn
        # beside this one. The card is chosen by `action_type`, as the visa one is.
        "question_intent": QuestionIntent.HR_QUESTION.value,
        "action_payload": {"action_type": "CONTRACT_SIGNING", "case_id": case_id},
    }


def _nothing_to_upload(state: ConversationState, language: str) -> dict:
    """
    Say why there is nothing to send, and drop the button.

    The intent is reported as an ordinary question rather than a document upload, because
    that label is what makes the interface draw the button. A reply explaining that there
    is nothing to upload, with an Upload Documents button underneath it, would be worse
    than either half alone.
    """
    if (state.get("employee_facts") or {}).get("education_plan_code") in ("", "NONE", None):
        message = message_in_language(NOTHING_TO_UPLOAD_NO_PLAN_MESSAGES, language)
        reason = "no education allowance on the package"
    else:
        message = message_in_language(NOTHING_TO_UPLOAD_NO_CASE_MESSAGES, language)
        reason = "an allowance, but no open claim"

    logger.info(f"Not offering the upload window to {state['employee_id']}: {reason}")

    return {
        "final_answer": _clean_and_format_markdown(message),
        "citations": [],
        "answer_status": AnswerStatus.VERIFIED.value,
        "question_intent": QuestionIntent.HR_QUESTION.value,
        "action_payload": None,
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
    full_name = (facts.get("name_ar") if lang == "ar" else facts.get("name")) or (facts.get("name") or "")
    # What somebody is called, not what is printed on their record. "Hello Ahmed Al Rashid"
    # is how a system addresses a case file; a greeting is the one place the person is
    # being spoken to rather than looked up. Falls back to the whole string, then to
    # "there", so a record with one name or none still greets somebody.
    employee_name = full_name.split()[0] if full_name.split() else "there"

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

    # 4. Not the first hello of this conversation.
    #
    # This used to ask whether the conversation had any remembered turns, and a greeting is
    # deliberately never remembered — its reply is a menu of topics, and leaving that in the
    # next question's prompt reads as a list of things to talk about. So three hellos in a
    # row each looked like the first and got the same sentence, introduction and all.
    #
    # `already_greeted` is the narrow fact that question actually wanted. It belongs to the
    # conversation rather than the turn, so it is kept out of the reset in
    # `load_employee_facts` alongside the two other fields that outlive a question.
    if state.get("already_greeted") or (state.get("remembered_turns") or []):
        answer_tmpl = message_in_language(REPEAT_GREETING_MESSAGES, lang)
        answer = answer_tmpl.format(employee_name=employee_name)
        return {
            "final_answer": _clean_and_format_markdown(answer),
            "citations": [],
            "answer_status": AnswerStatus.VERIFIED.value,
        }

    # 5. First-turn standard welcome greeting
    # Built from the constants rather than written out here.
    #
    # These were four hardcoded f-strings, and `GREETING_MESSAGES` sat unused beside them
    # saying something slightly different — so the wording was fixed in one place and stayed
    # wrong in the other. The greeting proper lives in `GREETING_BODY`; only the opening
    # word differs between a hello and a salam, and only that is chosen here.
    opening = (
        message_in_language(ISLAMIC_GREETING_OPENINGS, lang)
        if ISLAMIC_GREETING_PATTERN.search(question)
        else message_in_language(GREETING_OPENINGS, lang)
    )
    full_greeting = (
        f"{opening} {employee_name}! {message_in_language(GREETING_BODY, lang)}"
    )

    return {
        "final_answer": _clean_and_format_markdown(full_greeting),
        "citations": [],
        "answer_status": AnswerStatus.VERIFIED.value,
        # So the next hello is answered as a second one.
        "already_greeted": True,
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
