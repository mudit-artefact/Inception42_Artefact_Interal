"""
Leave actions that answer in one go: cancelling, checking status, and a manager's
approvals.

Applying for leave is not here. It is the one action that pauses to ask the employee
something — twice — so it lives in `leave_application.py`, split into steps that can be
paused in. See the note at the top of that module.
"""

import logging
import re

from app.database.engine import SessionLocal
from app.database.tables import Employee, LeaveRequest
from app.domain.enums import AnswerStatus, QuestionIntent
from app.services.leave_service import (
    get_manager_pending_approvals,
    get_pending_leave_requests,
)
from app.workflow.conversation_state import ConversationState
from app.workflow.tools import run_tool

logger = logging.getLogger(__name__)

AFFIRMATIVE_REPLY = re.compile(
    r"\b(confirm|yes|proceed|apply|submit|ok|okay|agree|approved|sure|نعم|تأكيد|موافق|تقديم)\b",
    re.IGNORECASE,
)

NEGATIVE_REPLY = re.compile(
    r"\b(cancel|no|stop|reject|abort|nevermind|don't|dont|لا|إلغاء|الغاء)\b",
    re.IGNORECASE,
)


def _could_not_act(outcome, lang: str, *, english: str, arabic: str) -> dict:
    """
    An action that did not happen, said in the employee's own language.

    A service that declines on purpose writes its own sentence — "request #12 is already
    Approved" — and that sentence is ours, so it is safe to pass on. It is only written in
    English, though, so an Arabic turn gets the Arabic line here instead; an English
    sentence in an Arabic reply fails the language check and would be thrown away anyway.

    Anything that actually broke says none of this. Its traceback is in the log.
    """
    declined_in_our_words = (
        outcome.result.get("message") if isinstance(outcome.result, dict) else None
    )
    if lang == "en" and declined_in_our_words:
        spoken = declined_in_our_words
    else:
        spoken = arabic if lang == "ar" else english

    return {
        "final_answer": spoken,
        "answer_status": AnswerStatus.SAFE_FALLBACK.value,
        "citations": [],
    }


# Applying for leave now lives in `leave_application.py`, split into steps so that the
# two pauses it needs sit in steps of their own. It was one step holding both, and every
# resume replayed everything in front of the pause: two model calls to read the request,
# and a fresh read of the balance the employee had already been shown.


