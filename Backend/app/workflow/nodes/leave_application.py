"""
Applying for leave, as separate steps rather than one step that pauses twice.

Applying asks the employee two things: which dates, and then whether the request in front
of them is right. Both were `interrupt()` calls inside a single step.

Resuming re-runs a step from its beginning, so every resume replayed everything in front
of the pause. Two model calls to read the request out of the message, and a fresh read of
the leave balance, ran again each time. The second of those is the one that matters: the
balance behind the card an employee is looking at was re-read after they had already seen
it, so what they confirmed and what was committed could differ.

The pauses now sit in steps of their own, containing nothing but the pause — the shape
`clarification.py` already uses, and for the same reason. What runs before a pause runs
once. What the employee confirmed is checked again at the moment of writing, so a card
that has gone stale fails rather than committing something they were never shown.
"""

import logging
from datetime import date

from langgraph.types import interrupt

from app.domain.enums import AnswerStatus
from app.services.leave_service import validate_leave_policy
from app.workflow.conversation_state import ConversationState
from app.workflow.language_model_client import generate_structured_output
from app.workflow.nodes.handle_leave_action import AFFIRMATIVE_REPLY, NEGATIVE_REPLY
from app.workflow.prompts import LEAVE_EXTRACTION_INSTRUCTIONS
from app.workflow.structured_outputs import LeaveApplicationDraft
from app.workflow.tools import run_tool

logger = logging.getLogger(__name__)

# How many times the employee may be asked for dates before the request is let go.
# Without a cap the calendar can be offered forever to a message no reading of which
# yields a date.
MOST_TIMES_TO_ASK_FOR_DATES = 1

# Where the application has got to. The branching function reads these and nothing else.
NEEDS_DATES = "needs_dates"
GAVE_UP_ON_DATES = "gave_up_on_dates"
POLICY_SAYS_NO = "policy_says_no"
AWAITING_CONFIRMATION = "awaiting_confirmation"


def _read_the_request(state: ConversationState) -> LeaveApplicationDraft:
    """What the employee is asking for, including anything they added at a pause."""
    prompt = (
        f"Today's date is: {date.today().strftime('%Y-%m-%d')}\n"
        f"Employee ID: {state['employee_id']}\n"
        f"Employee message: \"{state['employee_question']}\"\n"
    )
    if state.get("employee_clarification_reply"):
        prompt += f"Prior clarification reply: \"{state['employee_clarification_reply']}\"\n"
    if state.get("leave_dates_reply"):
        prompt += f"Employee provided dates: \"{state['leave_dates_reply']}\"\n"

    return generate_structured_output(
        messages=[
            {"role": "system", "content": LEAVE_EXTRACTION_INSTRUCTIONS},
            {"role": "user", "content": prompt},
        ],
        output_model=LeaveApplicationDraft,
    )


