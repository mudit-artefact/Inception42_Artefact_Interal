"""
Agentic Leave & Absence Action Nodes: Parameter extraction, calendar date picker,
policy validation, Human-in-the-Loop confirmation pauses, manager approvals,
and transactional database commits.
"""

from datetime import date
import logging
import re
from typing import Optional

from langgraph.types import interrupt

from app.database.engine import SessionLocal
from app.database.tables import Employee, LeaveBalance, LeaveRequest
from app.domain.enums import AnswerStatus, QuestionIntent
from app.services.leave_service import (
    approve_leave_request,
    cancel_leave_request,
    commit_leave_request,
    get_manager_pending_approvals,
    get_pending_leave_requests,
    reject_leave_request,
    validate_leave_policy,
)
from app.workflow.conversation_state import ConversationState
from app.workflow.language_model_client import generate_structured_output
from app.workflow.prompts import LEAVE_EXTRACTION_INSTRUCTIONS
from app.workflow.structured_outputs import LeaveApplicationDraft, LeaveCancellationDraft

logger = logging.getLogger(__name__)

AFFIRMATIVE_REPLY = re.compile(
    r"\b(confirm|yes|proceed|apply|submit|ok|okay|agree|approved|sure|نعم|تأكيد|موافق|تقديم)\b",
    re.IGNORECASE,
)

NEGATIVE_REPLY = re.compile(
    r"\b(cancel|no|stop|reject|abort|nevermind|don't|dont|لا|إلغاء|الغاء)\b",
    re.IGNORECASE,
)