def handle_manager_approval(state: ConversationState) -> dict:
    """Handle approve_leave and reject_leave intents from managers."""
    manager_id = state["employee_id"]
    question = state["employee_question"]
    lang = state.get("requested_language", "en")
    intent = state.get("question_intent")

    pending_approvals = get_manager_pending_approvals(manager_id)

    # Distinguish between inquiry ("what do I need to approve?", "show requests") vs explicit action ("approve leave #12")
    is_inquiry = bool(
        re.search(
            r"\b(what|which|show|list|view|check|need to approve|to approve|pending|requests? to approve|do i|leaves? awaiting)\b",
            question,
            re.I,
        )
    )
    # An action command must be an imperative instruction to approve or reject
    is_action_command = (
        bool(re.search(r"^\s*(please\s+)?(approve|reject|decline|accept)\b", question, re.I))
        or bool(re.search(r"\b(please\s+)?(approve|reject|decline|accept)\s+(leave|request|#|\d+|for\s+[a-zA-Z]+)\b", question, re.I))
    ) and not is_inquiry

    manager = None
    session = SessionLocal()
    try:
        manager = session.query(Employee).filter(Employee.user_id == manager_id).first()
    finally:
        session.close()

    b_name = manager.name.split()[0] if manager and manager.name else "there"

    if is_inquiry or not is_action_command or intent == QuestionIntent.CHECK_LEAVE_STATUS:
        if not pending_approvals:
            msg = (
                f"No {b_name}, you don't have any leave request pending of your juniors."
                if lang == "en"
                else f"لا {b_name}، لا توجد لديك أي طلبات إجازة معلقة من موظفيك."
            )
            return {
                "final_answer": msg,
                "answer_status": AnswerStatus.VERIFIED.value,
                "citations": [],
            }

        msg = (
            "You can review and click **Approve Leave** or **Reject** on the card below."
            if lang == "en"
            else "يمكنك مراجعة الطلب والنقر على **اعتماد الإجازة** أو **رفض** في البطاقة أدناه."
        )
        return {
            "final_answer": msg,
            "answer_status": AnswerStatus.VERIFIED.value,
            "action_payload": {
                "action_type": "MANAGER_PENDING_APPROVALS",
                "pending_approvals": pending_approvals,
            },
            "citations": [],
        }

    # Which request this is about. `pending_approvals` is already scoped to this
    # manager's own direct reports, so it is the only list a target may come from.
    #
    # A number in the message is a hint, not an instruction. It used to be taken
    # literally — any integer anywhere in the sentence became the request id, checked
    # against nothing — so "approve 3 days of annual leave" approved request #3,
    # whoever it belonged to.
    approvable = {approval["request_id"]: approval for approval in pending_approvals}
    target_id = None

    stated = re.search(r"#?\b(\d+)\b", question)
    if stated and int(stated.group(1)) in approvable:
        target_id = int(stated.group(1))

    if target_id is None:
        # A first name only decides it when exactly one report answers to it. Two people
        # called Omar is not a tie to break by picking the earlier row.
        named = [
            approval["request_id"]
            for approval in pending_approvals
            if approval["employee_name"].split()[0].lower() in question.lower()
        ]
        if len(named) == 1:
            target_id = named[0]

    if target_id is None and len(pending_approvals) == 1:
        target_id = pending_approvals[0]["request_id"]

    if not target_id:
        msg = (
            "Please review and click **Approve Leave** or **Reject** on the card below."
            if lang == "en"
            else "يرجى مراجعة الطلبات والنقر على **اعتماد الإجازة** أو **رفض** في البطاقة أدناه."
        )
        return {
            "final_answer": msg,
            "answer_status": AnswerStatus.VERIFIED.value,
            "action_payload": {
                "action_type": "MANAGER_PENDING_APPROVALS",
                "pending_approvals": pending_approvals,
            },
            "citations": [],
        }

    if intent == QuestionIntent.REJECT_LEAVE or re.search(r"\b(reject|decline)\b", question, re.I):
        # The target came from this manager's own scoped list, which is what authorises
        # the write from the workflow's side. The reporting-line check inside the
        # database transaction is the layer below this one, and is still owed.
        outcome = run_tool(
            "reject_leave",
            authorised_to_write=True,
            manager_id=manager_id,
            request_id=target_id,
        )
        if not outcome.ok:
            return _could_not_act(
                outcome,
                lang,
                english="I could not reject that request. Nothing has changed.",
                arabic="لم أتمكن من رفض هذا الطلب، ولم يطرأ أي تغيير.",
            )
        res = outcome.result
        ans = (
            f"❌ **Leave Request has been Rejected.**\n\n"
            f"Request from **{res['employee_name']}** for {res['days_requested']} days of {res['leave_type']} "
            f"has been marked as Rejected. The employee has been notified."
            if lang == "en"
            else f"❌ **تم رفض طلب الإجازة.**\n\n"
            f"طلب **{res['employee_name']}** لمدة {res['days_requested']} أيام من {res['leave_type']} "
            f"تم رفضه، وقد تم إشعار الموظف."
        )
        return {
            "final_answer": ans,
            "answer_status": AnswerStatus.ACTION_EXECUTED.value,
            "action_payload": {"action_type": "MANAGER_REJECTED_SUCCESS", "result": res},
            "citations": [],
        }

    # Only approve if explicit approve command is present and NOT an inquiry!
    if is_action_command and (intent == QuestionIntent.APPROVE_LEAVE or re.search(r"\b(approve|accept)\b", question, re.I)):
        outcome = run_tool(
            "approve_leave",
            authorised_to_write=True,
            manager_id=manager_id,
            request_id=target_id,
        )
        if not outcome.ok:
            return _could_not_act(
                outcome,
                lang,
                english="I could not approve that request. Nothing has changed.",
                arabic="لم أتمكن من اعتماد هذا الطلب، ولم يطرأ أي تغيير.",
            )
        res = outcome.result

        ans = (
            "Thanks for approving leave!"
            if lang == "en"
            else "شكراً لموافقتك على الإجازة!"
        )

        return {
            "final_answer": ans,
            "answer_status": AnswerStatus.ACTION_EXECUTED.value,
            "action_payload": {
                "action_type": "MANAGER_APPROVED_SUCCESS",
                "result": res,
            },
            "citations": [],
        }

    # Otherwise, display the pending approvals card!
    msg = (
        "Please review and click **Approve Leave** or **Reject** on the card below."
        if lang == "en"
        else "يرجى مراجعة الطلبات والنقر على **اعتماد الإجازة** أو **رفض** في البطاقة أدناه."
    )
    return {
        "final_answer": msg,
        "answer_status": AnswerStatus.VERIFIED.value,
        "action_payload": {
            "action_type": "MANAGER_PENDING_APPROVALS",
            "pending_approvals": pending_approvals,
        },
        "citations": [],
    }