def handle_leave_application(state: ConversationState) -> dict:
    """
    Read the request, check it against the policy, and decide what happens next.

    Runs again after the employee picks dates, which is the one thing worth re-reading:
    they have just said something new. Everything else that used to re-run on a resume no
    longer sits in front of a pause.
    """
    language = state.get("requested_language", "en")
    draft = _read_the_request(state)

    logger.info(
        f"Read a leave request for {state['employee_id']}: type={draft.leave_type}, "
        f"start={draft.start_date}, end={draft.end_date}, complete={draft.is_complete}"
    )

    if not draft.is_complete or not draft.start_date:
        already_asked = state.get("leave_dates_round", 0)
        if already_asked < MOST_TIMES_TO_ASK_FOR_DATES:
            return {"leave_stage": NEEDS_DATES, "leave_draft": draft.model_dump()}

        logger.info("Asked for dates once already and still have none; letting it go")
        return {
            "leave_stage": GAVE_UP_ON_DATES,
            "final_answer": (
                "تعذر معالجة طلب الإجازة دون تواريخ محددة. يرجى المحاولة مرة أخرى بتواريخ واضحة."
                if language == "ar"
                else "I could not read the dates for your leave request. Please try again "
                "with the start and end dates."
            ),
            "answer_status": AnswerStatus.SAFE_FALLBACK.value,
            "citations": [],
        }

    validation = validate_leave_policy(employee_id=state["employee_id"], draft=draft)

    if not validation.is_valid:
        violations = "\n".join(f"• {violation}" for violation in validation.violations)
        return {
            "leave_stage": POLICY_SAYS_NO,
            "final_answer": (
                f"⚠️ **تعذر تقديم طلب الإجازة بسبب شروط السياسة:**\n\n{violations}\n\n"
                "إذا كنت بحاجة إلى استثناء، يرجى التواصل مع مديرك المباشر أو الموارد البشرية."
                if language == "ar"
                else f"⚠️ **Unable to submit leave request due to policy requirements:**\n\n"
                f"{violations}\n\nPlease adjust your dates, or contact your line manager "
                f"({validation.approver_name}) or People & Culture."
            ),
            "answer_status": AnswerStatus.ACTION_REJECTED.value,
            "leave_draft": draft.model_dump(),
            "leave_validation": validation.model_dump(),
            "action_payload": {
                "action_type": "POLICY_VIOLATION",
                "is_valid": False,
                "violations": validation.violations,
                "leave_type": validation.leave_type,
                "start_date": validation.start_date,
                "end_date": validation.end_date,
                "working_days": validation.working_days,
            },
            "citations": [],
        }

    return {
        "leave_stage": AWAITING_CONFIRMATION,
        "leave_draft": draft.model_dump(),
        "leave_validation": validation.model_dump(),
    }


def request_leave_dates(state: ConversationState) -> dict:
    """Offer the calendar. No pause here — see the note at the top."""
    language = state.get("requested_language", "en")
    draft = state.get("leave_draft") or {}
    leave_type = draft.get("leave_type") or ("إجازة اعتيادية" if language == "ar" else "Annual leave")

    question = (
        f"يرجى تحديد التواريخ المطلوبة من التقويم أدناه لطلب {leave_type}:"
        if language == "ar"
        else f"Please pick your dates on the calendar below to apply for {leave_type}:"
    )

    return {
        "clarification_question": question,
        "original_question": state["employee_question"],
        "is_awaiting_clarification": True,
        "action_payload": {
            "action_type": "SHOW_LEAVE_CALENDAR_PICKER",
            "leave_type": leave_type,
            "min_date": date.today().strftime("%Y-%m-%d"),
        },
        "is_action_required": True,
    }


def wait_for_leave_dates(state: ConversationState) -> dict:
    """Pause until the employee picks dates. Nothing else belongs in here."""
    reply = interrupt(
        {
            "clarification_question": state.get("clarification_question"),
            "original_question": state.get("original_question"),
            "action_payload": state.get("action_payload"),
            "is_action_required": True,
        }
    )
    return {
        "leave_dates_reply": str(reply or ""),
        "leave_dates_round": state.get("leave_dates_round", 0) + 1,
        "is_awaiting_clarification": False,
    }


def compose_leave_confirmation(state: ConversationState) -> dict:
    """Build the card the employee is asked to confirm. No pause here."""
    language = state.get("requested_language", "en")
    validation = state["leave_validation"]

    question = (
        f"يرجى مراجعة وتأكيد طلب {validation['leave_type']} أدناه:"
        if language == "ar"
        else f"Please review and confirm your {validation['leave_type']} request below:"
    )

    def whole_if_it_can_be(number):
        return int(number) if float(number).is_integer() else number

    return {
        "clarification_question": question,
        "original_question": state["employee_question"],
        "is_awaiting_clarification": True,
        "is_action_required": True,
        "action_payload": {
            "action_type": "CONFIRM_LEAVE_APPLICATION",
            "leave_type": validation["leave_type"],
            "start_date": validation["start_date"],
            "end_date": validation["end_date"],
            "working_days": validation["working_days"],
            "balance_before": whole_if_it_can_be(validation["balance_before"]),
            "balance_after": whole_if_it_can_be(validation["balance_after"]),
            "approver_name": validation["approver_name"],
            "notice_compliant": validation["notice_compliant"],
            "requires_medical_certificate": validation["requires_medical_certificate"],
            "summary_text": question,
        },
    }


