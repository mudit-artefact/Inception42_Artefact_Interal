"""
How an answer is graded without a model in the loop.

Both evaluation runners score free text produced by a language model, and neither may use
a language model to do it — a judge that is itself a model turns a regression into an
argument about which of the two was wrong. So grading is plain comparison, and these are
the four comparisons every runner shares.

They lived inside `scripts/run_taxonomy_scenarios.py` until the conversation runner needed
them too. Two runners that each grow their own idea of whether "AED 450.0" states the fact
"450" will eventually disagree, and the disagreement will look like a system regression.
"""

import re
import unicodedata


# Markdown emphasis, which the assistant uses heavily and which means nothing to a
# comparison. "a maximum of **10** days" states the fact "10 days"; the asterisks sitting
# inside the phrase are the only thing that used to stop it matching.
MARKDOWN_NOISE = re.compile(r"[*_`#]+")


def flatten(text: str) -> str:
    """Comparable text: one line, normalised Arabic, lowercase, no markdown."""
    without_markdown = MARKDOWN_NOISE.sub("", unicodedata.normalize("NFKC", text or ""))
    return " ".join(without_markdown.split()).lower()


def as_a_number(text: str) -> str:
    """450, 450.0 and 450 are one figure. Matches how the answer check compares them."""
    try:
        return f"{float(text.replace(',', '')):g}"
    except ValueError:
        return text


def contains_fact(answer: str, fact: str) -> bool:
    """
    Whether the answer states a fact the case requires.

    A bare number is compared as a number, not as text. "450" is stated by an answer
    saying "AED 450.0", and is not stated by one that only mentions 2450 — matching on
    the characters gets both of those wrong, in opposite directions.
    """
    haystack, needle = flatten(answer), flatten(fact)
    if not needle:
        return True

    if re.fullmatch(r"[\d,.]+", needle):
        wanted = as_a_number(needle)
        return any(
            as_a_number(found) == wanted
            for found in re.findall(r"\d[\d,]*(?:\.\d+)?", haystack)
        )

    quantity = re.fullmatch(r"(\d[\d,]*(?:\.\d+)?)\s+([a-z]+?)s?", needle)
    if quantity:
        return _states_the_quantity(haystack, *quantity.groups())

    return needle in haystack


def _states_the_quantity(haystack: str, amount: str, unit: str) -> bool:
    """
    Whether the text states this many of this unit, however it is written.

    "6 months", "6 month" and "6-month" are one fact, and only the first used to count.
    An answer saying "your standard 6-month probationary period" was scored as having
    failed to give the length of probation, which is a report about hyphens dressed up as
    a report about the assistant.

    The unit still has to be there: this accepts "6-month" for "6 months" and refuses
    "6 days", so it loosens the phrasing and not the fact.
    """
    return re.search(
        rf"\b{re.escape(amount)}[-\s]+{re.escape(unit)}s?\b", haystack
    ) is not None


def looks_like_a_refusal(answer: str, intent: str) -> bool:
    """
    Whether the assistant declined rather than answered.

    The wire response carries `intent` but not the internal answer status, so an
    out-of-scope refusal is visible directly and every other kind is recognised by what
    the fixed messages actually say.
    """
    if intent == "not_in_scope":
        return True
    declining = [
        "cannot assist", "outside", "not able to", "contact people & culture",
        "people@hcservices.ae", "not yet published", "in drafting", "cannot provide",
        "i do not have", "unable to",
    ]
    flattened = flatten(answer)
    return any(phrase in flattened for phrase in declining)