def handle_leave_status(state: ConversationState) -> dict:
    """Handle check_leave_status intent: list pending / recent leave applications."""
    employee_id = state["employee_id"]
    question = state["employee_question"]
    lang = state.get("requested_language", "en")
    q_lower = question.lower()

    # Guard delegation to manager approvals:
    # Only delegate if the question is specifically inquiring about approvals they need to perform for their team,
    # and NEVER when they are asking about their own leave status!
    is_manager_approval_inquiry = bool(
        re.search(
            r"\b(what leave requests? do i need to approve|need to approve|requests? to approve|pending approvals?( from my team)?|leave requests? awaiting (my )?approval|my team('s)? leave requests?|who (in my team )?requested leave|is there any leave pending for me to approve|any pending leave(s)?|pending leave(s)? to approve|do i have (any )?(leave|approvals?) pending|junior(s)?('s)? leave|did (my |any )?junior(s)? (ask|request))\b",
            q_lower,
        )
    )
    is_self_status_inquiry = bool(
        re.search(
            r"\b(my leave|my leaves|my request|my pending leave|requested leaves?|does my|did my|is my|has my|status of my|leaves? i requested|leave i applied)\b",
            q_lower,
        )
    )

    if is_manager_approval_inquiry and not is_self_status_inquiry:
        return handle_manager_approval(state)

    session = SessionLocal()
    try:
        pending = get_pending_leave_requests(employee_id, session=session)

        # Retrieve the latest leave request overall for this employee
        latest_request = (
            session.query(LeaveRequest)
            .filter(LeaveRequest.employee_id == employee_id)
            .order_by(LeaveRequest.id.desc())
            .first()
        )

        emp = session.query(Employee).filter(Employee.user_id == employee_id).first()

        lines = []
        approved_payload = None

        if latest_request and latest_request.status == "Approved":
            approved_payload = {
                "request_id": latest_request.id,
                "leave_type": latest_request.leave_type,
                "start_date": latest_request.start_date,
                "end_date": latest_request.end_date,
                "days_requested": latest_request.days_requested,
                "approver_name": latest_request.approver_name,
                "manager_name": latest_request.approver_name,
                "employee_name": emp.name if emp else employee_id,
                "manager_email": emp.manager_email if emp else "manager@hcservices.ae",
                "status": "Approved",
            }

            if lang == "ar":
                lines.append(
                    f"🎉 **نعم! تم اعتماد طلب إجازتك!**\n\n"
                    f"تم اعتماد إجازتك ({latest_request.leave_type}) من **{latest_request.start_date}** إلى **{latest_request.end_date}** "
                    f"({latest_request.days_requested} أيام عمل) بواسطة مديرك المباشر **{latest_request.approver_name}**.\n\n"
                    f"هل ترغب في إضافتها إلى تقويمك أو إرسال بريد إلكتروني للمدير عبر الأزرار أدناه؟\n"
                )
            else:
                lines.append(
                    f"🎉 **Yes! Your Leave Request has been Approved!**\n\n"
                    f"Your {latest_request.leave_type} from **{latest_request.start_date}** to **{latest_request.end_date}** "
                    f"({latest_request.days_requested} working days) was approved by your manager, **{latest_request.approver_name}**.\n\n"
                    f"Would you like to mark this on your calendar or email your team?\n"
                )

        elif latest_request and latest_request.status == "Pending":
            if lang == "ar":
                lines.append(
                    f"📋 **طلب إجازتك قيد المراجعة حالياً:**\n\n"
                    f"طلبك لـ {latest_request.days_requested} أيام عمل من {latest_request.start_date} إلى {latest_request.end_date} "
                    f"({latest_request.leave_type}) قيد المراجعة والاعتماد بواسطة مديرك المباشر **{latest_request.approver_name}**."
                )
            else:
                lines.append(
                    f"📋 **Your Leave Request is Currently Pending:**\n\n"
                    f"Your request for {latest_request.days_requested} working days from **{latest_request.start_date}** to **{latest_request.end_date}** "
                    f"({latest_request.leave_type}) is currently pending review and approval by your manager, **{latest_request.approver_name}**."
                )

        elif latest_request and latest_request.status == "Rejected":
            if lang == "ar":
                lines.append(
                    f"❌ **طلب إجازتك تم رفضه:**\n\n"
                    f"طلبك لـ {latest_request.leave_type} تم رفضه من قبل **{latest_request.approver_name}**."
                )
            else:
                lines.append(
                    f"❌ **Your Leave Request was Rejected:**\n\n"
                    f"Your request for {latest_request.leave_type} was rejected by **{latest_request.approver_name}**."
                )

        # If there are other pending requests distinct from the latest shown above
        other_pending = [
            p for p in pending
            if not latest_request or p["id"] != latest_request.id
        ]
        if other_pending:
            if lang == "ar":
                lines.append("\n📋 **طلبات إجازة أخرى معلقة:**\n")
                for req in other_pending:
                    lines.append(
                        f"• **{req['leave_type']}:** من {req['start_date']} إلى {req['end_date']} "
                        f"({req['days_requested']} أيام) — قيد المراجعة بواسطة {req['approver_name']}"
                    )
            else:
                lines.append("\n📋 **Other Pending Leave Requests:**\n")
                for req in other_pending:
                    lines.append(
                        f"• **{req['leave_type']}:** {req['start_date']} to {req['end_date']} "
                        f"({req['days_requested']} working days) — Under review by {req['approver_name']}"
                    )

        if not lines:
            msg = (
                "You currently have no pending or recently approved leave requests."
                if lang == "en"
                else "لا توجد لديك حالياً أي طلبات إجازة معلقة أو معتمدة حديثاً."
            )
            return {
                "final_answer": msg,
                "answer_status": AnswerStatus.VERIFIED.value,
                "citations": [],
            }

        return {
            "final_answer": "\n".join(lines).strip(),
            "answer_status": AnswerStatus.VERIFIED.value,
            "action_payload": {
                "action_type": "LEAVE_APPROVED_NOTIFICATION" if approved_payload else "LEAVE_PENDING_LIST",
                "approved_leave": approved_payload,
                "pending_requests": pending,
            },
            "citations": [],
        }
    finally:
        session.close()