def wait_for_leave_confirmation(state: ConversationState) -> dict:
    """Pause until the employee confirms or declines. Nothing else belongs in here."""
    decision = interrupt(
        {
            "clarification_question": state.get("clarification_question"),
            "original_question": state.get("original_question"),
            "action_payload": state.get("action_payload"),
            "is_action_required": True,
        }
    )
    return {
        "leave_confirmation_reply": str(decision or ""),
        "is_awaiting_clarification": False,
    }


def _is_a_decision(reply: str) -> bool:
    """
    Whether this reply is an answer to "confirm?" rather than a fresh request.

    A card sitting open used to take any message containing a word like "apply" as a yes.
    So "apply for 5 days sick leave in June", typed while an annual leave card was open,
    confirmed the annual leave card and lost the sick leave request without saying so.

    A decision is short. Anything long enough to carry a new request is treated as one,
    which fails closed: nothing is committed and the employee is told so.
    """
    return len(reply.split()) <= 4


def submit_leave_application(state: ConversationState) -> dict:
    """
    Commit the request the employee confirmed — if that is still what it is.

    The policy is checked again here rather than trusted from before the pause. A balance
    can move between a card being drawn and a card being confirmed, and the only honest
    answers are to commit what was shown or to refuse; committing something else is not
    among them.
    """
    language = state.get("requested_language", "en")
    reply = (state.get("leave_confirmation_reply") or "").strip()

    declined = {
        "answer_status": AnswerStatus.ACTION_REJECTED.value,
        "action_payload": {"action_type": "LEAVE_CANCELLED_BY_USER"},
        "citations": [],
    }

    if NEGATIVE_REPLY.search(reply) and _is_a_decision(reply):
        return {
            **declined,
            "final_answer": (
                "تم إلغاء طلب الإجازة. لم يتم إجراء أي تغيير على رصيدك."
                if language == "ar"
                else "Your leave request has been cancelled. Nothing has changed on your balance."
            ),
        }

    if not (AFFIRMATIVE_REPLY.search(reply) and _is_a_decision(reply)):
        logger.info(f"Not a confirmation, so nothing was submitted: {reply[:60]!r}")
        return {
            **declined,
            "final_answer": (
                "لم يتم إرسال طلب الإجازة لعدم تأكيده. يرجى إخباري إذا كنت ترغب في تقديم طلب جديد."
                if language == "ar"
                else "I did not submit that leave request, because it was not confirmed. "
                "Tell me if you would like to start a new one."
            ),
        }

    draft = LeaveApplicationDraft(**state["leave_draft"])
    checked_again = validate_leave_policy(employee_id=state["employee_id"], draft=draft)

    if not checked_again.is_valid:
        logger.info("The request no longer passes the policy check; refusing to submit")
        return {
            **declined,
            "final_answer": (
                "تغيّر رصيدك منذ عرض هذا الطلب، ولم يعد مطابقاً للسياسة. لم يتم إرسال أي شيء."
                if language == "ar"
                else "Your balance has changed since this request was drawn up, and it no "
                "longer meets the policy. Nothing has been submitted."
            ),
        }

    submission = run_tool(
        "apply_for_leave",
        authorised_to_write=True,
        employee_id=state["employee_id"],
        validation=checked_again,
        reason=draft.reason,
    )

    if not submission.ok:
        return {
            "final_answer": (
                "لم أتمكن من إرسال طلب الإجازة، ولم يطرأ أي تغيير على رصيدك. يرجى المحاولة مرة أخرى."
                if language == "ar"
                else "I could not submit your leave request, and nothing has changed on "
                "your balance. Please try again, or contact People & Culture if it keeps "
                "happening."
            ),
            "answer_status": AnswerStatus.SAFE_FALLBACK.value,
            "citations": [],
        }

    return {
        "final_answer": (
            "✅ **تم إرسال طلب الإجازة بنجاح وهو بانتظار اعتماد المدير.**"
            if language == "ar"
            else "✅ **Leave Request Submitted & Awaiting Manager Approval!**"
        ),
        "answer_status": AnswerStatus.ACTION_EXECUTED.value,
        "action_payload": {
            "action_type": "LEAVE_SUBMITTED_PENDING_APPROVAL",
            "receipt": submission.result,
        },
        "citations": [],
    }
