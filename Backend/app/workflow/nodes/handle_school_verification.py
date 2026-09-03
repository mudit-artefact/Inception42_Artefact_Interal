"""
HCS-11 School Verification Action Node: Handles proof of schooling inquiries,
education allowance status, document submissions, and reviewer queues.
"""

from datetime import date
import logging
import re
from typing import Any, Dict, List, Optional

from app.domain.enums import AnswerStatus, QuestionIntent
from app.services.hcs11_client import hcs11_client
from app.workflow.conversation_state import ConversationState

logger = logging.getLogger(__name__)

# Mapping from HCS-01 employee IDs or names to HCS-11 synthetic employee IDs
HCS01_TO_HCS11_EMP_MAP = {
    "EMP001": "E0001",  # Ahmed mapped to Layla Haddad's dependents (Rami, Maya)
    "EMP002": "E0001",  # Fatima mapped to Layla Haddad's dependents (Rami, Maya)
    "EMP003": "E0002",  # Aisha mapped to Omar Nasser's dependents (Sara, Ziad)
    "EMP004": "E0003",  # Sultan mapped to Mariam Saeed's dependents (Yousef, Dana)
    "EMP005": "E0003",  # Maryam mapped to Mariam Saeed's dependents (Yousef, Dana)
    "EMP007": "E0007",  # Faisal Hamdan (Hana)
}

CHILD_TO_EMP_MAP = {
    "rami": "E0001",
    "maya": "E0001",
    "sara": "E0002",
    "ziad": "E0002",
    "yousef": "E0003",
    "dana": "E0003",
    "hana": "E0007",
    "hanaa": "E0007",
}


def _resolve_hcs11_employee_id(state: ConversationState) -> str:
    """Resolve HCS-11 employee ID from question context or active employee."""
    question = (state.get("employee_question") or "").lower()
    for child_name, emp_id in CHILD_TO_EMP_MAP.items():
        if re.search(rf"\b{child_name}\b", question):
            return emp_id

    active_id = state.get("employee_id", "EMP001")
    if active_id in HCS01_TO_HCS11_EMP_MAP:
        return HCS01_TO_HCS11_EMP_MAP[active_id]
    if active_id.startswith("E00"):
        return active_id
    return "E0001"


def handle_school_verification(state: ConversationState) -> Dict[str, Any]:
    """
    Process HCS-11 school verification inquiries, allowances, and submissions.
    """
    intent = state.get("question_intent")
    question = state.get("employee_question", "")
    lang = state.get("requested_language", "en")
    hcs11_emp_id = _resolve_hcs11_employee_id(state)

    # 1. Reviewer Queue Intent
    if intent == QuestionIntent.REVIEW_SCHOOL_CASES.value or re.search(
        r"\b(review|pending|cases?)\s+(school|education|allowance)\b", question.lower()
    ):
        return _handle_school_review_queue(state, lang)

    # 2. Document Submission Intent
    if intent == QuestionIntent.SUBMIT_SCHOOL_VERIFICATION.value or re.search(
        r"\b(submit|upload|send)\s+(school|proof|certificate|letter)\b", question.lower()
    ):
        return _handle_school_submission_intent(state, hcs11_emp_id, lang)

    # 3. Default: Status & Allowance Inquiry
    return _handle_school_status_inquiry(state, hcs11_emp_id, lang)