def handle_leave_cancellation(state: ConversationState) -> dict:
    """Handle cancel_leave intent: cancels pending leave and restores balance."""
    employee_id = state["employee_id"]
    question = state["employee_question"]
    lang = state.get("requested_language", "en")

    # Which request, e.g. "cancel leave #3". As with approval, a number only counts when
    # it names one of this employee's own pending requests. The query behind the write
    # already scopes by employee, so this cannot reach another person's row either way —
    # but saying "that is not one of yours" beats a bare "not found".
    pending_read = run_tool("check_leave_status", employee_id=employee_id)
    pending = pending_read.result if pending_read.ok else []
    cancellable = {request["id"] for request in pending}

    target_id = None
    stated = re.search(r"#?\b(\d+)\b", question)
    if stated and int(stated.group(1)) in cancellable:
        target_id = int(stated.group(1))
    elif len(pending) == 1:
        target_id = pending[0]["id"]

    if not target_id:
        if not pending:
            msg = (
                "You don't have any pending leave requests to cancel."
                if lang == "en"
                else "لا توجد لديك أي طلبات إجازة معلقة لإلغائها."
            )
        else:
            msg = (
                "Please specify which leave request you would like to cancel."
                if lang == "en"
                else "يرجى تحديد طلب الإجازة المراد إلغاؤه."
            )
        return {
            "final_answer": msg,
            "answer_status": AnswerStatus.VERIFIED.value,
            "citations": [],
        }

    # The employee asked to cancel their own request, and the target came from their own
    # pending list. That is what authorises the write.
    outcome = run_tool(
        "cancel_leave",
        authorised_to_write=True,
        employee_id=employee_id,
        request_id=target_id,
    )
    if not outcome.ok:
        return _could_not_act(
            outcome,
            lang,
            english="I could not cancel that request. Nothing has changed.",
            arabic="لم أتمكن من إلغاء هذا الطلب، ولم يطرأ أي تغيير.",
        )

    if lang == "ar":
        ans = (
            "✅ **تم إلغاء طلب الإجازة بنجاح!**\n\n"
            "تم تحديث حالة الطلب إلى ملغي."
        )
    else:
        ans = (
            "✅ **Your leave request has been cancelled!**\n\n"
            "The request has been removed from pending approvals."
        )

    return {
        "final_answer": ans,
        "answer_status": AnswerStatus.ACTION_EXECUTED.value,
        "citations": [],
    }
