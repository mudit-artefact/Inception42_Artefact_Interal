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

# The last two are the Arabic decimal separator and thousands mark. Without them
# "14٫4 يوماً" parsed as the number 4.
ARABIC_INDIC_DIGITS = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩٫٬", "0123456789.,"
)

# What makes a number a quantity rather than list numbering or a section reference.
_UNITS = (
    r"working\s+days?|days?|months?|weeks?|hours?|AED|dirhams?|%|percent"
    r"|أيام|يوم|يوماً|أشهر|شهر|ساعات|ساعة|درهم|بالمائة|٪"
)

# The unit is captured as well as the number, because what a figure may be grounded by
# depends on what it is measuring. See `_is_grounded`.
#
# Two shapes, because a currency is written on whichever side the language puts it. Every
# unit follows its number — "15 days", "45,000 درهم" — except the currency code in
# English, which precedes it: "AED 45,000". That second shape used to be no shape at all,
# so a dirham figure written the way anybody actually writes it in English was not a
# quantity as far as this check was concerned, and was never held against anything.
#
# Groups: 1 number / 2 unit, or 3 currency / 4 number.
QUANTITY_PATTERN = re.compile(
    r"(?:(\d[\d,]*(?:\.\d+)?)\s*(" + _UNITS + r")"
    r"|(AED|dirhams?)\s*(\d[\d,]*(?:\.\d+)?))",
    re.IGNORECASE,
)

# A percentage may stand on the fraction it means, and nothing else may.
PERCENT_UNITS = {"%", "٪", "percent", "بالمائة"}

# Figures a policy writes as words instead of digits. HC-PC-002 §2.2.1 in Arabic sets the
# sick leave window as "فترة اثني عشر شهراً" — a twelve-month period, with no 12 in it — so an
# answer saying "12 شهراً" was quoting the policy and was rejected for inventing.
NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100,
    "اثني عشر": 12, "اثنا عشر": 12, "خمسة عشر": 15,
    "واحد": 1, "واحدة": 1, "اثنين": 2, "اثنان": 2,
    "ثلاثة": 3, "ثلاث": 3, "أربعة": 4, "أربع": 4,
    "خمسة": 5, "خمس": 5, "ستة": 6, "ست": 6,
    "سبعة": 7, "سبع": 7, "ثمانية": 8, "ثماني": 8,
    "تسعة": 9, "تسع": 9, "عشرة": 10, "عشر": 10,
    "عشرين": 20, "العشرين": 20, "ثلاثين": 30, "الثلاثين": 30,
    "أربعين": 40, "الأربعين": 40, "خمسين": 50, "الخمسين": 50,
    "ستين": 60, "الستين": 60, "سبعين": 70, "السبعين": 70,
    "ثمانين": 80, "الثمانين": 80, "تسعين": 90, "التسعين": 90,
    "مائة": 100, "مئة": 100,
}

# Longest first, so "اثني عشر" is read as twelve and not as the ten inside it.
_NUMBER_WORDS_ALTERNATION = "|".join(
    re.escape(word) for word in sorted(NUMBER_WORDS, key=len, reverse=True)
)

# A number word only counts where a unit follows it, exactly as a digit does. That is what
# keeps the "one" in "one of the following" prose, unable to ground a "1 day" in an answer.
SPELLED_QUANTITY_PATTERN = re.compile(
    r"\b(" + _NUMBER_WORDS_ALTERNATION + r")(?!\w)[\s\-‐‑–—]*(?:" + _UNITS + r")",
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
            # The claims, not just the reason. Without them a rejection says an answer
            # was thrown away but never which figure did it, and finding out means
            # replaying the turn against the model.
            offending = f" — {outcome.unsupported_claims}" if outcome.unsupported_claims else ""
            logger.info(f"The drafted answer was rejected: {outcome.reason}{offending}")
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
        if not _is_grounded(
            # Whichever side the number fell on, and the unit it was measuring.
            matched_quantity.group(1) or matched_quantity.group(4),
            matched_quantity.group(2) or matched_quantity.group(3) or "",
            grounded,
        )
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


def _is_grounded(number_text: str, unit: str, grounded: set[str]) -> bool:
    """
    Whether one quantity in the answer stands on something behind it.

    A percentage is allowed to stand on the fraction it means. The record prints "Works
    0.6 of full time" and the sentence anybody would write is "you work 60% of full time"
    — one fact, written the way each side writes it, and rejecting it told a part-time
    employee her own working pattern could not be confirmed.

    Only a percentage may do this. A figure measured in days can never be grounded by a
    fraction, so an invented "you may carry over 30 days" is still caught even with a 0.3
    sitting somewhere in the evidence.
    """
    value = _normalise_number(number_text)
    if value in grounded:
        return True
    if unit.strip().lower() not in PERCENT_UNITS:
        return False
    try:
        return f"{float(value) / 100:g}" in grounded
    except ValueError:
        return False


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


# Text the answer is quoting rather than writing: the employee's own earlier words, a
# policy title, a document name.
QUOTED_SPAN_PATTERN = re.compile(r"[“\"«][^”\"»]*[”\"»]")


def check_the_answer_is_in_the_requested_language(
    answer: str, requested_language: str
) -> ValidationOutcome:
    """
    An Arabic question must not be answered in English, or the reverse.

    What is judged is the assistant's own prose, not what it is quoting. An employee who
    asked four questions in English and then asked in Arabic what they had asked is owed
    their own words back unchanged, inside an Arabic reply — and counting those quoted
    English words against the reply called it English and threw it away.

    Only when the answer is nothing *but* quotation is the whole of it judged, so wrapping
    a reply in quote marks cannot be a way around the check.
    """
    if not answer.strip():
        return ValidationOutcome(is_valid=False, reason="the answer is empty")

    in_its_own_words = QUOTED_SPAN_PATTERN.sub(" ", answer)
    judged = in_its_own_words if in_its_own_words.strip() else answer

    if detect_language(judged) == requested_language:
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
    """Every figure the text states, whether it wrote it in digits or in words."""
    normalised = _normalise_digits(text)
    in_digits = {
        _normalise_number(number)
        for number in re.findall(r"\d[\d,]*(?:\.\d+)?", normalised)
    }
    in_words = {
        _normalise_number(str(NUMBER_WORDS[match.group(1).lower()]))
        for match in SPELLED_QUANTITY_PATTERN.finditer(normalised)
    }
    return in_digits | in_words