def _handle_school_status_inquiry(
    state: ConversationState, employee_id: str, lang: str
) -> Dict[str, Any]:
    """Inquire about current verification cases, approval status, and allowance."""
    cases = hcs11_client.list_cases(employee_id=employee_id)
    dependents = hcs11_client.get_dependents(employee_id=employee_id)

    if not cases and not dependents:
        msg = (
            "I could not locate any active school verification cases or eligible dependents "
            "for your profile in the current 2026–2027 academic cycle.\n\n"
            "If you have school-aged children, please ensure they are registered under your HR dependent records."
            if lang == "en"
            else "لم أتمكن من العثور على حالات تحقق دراسي نشطة أو معالين مسجلين لملفك في الدورة الدراسية الحالية 2026–2027."
        )
        return {
            "final_answer": msg,
            "citations": [],
            "answer_status": AnswerStatus.VERIFIED.value,
        }

    # Format natural language status response
    lines = []
    if lang == "ar":
        lines.append("### 🎓 حالة التحقق من إثبات الدراسة وبدل التعليم (2026–2027):")
    else:
        lines.append("### 🎓 School Verification & Education Allowance Status (2026–2027):")

    lines.append("")

    for c in cases:
        child_name = c.get("child_name") or f"Dependent {c.get('dependent_id')}"
        status = c.get("case_status", "Awaiting Submission")
        approved_aed = c.get("approved_amount_aed")
        deadline = c.get("submission_deadline", "2026-10-15")

        if status == "Approved":
            amount_str = f"{approved_aed:,} AED" if approved_aed else "45,000 AED"
            lines.append(
                f"* ✅ **{child_name}**: **Approved** ({amount_str} ready for payroll). "
                f"Document verified and complies with HCS-11 plan guidelines."
            )
        elif status == "Under Review":
            route = c.get("route") or "Reviewer Queue"
            recom = c.get("recommendation") or "Pending HR review"
            lines.append(
                f"* ⏳ **{child_name}**: **Under Review** ({route}). "
                f"Document is flagged for human reviewer: *{recom}*."
            )
        else:
            lines.append(
                f"* 📋 **{child_name}**: **Awaiting Submission** (Deadline: {deadline}). "
                f"Please upload an official school enrollment letter for this academic year."
            )

    lines.append("")
    if any(c.get("case_status") != "Approved" for c in cases):
        lines.append(
            "💡 *Tip: You can submit your school certificate directly by typing 'Upload school document for Rami' or clicking the upload action below.*"
        )

    return {
        "final_answer": "\n".join(lines),
        "citations": [
            {
                "id": "hcs11-policy-01",
                "title": "HCS-11 Education Allowance Policy",
                "source": "HC-PC-011 Proof of Schooling Guidelines",
                "source_type": "policy",
                "section": "Section 3 — Annual Verification & Allowance Cap",
                "score": 0.98,
                "snippet": "Annual proof of schooling is required for eligible dependents between ages 4 and 18. Maximum allowance is 45,000 AED per child.",
                "url": "#",
            }
        ],
        "answer_status": AnswerStatus.VERIFIED.value,
        "action_payload": {
            "action_type": "SCHOOL_VERIFICATION_STATUS",
            "employee_id": employee_id,
            "cases": cases,
            "dependents": dependents,
        },
    }


def _handle_school_submission_intent(
    state: ConversationState, employee_id: str, lang: str
) -> Dict[str, Any]:
    """Guide the employee on submitting a school proof letter."""
    dependents = hcs11_client.get_dependents(employee_id=employee_id)
    cases = hcs11_client.list_cases(employee_id=employee_id)

    children_names = [d["full_name"] for d in dependents if d.get("relationship") == "Child"]
    children_str = ", ".join(children_names) if children_names else "your eligible children"

    msg = (
        f"### 📤 Submit Proof of Schooling (Academic Cycle 2026–2027)\n\n"
        f"You can submit proof of schooling for **{children_str}**.\n\n"
        f"**Document Requirements:**\n"
        f"* Must be an official enrollment letter on school letterhead for the 2026–2027 academic year.\n"
        f"* Must contain student name, date of birth, and official signature/stamp.\n"
        f"* Accepted file formats: PDF, PNG, or JPEG (up to 10 MB).\n\n"
        f"Please select the child or upload the certificate below:"
    )

    return {
        "final_answer": msg,
        "citations": [],
        "answer_status": AnswerStatus.VERIFIED.value,
        "action_payload": {
            "action_type": "SCHOOL_DOCUMENT_SUBMISSION",
            "employee_id": employee_id,
            "dependents": dependents,
            "cases": cases,
        },
    }


def _handle_school_review_queue(state: ConversationState, lang: str) -> Dict[str, Any]:
    """Retrieve and display cases awaiting human reviewer decisions."""
    cases = hcs11_client.list_cases(status="Under Review")

    if not cases:
        return {
            "final_answer": "🎉 **No School Verification Cases Pending Review!** All submitted claims have been processed or approved.",
            "citations": [],
            "answer_status": AnswerStatus.VERIFIED.value,
        }

    lines = [
        f"### 📋 School Verification Cases Awaiting Review ({len(cases)} cases):\n"
    ]
    for c in cases[:5]:
        child = c.get("child_name") or c.get("dependent_id")
        recom = c.get("recommendation") or "Review required"
        lines.append(f"* **Case #{c.get('case_id')}** ({child}): {recom}")

    return {
        "final_answer": "\n".join(lines),
        "citations": [],
        "answer_status": AnswerStatus.VERIFIED.value,
        "action_payload": {
            "action_type": "SCHOOL_REVIEW_QUEUE",
            "pending_count": len(cases),
            "cases": cases,
        },
    }