def handle_leave_application(state: ConversationState) -> dict:
    """
    Handle the apply_leave intent:
    1. Extract dates, duration, leave type from message.
    2. Check completeness. If missing fields, pause with SHOW_LEAVE_CALENDAR_PICKER interrupt.
    3. Run deterministic policy validation against employee balances and rules.
    4. If invalid, decline with clear policy reasons.
    5. If valid, pause via interrupt for Human-in-the-Loop user confirmation.
    6. Upon confirmation resume, submit to manager as Pending.
    """
    employee_id = state["employee_id"]
    question = state["employee_question"]
    lang = state.get("requested_language", "en")
    today_str = date.today().strftime("%Y-%m-%d")

    # Step A: Extract draft parameters
    extract_prompt = (
        f"Today's date is: {today_str}\n"
        f"Employee ID: {employee_id}\n"
        f'Employee message: "{question}"\n'
    )
    if state.get("employee_clarification_reply"):
        extract_prompt += f'Prior clarification reply: "{state["employee_clarification_reply"]}"\n'

    draft = generate_structured_output(
        messages=[
            {"role": "system", "content": LEAVE_EXTRACTION_INSTRUCTIONS},
            {"role": "user", "content": extract_prompt},
        ],
        output_model=LeaveApplicationDraft,
    )

    logger.info(
        f"Extracted leave draft for {employee_id}: type={draft.leave_type}, "
        f"start={draft.start_date}, end={draft.end_date}, days={draft.days_requested}, "
        f"complete={draft.is_complete}"
    )

    # Step B: If dates/duration missing, pause and offer the interactive calendar picker
    if not draft.is_complete or not draft.start_date:
        clarification_msg = (
            f"Please select your dates on the calendar below to apply for {draft.leave_type or 'Annual leave'}:"
            if lang == "en"
            else f"يرجى تحديد التواريخ المطلوبة من التقويم أدناه لطلب {draft.leave_type or 'إجازة اعتيادية'}:"
        )
        user_reply = interrupt(
            {
                "clarification_question": clarification_msg,
                "original_question": question,
                "action_payload": {
                    "action_type": "SHOW_LEAVE_CALENDAR_PICKER",
                    "leave_type": draft.leave_type or "Annual leave",
                    "min_date": today_str,
                },
                "is_action_required": True,
            }
        )
        # Resumed with dates chosen by employee!
        extract_prompt += f'Employee provided dates: "{user_reply}"\n'
        draft = generate_structured_output(
            messages=[
                {"role": "system", "content": LEAVE_EXTRACTION_INSTRUCTIONS},
                {"role": "user", "content": extract_prompt},
            ],
            output_model=LeaveApplicationDraft,
        )

    # If still incomplete after asking:
    if not draft.is_complete or not draft.start_date:
        fallback_msg = (
            "Unable to process leave request without valid dates. Please try again with specific dates."
            if lang == "en"
            else "تعذر معالجة طلب الإجازة دون تواريخ محددة. يرجى المحاولة مرة أخرى بتواريخ واضحة."
        )
        return {
            "final_answer": fallback_msg,
            "answer_status": AnswerStatus.SAFE_FALLBACK.value,
            "citations": [],
        }

    # Step C: Deterministic policy validation
    validation = validate_leave_policy(employee_id=employee_id, draft=draft)
    state_validation_dict = validation.model_dump()

    # Step D: If policy check fails (insufficient balance, notice violation, probation restriction)
    if not validation.is_valid:
        violations_text = "\n".join(f"• {v}" for v in validation.violations)
        if lang == "ar":
            decline_msg = (
                f"⚠️ **تعذر تقديم طلب الإجازة بسبب شروط السياسة:**\n\n"
                f"{violations_text}\n\n"
                f"إذا كنت بحاجة إلى استثناء أو مزيد من المساعدة، يرجى التواصل مع مسؤول الموارد البشرية أو مديرك المباشر."
            )
        else:
            decline_msg = (
                f"⚠️ **Unable to submit leave request due to policy requirements:**\n\n"
                f"{violations_text}\n\n"
                f"Please adjust your dates or contact your Line Manager ({validation.approver_name}) / HR for special dispensation."
            )

        return {
            "final_answer": decline_msg,
            "answer_status": AnswerStatus.ACTION_REJECTED.value,
            "leave_draft": draft.model_dump(),
            "leave_validation": state_validation_dict,
            "action_payload": {
                "action_type": "POLICY_VIOLATION",
                "is_valid": False,
                "violations": validation.violations,
                "leave_type": validation.leave_type,
                "start_date": validation.start_date,
                "end_date": validation.end_date,
                "working_days": validation.working_days,
            },
            "citations": [
                {
                    "source": "HC-PC-001 §1.4 / omni_hr.db",
                    "section": "Leave Policy Compliance Check",
                    "score": 1.0,
                    "language": lang,
                    "snippet": f"Validated against {validation.leave_type} policies and live balances.",
                }
            ],
        }

    # Step E: Valid! Prepare Human-in-the-Loop Confirmation Card and Pause
    confirmation_question = (
        f"Please confirm your {validation.leave_type} request for **{validation.working_days} working days** "
        f"(from **{validation.start_date}** to **{validation.end_date}**). "
        f"This will be routed to your Line Manager (**{validation.approver_name}**) for review and approval."
        if lang == "en"
        else (
            f"يرجى تأكيد طلب {validation.leave_type} لمدة **{validation.working_days} أيام عمل** "
            f"(من **{validation.start_date}** إلى **{validation.end_date}**). "
            f"سيتم إرسال الطلب إلى مديرك المباشر (**{validation.approver_name}**) للمراجعة والاعتماد."
        )
    )

    action_payload = {
        "action_type": "CONFIRM_LEAVE_APPLICATION",
        "leave_type": validation.leave_type,
        "start_date": validation.start_date,
        "end_date": validation.end_date,
        "working_days": validation.working_days,
        "balance_before": validation.balance_before,
        "balance_after": validation.balance_after,
        "approver_name": validation.approver_name,
        "notice_compliant": validation.notice_compliant,
        "requires_medical_certificate": validation.requires_medical_certificate,
        "summary_text": confirmation_question,
    }

    # LangGraph interrupt: pauses workflow until user confirms or cancels
    user_decision = interrupt(
        {
            "clarification_question": confirmation_question,
            "original_question": question,
            "action_payload": action_payload,
            "is_action_required": True,
        }
    )

    # Step F: User Resumed! Check confirmation decision
    decision_text = str(user_decision or "").strip()
    logger.info(f"Leave action resumed with user decision: '{decision_text}'")

    if NEGATIVE_REPLY.search(decision_text):
        cancel_msg = (
            "Your leave request has been cancelled. No changes were made to your leave balance."
            if lang == "en"
            else "تم إلغاء طلب الإجازة. لم يتم إجراء أي تغيير على رصيدك."
        )
        return {
            "final_answer": cancel_msg,
            "answer_status": AnswerStatus.ACTION_REJECTED.value,
            "action_payload": {"action_type": "LEAVE_CANCELLED_BY_USER"},
            "citations": [],
        }

    # Step G: Confirmed! Submit Request as Pending to Manager
    try:
        receipt = commit_leave_request(
            employee_id=employee_id,
            validation=validation,
            reason=draft.reason,
        )

        if lang == "ar":
            success_msg = (
                f"✅ **تم إرسال طلب الإجازة بنجاح وهو بانتظار اعتماد المدير!**\n\n"
                f"• **رقم الطلب:** #{receipt['request_id']}\n"
                f"• **نوع الإجازة:** {receipt['leave_type']}\n"
                f"• **الفترة:** من {receipt['start_date']} إلى {receipt['end_date']} ({receipt['days_requested']} أيام عمل)\n"
                f"• **الحالة:** قيد المراجعة والاعتماد ({receipt['status']})\n"
                f"• **المدير المباشر:** {receipt['approver_name']}\n"
                f"• **الرصيد المتبقي الحالي:** {receipt['current_balance']} يوم\n\n"
                f"تم إرسال طلب اعتماد رسمي إلى مديرك المباشر. فور اعتماده، سيصلك إشعار لتسجيل الإجازة بالتقويم ومراسلة الموارد البشرية."
            )
        else:
            success_msg = (
                f"✅ **Leave Request Submitted & Awaiting Manager Approval!**\n\n"
                f"• **Request ID:** #{receipt['request_id']}\n"
                f"• **Leave Type:** {receipt['leave_type']}\n"
                f"• **Dates:** {receipt['start_date']} to {receipt['end_date']} ({receipt['days_requested']} working days)\n"
                f"• **Status:** Pending Approval\n"
                f"• **Approver:** {receipt['approver_name']} (Line Manager)\n"
                f"• **Current Balance:** {receipt['current_balance']} days (will become {receipt['projected_balance']} upon approval)\n\n"
                f"Your request has been forwarded to your line manager for review. Once approved, you will be notified and can download your calendar invite (.ics) or notify HR."
            )

        return {
            "final_answer": success_msg,
            "answer_status": AnswerStatus.ACTION_EXECUTED.value,
            "action_payload": {
                "action_type": "LEAVE_SUBMITTED_PENDING_APPROVAL",
                "receipt": receipt,
            },
            "citations": [
                {
                    "source": "omni_hr.db / leave_requests",
                    "table_name": "leave_requests",
                    "section": f"Request #{receipt['request_id']}",
                    "score": 1.0,
                    "language": lang,
                    "snippet": f"Created pending request #{receipt['request_id']} for {receipt['approver_name']} approval.",
                }
            ],
        }
    except Exception as exc:
        logger.error(f"Error submitting leave request: {exc}", exc_info=True)
        return {
            "final_answer": f"An error occurred while submitting your leave request: {str(exc)}",
            "answer_status": AnswerStatus.SAFE_FALLBACK.value,
            "citations": [],
        }


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

            if len(pending_approvals) == 1:
                c_name = pending_approvals[0]["employee_name"]
                header = (
                    f"Yes, **{c_name}** asked for a leave request:\n"
                    if lang == "en"
                    else f"نعم، طلب **{c_name}** إجازة بانتظار اعتمادك:\n"
                )
            else:
                c_names = ", ".join(list(dict.fromkeys(pa["employee_name"] for pa in pending_approvals)))
                header = (
                    f"Yes, your juniors ({c_names}) asked for leave requests:\n"
                    if lang == "en"
                    else f"نعم، طلب موظفوك ({c_names}) إجازة بانتظار اعتمادك:\n"
                )

            lines = [header]
            for pa in pending_approvals:
                lines.append(
                    f"• **Request #{pa['request_id']}** by **{pa['employee_name']}** ({pa['employee_role']}): "
                    f"{pa['days_requested']} days of {pa['leave_type']} from {pa['start_date']} to {pa['end_date']}"
                )
            lines.append("\nYou can review and click **Approve Leave** or **Reject** on the card below, or state the request ID.")
            return {
                "final_answer": "\n".join(lines),
                "answer_status": AnswerStatus.VERIFIED.value,
                "action_payload": {
                    "action_type": "MANAGER_PENDING_APPROVALS",
                    "pending_approvals": pending_approvals,
                },
                "citations": [],
            }

    # Extract target request ID if stated, or look for direct report name
    id_match = re.search(r"#?\b(\d+)\b", question)
    target_id = None
    if id_match:
        target_id = int(id_match.group(1))
    elif pending_approvals:
        for pa in pending_approvals:
            emp_first_name = pa["employee_name"].split()[0].lower()
            if emp_first_name in question.lower():
                target_id = pa["request_id"]
                break
        if not target_id and len(pending_approvals) == 1:
            target_id = pending_approvals[0]["request_id"]

    if not target_id:
        lines = ["📋 **Pending Leave Requests Awaiting Your Approval:**\n"]
        for pa in pending_approvals:
            lines.append(
                f"• **Request #{pa['request_id']}** by **{pa['employee_name']}** ({pa['employee_role']}): "
                f"{pa['days_requested']} days of {pa['leave_type']} from {pa['start_date']} to {pa['end_date']}"
            )
        lines.append("\nPlease state which request ID you want to approve or reject (e.g. 'Approve request #19').")
        return {
            "final_answer": "\n".join(lines),
            "answer_status": AnswerStatus.VERIFIED.value,
            "action_payload": {
                "action_type": "MANAGER_PENDING_APPROVALS",
                "pending_approvals": pending_approvals,
            },
            "citations": [],
        }

    if intent == QuestionIntent.REJECT_LEAVE or re.search(r"\b(reject|decline)\b", question, re.I):
        res = reject_leave_request(manager_id=manager_id, request_id=target_id)
        if not res.get("success"):
            return {
                "final_answer": res.get("message", "Unable to reject request."),
                "answer_status": AnswerStatus.SAFE_FALLBACK.value,
                "citations": [],
            }
        ans = (
            f"❌ **Leave Request #{target_id} has been Rejected.**\n\n"
            f"Request from **{res['employee_name']}** for {res['days_requested']} days of {res['leave_type']} "
            f"has been marked as Rejected. The employee has been notified."
        )
        return {
            "final_answer": ans,
            "answer_status": AnswerStatus.ACTION_EXECUTED.value,
            "action_payload": {"action_type": "MANAGER_REJECTED_SUCCESS", "result": res},
            "citations": [],
        }

    # Only approve if explicit approve command is present and NOT an inquiry!
    if is_action_command and (intent == QuestionIntent.APPROVE_LEAVE or re.search(r"\b(approve|accept)\b", question, re.I)):
        res = approve_leave_request(manager_id=manager_id, request_id=target_id)
        if not res.get("success"):
            return {
                "final_answer": res.get("message", "Unable to approve request."),
                "answer_status": AnswerStatus.SAFE_FALLBACK.value,
                "citations": [],
            }

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

    # Otherwise, NEVER auto-approve; display the pending approvals card!
    lines = ["📋 **Pending Leave Requests Awaiting Your Approval:**\n"]
    for pa in pending_approvals:
        lines.append(
            f"• **Request #{pa['request_id']}** by **{pa['employee_name']}** ({pa['employee_role']}): "
            f"{pa['days_requested']} days of {pa['leave_type']} from {pa['start_date']} to {pa['end_date']}"
        )
    lines.append("\nYou can review and click **Approve Leave** or **Reject** on the card below, or state the request ID.")
    return {
        "final_answer": "\n".join(lines),
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
                "employee_name": emp.name if emp else employee_id,
                "manager_email": emp.manager_email if emp else "manager@hcservices.ae",
                "status": "Approved",
            }

            if lang == "ar":
                lines.append(
                    f"🎉 **نعم! تم اعتماد طلب إجازتك!**\n\n"
                    f"تم اعتماد إجازتك ({latest_request.leave_type}) من **{latest_request.start_date}** إلى **{latest_request.end_date}** "
                    f"({latest_request.days_requested} أيام عمل) بواسطة مديرك المباشر **{latest_request.approver_name}**.\n\n"
                    f"هل ترغب في إضافتها إلى تقويمك أو إرسال بريد إلكتروني للمدير والموارد البشرية عبر الأزرار أدناه؟\n"
                )
            else:
                lines.append(
                    f"🎉 **Yes! Your Leave Request has been Approved!**\n\n"
                    f"Your {latest_request.leave_type} from **{latest_request.start_date}** to **{latest_request.end_date}** "
                    f"({latest_request.days_requested} working days) was approved by your manager, **{latest_request.approver_name}**.\n\n"
                    f"Would you like to mark this on your calendar or email your manager & HR in CC?\n"
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
                    f"❌ **طلب إجازتك #{latest_request.id} تم رفضه:**\n\n"
                    f"طلبك لـ {latest_request.leave_type} تم رفضه من قبل **{latest_request.approver_name}**."
                )
            else:
                lines.append(
                    f"❌ **Your Leave Request #{latest_request.id} was Rejected:**\n\n"
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
                        f"• **طلب #{req['id']} ({req['leave_type']}):** من {req['start_date']} إلى {req['end_date']} "
                        f"({req['days_requested']} أيام) — قيد المراجعة بواسطة {req['approver_name']}"
                    )
            else:
                lines.append("\n📋 **Other Pending Leave Requests:**\n")
                for req in other_pending:
                    lines.append(
                        f"• **Request #{req['id']} ({req['leave_type']}):** {req['start_date']} to {req['end_date']} "
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
            "citations": [
                {
                    "source": "omni_hr.db / leave_requests",
                    "table_name": "leave_requests",
                    "section": "Leave Status Tracking",
                    "score": 1.0,
                    "language": lang,
                    "snippet": "Retrieved latest leave records.",
                }
            ],
        }
    finally:
        session.close()


