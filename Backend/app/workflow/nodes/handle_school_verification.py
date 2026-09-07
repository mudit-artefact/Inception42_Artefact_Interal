"""
Proof of schooling and the education allowance, answered from the employee's own plan.

This used to be a paragraph typed into the code and returned to everyone who asked. It
stated "up to AED 45,000 per eligible child" and "ages 4 and 18", marked itself verified,
and attached no source.

AED 45,000 is real — it is the ceiling on the Enhanced plan — but six of the twelve seeded
employees are on Standard at AED 25,000 and one has no education plan at all, so seven of
the twelve were told a number that was not theirs. The age band was not real at all: there
is no age rule in the plan data and no education policy in the document set.

The figures now come from the employee's own plan row, and they travel in the payload as
well as the sentence, so the check that holds every quantity against its evidence has
something to hold them against.
"""

import logging
from typing import Any, Dict

from app.domain.enums import AnswerStatus
from app.workflow.conversation_state import ConversationState
from app.workflow.tools import run_tool

logger = logging.getLogger(__name__)


def handle_school_verification(state: ConversationState) -> Dict[str, Any]:
    """Tell the employee what their own plan covers, or that they are on none."""
    lang = state.get("requested_language", "en")
    employee_id = state["employee_id"]

    outcome = run_tool("get_education_entitlement", employee_id=employee_id)

    if not outcome.ok:
        return {
            "final_answer": (
                "لم أتمكن من قراءة خطة التعليم الخاصة بك الآن. يرجى التواصل مع قسم شؤون الموظفين."
                if lang == "ar"
                else "I could not read your education plan just now. Please contact "
                "People & Culture."
            ),
            "answer_status": AnswerStatus.SAFE_FALLBACK.value,
            "citations": [],
        }

    entitlement = outcome.result

    if not entitlement.get("entitled"):
        logger.info(f"{employee_id} is on no education plan")
        return {
            "final_answer": (
                "### 🎓 بدل التعليم\n\n"
                "لا يوجد بدل تعليم مدرج ضمن باقة مزاياك الحالية. "
                "إذا كنت تعتقد أن هذا غير صحيح، يرجى التواصل مع قسم شؤون الموظفين."
                if lang == "ar"
                else "### 🎓 Education Allowance\n\n"
                "There is no education allowance on your current benefits package. "
                "If you believe that is wrong, please contact People & Culture."
            ),
            "answer_status": AnswerStatus.VERIFIED.value,
            "action_payload": {
                "action_type": "EDUCATION_ENTITLEMENT",
                "entitlement": entitlement,
            },
            "citations": [],
        }

    documents = entitlement["required_documents"]
    documents_line = "\n".join(f"* {document}" for document in documents)
    limit = entitlement["annual_limit_aed"]

    if lang == "ar":
        answer = (
            "### 🎓 إثبات الدراسة وبدل التعليم\n\n"
            f"**خطتك:** {entitlement['plan_name']}\n\n"
            f"**الحد السنوي:** {limit} درهم لكل طفل مؤهل\n\n"
            f"**السنة الدراسية:** من {entitlement['academic_year_start']} "
            f"إلى {entitlement['academic_year_end']}\n\n"
            "**المستندات المطلوبة:**\n"
            f"{documents_line}\n\n"
            "لتقديم المستندات أو الاستفسار، يرجى التواصل مع قسم شؤون الموظفين."
        )
    else:
        answer = (
            "### 🎓 Proof of Schooling & Education Allowance\n\n"
            f"**Your plan:** {entitlement['plan_name']}\n\n"
            f"**Annual limit:** {limit} AED per eligible child\n\n"
            f"**Academic year:** {entitlement['academic_year_start']} to "
            f"{entitlement['academic_year_end']}\n\n"
            "**Documents required:**\n"
            f"{documents_line}\n\n"
            "To submit documents or ask about a claim, contact People & Culture."
        )

    return {
        "final_answer": answer,
        "answer_status": AnswerStatus.VERIFIED.value,
        "action_payload": {
            "action_type": "EDUCATION_ENTITLEMENT",
            "entitlement": entitlement,
        },
        "citations": [],
    }
