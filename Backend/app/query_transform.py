"""
app/query_transform.py — Query Understanding, Intent Classification & Acronym Expansion
"""

import re
from typing import Dict, List, Tuple
from pydantic import BaseModel


class QueryTransformationResult(BaseModel):
    original_query: str
    rewritten_query: str
    intent: str
    acronyms_expanded: List[str]
    target_language: str
    is_greeting: bool
    is_out_of_domain: bool
    confidence_score: float


# Comprehensive HR domain abbreviations
HR_ACRONYMS: Dict[str, str] = {
    r"\bAL\b": "Annual Leave",
    r"\bSL\b": "Sick Leave",
    r"\bWFH\b": "Work From Home (Remote Work)",
    r"\bWFA\b": "Work From Anywhere",
    r"\bPIP\b": "Performance Improvement Plan (Probation Review)",
    r"\bEOSB\b": "End of Service Benefits (Gratuity)",
    r"\bEOB\b": "End of Service Benefits",
    r"\bGRT\b": "Gratuity Entitlement",
    r"\bHRBP\b": "HR Business Partner",
    r"\bDHA\b": "Dubai Health Authority",
    r"\bDOH\b": "Department of Health Abu Dhabi",
    r"\bMOH\b": "Ministry of Health",
    r"\bLM\b": "Line Manager",
    r"\bTL\b": "Team Lead",
    r"\bLTI\b": "Long Term Illness (Sick Leave)",
    r"\bPTO\b": "Paid Time Off (Annual Leave)",
    r"\bFWA\b": "Flexible Working Arrangement",
}

GREETING_PATTERNS = [
    r"^(hi|hello|hey|greetings|good\s+(morning|afternoon|evening)|start|howdy|welcome)\b",
    r"^(مرحبا|أهلا|اهلا|السلام عليكم|صباح الخير|مساء الخير|مرحباً|هلا)\b",
]

OUT_OF_DOMAIN_PATTERNS = [
    r"\b(python|javascript|code|script|sql injection|recipe|bake|cake|weather|crypto|bitcoin|movie|song|guitar|president|election)\b",
    r"\b(برمجة|كود|طبخ|وصفة|طقس|بيتكوين|أغنية|فيلم|سياسة|انتخابات)\b",
]

MANAGER_PATTERNS = [
    r"\b(manager|lead|supervisor|boss|reporting|line manager|who is my manager)\b",
    r"\b(مدير|مديري|المسؤول|المدير المباشر|من هو مديري)\b",
]

LEAVE_PATTERNS = [
    r"\b(leave|vacation|holiday|annual leave|sick leave|carry over|balance|days off|time off)\b",
    r"\b(إجازة|اجازة|إجازات|رصيد|مرضي|سنوي|متبقي|أيام)\b",
]

EXPENSE_PATTERNS = [
    r"\b(expense|claim|reimbursement|receipt|travel allowance|meal|per diem|aed|cost)\b",
    r"\b(مصروفات|نفقات|استرداد|فاتورة|بدل سفر|درهم|تعويض)\b",
]


class QueryTransformer:
    """Pre-retrieval query intelligence and expansion pipeline."""

    @staticmethod
    def detect_language(text: str) -> str:
        arabic_chars = len(re.findall(r"[\u0600-\u06FF]", text))
        total_chars = len(re.findall(r"\w", text)) or 1
        return "ar" if (arabic_chars / total_chars) > 0.3 else "en"

    @classmethod
    def transform(cls, query: str, user_target_lang: str = "en") -> QueryTransformationResult:
        trimmed = query.strip()
        lang = cls.detect_language(trimmed) or user_target_lang

        # 1. Detect Greeting Intent
        is_greeting = any(re.search(pat, trimmed, re.IGNORECASE) for pat in GREETING_PATTERNS)
        if is_greeting and len(trimmed.split()) <= 4:
            return QueryTransformationResult(
                original_query=query,
                rewritten_query=trimmed,
                intent="greeting_onboarding",
                acronyms_expanded=[],
                target_language=lang,
                is_greeting=True,
                is_out_of_domain=False,
                confidence_score=0.99,
            )

        # 2. Detect Out-of-domain
        is_ood = any(re.search(pat, trimmed, re.IGNORECASE) for pat in OUT_OF_DOMAIN_PATTERNS)
        if is_ood and not any(re.search(p, trimmed, re.IGNORECASE) for p in LEAVE_PATTERNS + MANAGER_PATTERNS):
            return QueryTransformationResult(
                original_query=query,
                rewritten_query=trimmed,
                intent="out_of_domain",
                acronyms_expanded=[],
                target_language=lang,
                is_greeting=False,
                is_out_of_domain=True,
                confidence_score=0.95,
            )

        # 3. Expand HR Acronyms
        rewritten = trimmed
        expanded_list = []
        for pat, expansion in HR_ACRONYMS.items():
            if re.search(pat, rewritten, re.IGNORECASE):
                rewritten = re.sub(pat, f"{expansion}", rewritten, flags=re.IGNORECASE)
                expanded_list.append(expansion)

        # 4. Classify Intent
        if any(re.search(pat, rewritten, re.IGNORECASE) for pat in MANAGER_PATTERNS):
            intent = "manager_inquiry"
            confidence = 0.96
        elif any(re.search(pat, rewritten, re.IGNORECASE) for pat in LEAVE_PATTERNS):
            intent = "leave_inquiry"
            confidence = 0.98
        elif any(re.search(pat, rewritten, re.IGNORECASE) for pat in EXPENSE_PATTERNS):
            intent = "expense_claim"
            confidence = 0.94
        else:
            intent = "policy_inquiry"
            confidence = 0.88

        # 5. Clarify and add domain context if query is very short (e.g. "notice period", "pip")
        if len(rewritten.split()) <= 3 and intent == "leave_inquiry":
            rewritten = f"HC Services policy for {rewritten} entitlement rules and approval notice"
        elif len(rewritten.split()) <= 3 and intent == "policy_inquiry":
            rewritten = f"HC Services HR policy and guidelines for {rewritten}"

        return QueryTransformationResult(
            original_query=query,
            rewritten_query=rewritten,
            intent=intent,
            acronyms_expanded=expanded_list,
            target_language=lang,
            is_greeting=False,
            is_out_of_domain=False,
            confidence_score=confidence,
        )