def handle_leave_cancellation(state: ConversationState) -> dict:
    """Handle cancel_leave intent: cancels pending leave and restores balance."""
    employee_id = state["employee_id"]
    question = state["employee_question"]
    lang = state.get("requested_language", "en")

    # Extract request ID if mentioned, e.g. "cancel leave #3" or "cancel request 3"
    id_match = re.search(r"#?\b(\d+)\b", question)
    pending = get_pending_leave_requests(employee_id)

    target_id = None
    if id_match:
        target_id = int(id_match.group(1))
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
            options = ", ".join(f"#{r['id']} ({r['leave_type']} {r['start_date']})" for r in pending)
            msg = (
                f"Please specify which leave request ID to cancel. Your pending requests: {options}"
                if lang == "en"
                else f"يرجى تحديد رقم طلب الإجازة المراد إلغاؤه. طلباتك المعلقة: {options}"
            )
        return {
            "final_answer": msg,
            "answer_status": AnswerStatus.VERIFIED.value,
            "citations": [],
        }

    res = cancel_leave_request(employee_id=employee_id, request_id=target_id)
    if not res.get("success"):
        return {
            "final_answer": res.get("message", "Unable to cancel request."),
            "answer_status": AnswerStatus.SAFE_FALLBACK.value,
            "citations": [],
        }

    if lang == "ar":
        ans = (
            f"✅ **تم إلغاء طلب الإجازة #{target_id} بنجاح!**\n\n"
            f"تم تحديث حالة الطلب إلى ملغي."
        )
    else:
        ans = (
            f"✅ **Leave Request #{target_id} has been cancelled!**\n\n"
            f"The request has been removed from pending approvals."
        )

    return {
        "final_answer": ans,
        "answer_status": AnswerStatus.ACTION_EXECUTED.value,
        "citations": [
            {
                "source": "omni_hr.db / leave_requests",
                "table_name": "leave_requests",
                "section": f"Cancelled Request #{target_id}",
                "score": 1.0,
                "language": lang,
                "snippet": f"Cancelled #{target_id}.",
            }
        ],
    }
