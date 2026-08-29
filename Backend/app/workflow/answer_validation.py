"""
Checking a drafted answer before the employee sees it.

Nothing here calls the language model. These are cheap, deterministic checks, so every
answer is checked at no extra cost and with no extra delay.

The check that matters most for this product is the numeric one. An HR assistant that
invents "you may carry over 30 days" is worse than one that declines to answer, and a
fabricated figure is exactly what a fluent model produces when the evidence is thin.
"""

import logging
import re
from dataclasses import dataclass, field

from app.core.language_detection import detect_language

logger = logging.getLogger(__name__)

ARABIC_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

# A number that is being used as a quantity, in either language.
QUANTITY_PATTERN = re.compile(
    r"(\d[\d,]*(?:\.\d+)?)\s*"
    r"(?:working\s+days?|days?|months?|weeks?|hours?|AED|dirhams?|%|percent"
    r"|أيام|يوم|يوماً|أشهر|شهر|ساعات|ساعة|درهم|بالمائة|٪)",
    re.IGNORECASE,
)

EMPLOYEE_IDENTIFIER_PATTERN = re.compile(r"\bEMP\d{3,}\b", re.IGNORECASE)

COMPANY_EMAIL_DOMAIN = "hcservices.ae"
EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@([\w.-]+\.\w+)\b")


@dataclass
class ValidationOutcome:
    """Whether an answer may be shown, and why not when it may not."""

    is_valid: bool
    reason: str = ""
    unsupported_claims: list[str] = field(default_factory=list)


def validate_answer(
    answer: str,
    evidence_text: str,
    employee_id: str,
    requested_language: str,
    has_any_evidence: bool,
) -> ValidationOutcome:
    """Run every check. The first failure decides the outcome."""
    for check in (
        lambda: check_evidence_is_present(has_any_evidence),
        lambda: check_every_quantity_appears_in_the_evidence(answer, evidence_text),
        lambda: check_no_other_employee_is_named(answer, employee_id),
        lambda: check_the_answer_is_in_the_requested_language(answer, requested_language),
    ):
        outcome = check()
        if not outcome.is_valid:
            logger.info(f"The drafted answer was rejected: {outcome.reason}")
            return outcome

    return ValidationOutcome(is_valid=True)


def check_evidence_is_present(has_any_evidence: bool) -> ValidationOutcome:
    """An answer with nothing behind it cannot be grounded, however fluent it reads."""
    if has_any_evidence:
        return ValidationOutcome(is_valid=True)
    return ValidationOutcome(
        is_valid=False, reason="no policy extract or employee fact was retrieved"
    )


def check_every_quantity_appears_in_the_evidence(
    answer: str, evidence_text: str
) -> ValidationOutcome:
    """
    Every number the answer states as a quantity must appear in the evidence.

    Only numbers carrying a unit are checked — days, months, hours, dirhams, percentages —
    so ordinary prose and list numbering are left alone.
    """
    evidence_numbers = _numbers_in(evidence_text)
    unsupported_claims = [
        matched_quantity.group(0).strip()
        for matched_quantity in QUANTITY_PATTERN.finditer(_normalise_digits(answer))
        if _normalise_number(matched_quantity.group(1)) not in evidence_numbers
    ]

    if not unsupported_claims:
        return ValidationOutcome(is_valid=True)
    return ValidationOutcome(
        is_valid=False,
        reason="the answer states figures that do not appear in the evidence",
        unsupported_claims=unsupported_claims,
    )


def check_no_other_employee_is_named(answer: str, employee_id: str) -> ValidationOutcome:
    """An answer must never carry another person's record or an outside email address."""
    other_identifiers = {
        found.upper()
        for found in EMPLOYEE_IDENTIFIER_PATTERN.findall(answer)
        if found.upper() != employee_id.upper()
    }
    if other_identifiers:
        return ValidationOutcome(
            is_valid=False,
            reason="the answer refers to another employee's record",
            unsupported_claims=sorted(other_identifiers),
        )

    outside_domains = {
        domain
        for domain in EMAIL_PATTERN.findall(answer)
        if not domain.lower().endswith(COMPANY_EMAIL_DOMAIN)
    }
    if outside_domains:
        return ValidationOutcome(
            is_valid=False,
            reason="the answer contains an email address outside the company",
            unsupported_claims=sorted(outside_domains),
        )

    return ValidationOutcome(is_valid=True)


def check_the_answer_is_in_the_requested_language(
    answer: str, requested_language: str
) -> ValidationOutcome:
    """An Arabic question must not be answered in English, or the reverse."""
    if not answer.strip():
        return ValidationOutcome(is_valid=False, reason="the answer is empty")
    if detect_language(answer) == requested_language:
        return ValidationOutcome(is_valid=True)
    return ValidationOutcome(
        is_valid=False,
        reason=f"the answer is not written in the requested language ({requested_language})",
    )


def _normalise_digits(text: str) -> str:
    return text.translate(ARABIC_INDIC_DIGITS)


def _normalise_number(number_text: str) -> str:
    """Compare 3,000 and 3000 and 3000.0 as the same figure."""
    cleaned = number_text.replace(",", "")
    try:
        return f"{float(cleaned):g}"
    except ValueError:
        return cleaned


def _numbers_in(text: str) -> set[str]:
    return {
        _normalise_number(number)
        for number in re.findall(r"\d[\d,]*(?:\.\d+)?", _normalise_digits(text))
    }
