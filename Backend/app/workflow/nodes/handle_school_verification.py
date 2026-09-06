"""
School Verification & Education Allowance Guidance:
Provides policy-grounded guidance for proof of schooling and education allowance.
"""

import logging
from typing import Any, Dict

from app.domain.enums import AnswerStatus
from app.workflow.conversation_state import ConversationState

logger = logging.getLogger(__name__)


def handle_school_verification(state: ConversationState) -> Dict[str, Any]:
    """
    Provide guidance on Proof of Schooling and Education Allowance policy.
    """
    lang = state.get("requested_language", "en")

    if lang == "ar":
        msg = (
            "### 🎓 إثبات الدراسة وبدل التعليم (2026–2027)\n\n"
            "للحصول على بدل التعليم أو التحقق من إثبات قيد الأبناء:\n\n"
            "* **الفئة العمرية المستحقة**: الأبناء المعالون بين 4 و18 سنة المسجلون رسمياً في المدارس المعتمدة.\n"
            "* **الحد الأقصى للبدل**: حتى 45,000 درهم إماراتي لكل طفل مؤهل وفق سياسة الشركة.\n"
            "* **المستندات المطلوبة**: شهادة قيد دراسي رسمية حديثة معتمدة من المدرسة + فاتورة الرسوم الدراسية / إيصال الدفع.\n\n"
            "لتقديم الطلبات أو الاستفسار عن المعاملات، يرجى التواصل مع قسم شؤون الموظفين (People & Culture)."
        )
    else:
        msg = (
            "### 🎓 Proof of Schooling & Education Allowance (2026–2027)\n\n"
            "Here is the overview for education allowance claims and schooling verification:\n\n"
            "* **Eligibility**: Registered dependent children between ages 4 and 18 enrolled in recognized schools.\n"
            "* **Allowance Limit**: Up to AED 45,000 per eligible child per academic year per company policy.\n"
            "* **Required Documents**: Official school enrollment certificate on school letterhead (stamped & signed) along with the tuition invoice or payment receipt.\n\n"
            "For active submissions or inquiries, please contact the People & Culture team."
        )

    return {
        "final_answer": msg,
        "citations": [],
        "answer_status": AnswerStatus.VERIFIED.value,
    }

