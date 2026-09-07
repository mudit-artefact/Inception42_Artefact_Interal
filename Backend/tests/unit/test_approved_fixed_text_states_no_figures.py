"""
An approved fixed sentence may not carry a figure.

Every answer now passes the check that holds each quantity against the evidence behind
it — but a fixed sentence is its own evidence, so a number typed into one grounds itself
and sails through. The check cannot be the guard here. This is.

It is the rule the education allowance answer broke. "Up to AED 45,000 per eligible
child" was typed into a node, returned to everyone, and marked verified. Nothing at the
time could have caught it, because there was nothing that said fixed copy must not state
entitlements. This says it.

A figure that belongs to an employee is read from their record and travels with the
answer. A figure that belongs to policy is quoted from the documents with a citation.
A figure sitting in a Python string belongs to neither.
"""

import pytest

from app.workflow import prompts
from app.workflow.answer_validation import QUANTITY_PATTERN

# Every constant in prompts.py holding text an employee reads verbatim.
APPROVED_FIXED_TEXT = [
    "DOCUMENT_UPLOAD_RESPONSE",
    "DOCUMENT_UPLOAD_RESPONSE_WITH_FILES",
    "NOTHING_TO_REPHRASE_MESSAGES",
    "GREETING_MESSAGES",
    "GREETING_BODY",
    "ACKNOWLEDGMENT_MESSAGES",
    "PLEASANTRY_MESSAGES",
    "GRATITUDE_MESSAGES",
    "REPEAT_GREETING_MESSAGES",
    "OUT_OF_SCOPE_MESSAGES",
    "NO_EVIDENCE_MESSAGES",
    "ESCALATION_MESSAGES",
]


def _sentences_in(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [line for item in value.values() for line in _sentences_in(item)]
    if isinstance(value, (list, tuple)):
        return [line for item in value for line in _sentences_in(item)]
    return []


@pytest.mark.parametrize("constant_name", APPROVED_FIXED_TEXT)
def test_no_approved_sentence_states_a_quantity(constant_name):
    sentences = _sentences_in(getattr(prompts, constant_name))
    assert sentences, f"{constant_name} holds no text; has it been renamed?"

    for sentence in sentences:
        stated = [match.group(0).strip() for match in QUANTITY_PATTERN.finditer(sentence)]
        assert not stated, (
            f"{constant_name} states {stated}. A day count, an amount or a percentage in "
            "fixed copy is grounded in nothing but itself — read it from the employee's "
            "record or quote it from the policy documents instead."
        )


def test_the_constants_this_guards_still_exist():
    """A renamed constant would leave this test passing while guarding nothing."""
    missing = [name for name in APPROVED_FIXED_TEXT if not hasattr(prompts, name)]
    assert not missing, f"{missing} no longer exist; update this list"
