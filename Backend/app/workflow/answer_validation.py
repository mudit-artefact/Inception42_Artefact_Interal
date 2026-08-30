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
    declared_calculations: list[dict] | None = None,
    employee_question: str = "",
) -> ValidationOutcome:
    """Run every check. The first failure decides the outcome."""
    for check in (
        lambda: check_evidence_is_present(has_any_evidence),
        lambda: check_every_quantity_is_grounded(
            answer, evidence_text, declared_calculations or [], employee_question
        ),
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


def check_every_quantity_is_grounded(
    answer: str,
    evidence_text: str,
    declared_calculations: list[dict],
    employee_question: str = "",
) -> ValidationOutcome:
    """
    Every quantity in the answer is either quoted from the evidence or worked out from it.

    Only numbers carrying a unit are checked — days, months, hours, dirhams, percentages —
    so ordinary prose and list numbering are left alone.

    This used to demand that every figure appear in the evidence verbatim, which sounds
    like grounding and is really a ban on arithmetic. "You have 15 days left, so taking 15
    would leave 0" was rejected because no document prints a zero, and the employee was
    told the assistant could not confirm it. Correct answers were being discarded; not one
    invented figure was ever caught that this does not also catch.

    A figure now passes if the assistant declared how it got there and every input to that
    sum is in the evidence. An invented figure has no inputs to point at and still fails.
    The sum itself is taken on trust — a deliberate choice, and the place to add a
    recomputation if one is ever wanted.
    """
    evidence_numbers = _numbers_in(evidence_text)
    supposed_numbers = _numbers_in(employee_question)
    derived_numbers, premises_used = _figures_worked_out_from(
        declared_calculations, evidence_numbers, supposed_numbers
    )
    grounded = evidence_numbers | derived_numbers | premises_used

    unsupported_claims = [
        matched_quantity.group(0).strip()
        for matched_quantity in QUANTITY_PATTERN.finditer(_normalise_digits(answer))
        if _normalise_number(matched_quantity.group(1)) not in grounded
    ]

    if not unsupported_claims:
        return ValidationOutcome(is_valid=True)
    return ValidationOutcome(
        is_valid=False,
        reason=(
            "the answer states figures that are neither in the evidence nor worked out "
            "from it"
        ),
        unsupported_claims=unsupported_claims,
    )


def _figures_worked_out_from(
    declared_calculations: list[dict],
    evidence_numbers: set[str],
    supposed_numbers: set[str],
) -> tuple[set[str], set[str]]:
    """
    The results of the sums the assistant declared, keeping only the honest ones, and the
    figures the employee supposed that those sums were entitled to quote back.

    A calculation counts when every input is either in the evidence or in the question the
    employee just asked, AND at least one input is in the evidence. That last condition is
    what keeps the guarantee: a sum built only out of numbers the employee typed proves
    nothing, and is exactly how "can I carry over 25 days?" could be answered "yes, 25
    days" before any of this existed.

    The second half of the return is the reason this needed changing. An employee who asks
    "if I am off sick for 40 days, what happens?" is owed an answer that says 40 — the
    number is the premise of their own question. Demanding that 40 appear in a policy
    document threw away a correct answer and told them nothing could be confirmed. So a
    supposed figure becomes quotable, but only once it has been used as an input to a
    calculation that is itself anchored in the evidence.
    """
    worked_out: set[str] = set()
    premises_used: set[str] = set()

    for calculation in declared_calculations:
        inputs = [_normalise_number(str(number))
                  for number in calculation.get("from_numbers") or []]
        supposed = [number for number in inputs if number in supposed_numbers]
        from_evidence = [number for number in inputs if number in evidence_numbers]
        unaccounted = [number for number in inputs
                       if number not in evidence_numbers and number not in supposed_numbers]

        if not inputs or unaccounted or not from_evidence:
            logger.info(
                f"Ignoring a declared calculation that is not anchored in the evidence: "
                f"{calculation.get('how') or calculation}"
            )
            continue

        worked_out.add(_normalise_number(str(calculation.get("result"))))
        premises_used.update(supposed)

    return worked_out, premises_used


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
