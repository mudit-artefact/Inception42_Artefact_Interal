"""
An answer may work a figure out. It may not invent one.

The check on an answer's figures used to demand that every one appear in the evidence
word for word. That reads like grounding and is really a ban on arithmetic: "you have 15
days left, so taking 15 would leave 0" was rejected because no policy document prints a
zero, and the employee was told the assistant could not confirm it. Five of the failures
in the scenario suite were that one rule, and not one invented figure was ever caught by
it that is not still caught now.

A figure now passes if the assistant declared the sum behind it and every input to that
sum is in the evidence. The sum itself is taken on trust — a deliberate choice, revisited
by adding a recomputation to `_figures_worked_out_from` if it is ever wanted. What is not
taken on trust is where the ingredients came from, which is what stops a declaration
being used to launder a number.
"""

from app.workflow.answer_validation import validate_answer

EVIDENCE = (
    "Days 1-15 of the 90 are at full pay. Days 16-60 are at half pay.\n"
    "THIS EMPLOYEE'S OWN RECORD\n"
    "Annual leave: 24 entitled, 5 used, 19 remaining\n"
    "Sick leave taken this year: 34 days"
)


def checked(answer: str, calculations: list[dict] | None = None):
    return validate_answer(
        answer=answer,
        evidence_text=EVIDENCE,
        employee_id="EMP006",
        requested_language="en",
        has_any_evidence=True,
        declared_calculations=calculations or [],
    )


# ── What must now be allowed ─────────────────────────────────────────────────


def test_a_declared_subtraction_is_allowed():
    """The flagship case: 19 appears nowhere, and is the correct answer."""
    outcome = checked(
        "Of your 34 sick days, 15 days were at full pay and 19 days at half pay.",
        [{"result": 19, "from_numbers": [34, 15], "how": "34 - 15"}],
    )

    assert outcome.is_valid


def test_a_declared_result_of_zero_is_allowed():
    """Zero is printed in no policy document, which is why this needed fixing."""
    outcome = checked(
        "You have 19 remaining, so taking 19 days would leave 0 days.",
        [{"result": 0, "from_numbers": [19, 19], "how": "19 - 19"}],
    )

    assert outcome.is_valid


def test_a_figure_quoted_straight_from_the_evidence_needs_no_declaration():
    outcome = checked("You are entitled to 24 days a year.")

    assert outcome.is_valid


# ── What must still be refused ───────────────────────────────────────────────


def test_an_invented_figure_is_still_refused():
    outcome = checked("You may carry over 30 days.")

    assert not outcome.is_valid
    assert outcome.unsupported_claims == ["30 days"]


def test_a_declaration_with_no_inputs_cannot_launder_a_figure():
    """
    Otherwise the declaration becomes the loophole rather than the safeguard.

    An empty input list would let the model assert any figure and mark it as worked out,
    which is precisely the behaviour the check exists to prevent.
    """
    outcome = checked(
        "You may carry over 30 days.",
        [{"result": 30, "from_numbers": [], "how": "it follows from the policy"}],
    )

    assert not outcome.is_valid


def test_a_declaration_built_on_a_figure_not_in_the_evidence_is_ignored():
    outcome = checked(
        "You may carry over 30 days.",
        [{"result": 30, "from_numbers": [55, 25], "how": "55 - 25"}],
    )

    assert not outcome.is_valid


def test_one_bad_declaration_does_not_invalidate_a_good_one():
    """Each sum stands or falls on its own inputs, so a bad one cannot take a good one down."""
    outcome = checked(
        "You have 19 days left; 15 days were at full pay.",
        [
            {"result": 19, "from_numbers": [24, 5], "how": "24 - 5"},
            {"result": 99, "from_numbers": [777], "how": "nonsense"},
        ],
    )

    assert outcome.is_valid


# ── What the change must not have weakened ───────────────────────────────────


def test_another_employees_record_is_still_refused():
    outcome = checked(
        "Ahmed (EMP001) has 15 days remaining.",
        [{"result": 15, "from_numbers": [24, 5], "how": "24 - 5"}],
    )

    assert not outcome.is_valid
    assert "EMP001" in outcome.unsupported_claims


def test_an_answer_with_no_evidence_at_all_is_still_refused():
    outcome = validate_answer(
        answer="You are entitled to 24 days.",
        evidence_text="",
        employee_id="EMP006",
        requested_language="en",
        has_any_evidence=False,
        declared_calculations=[{"result": 24, "from_numbers": [24], "how": "quoted"}],
    )

    assert not outcome.is_valid


# ── A figure the employee supposed in their own question ─────────────────────
#
# "If I am off sick for 40 days, what happens?" is a hypothetical. The 40 exists nowhere
# in the policy, because it is the employee's own premise — and demanding that it appear
# in a document threw away this answer and told them nothing could be confirmed:
#
#   "Off for 40 calendar days extends your probation by 10 calendar days, because
#    absence beyond 30 days extends it by the excess (40 - 30 = 10)."
#
# The answer is right, the working is declared, and 30 comes straight from the policy.
# Only the employee's own 40 was missing, and quoting it back is not a claim about policy.


def supposing(answer: str, question: str, calculations: list[dict] | None = None):
    return validate_answer(
        answer=answer,
        evidence_text=(
            "Sick absence exceeding 30 calendar days during probation extends the "
            "probationary period by the number of days in excess of 30."
        ),
        employee_id="EMP003",
        requested_language="en",
        has_any_evidence=True,
        declared_calculations=calculations or [],
        employee_question=question,
    )


def test_a_hypothetical_the_employee_supplied_can_be_quoted_back():
    outcome = supposing(
        "Being off for 40 days would extend your probation by 10 days.",
        "If I am off sick for 40 days during probation, what happens?",
        [{"result": 10, "from_numbers": [40, 30], "how": "40 - 30"}],
    )

    assert outcome.is_valid


def test_the_question_is_still_not_evidence_on_its_own():
    """
    The hole this check exists to close. An employee naming a figure does not make it
    true, and an answer agreeing with them proves nothing.
    """
    outcome = supposing("Yes, you may carry over 25 days.", "Can I carry over 25 days?")

    assert not outcome.is_valid


def test_a_sum_built_only_from_the_employees_own_numbers_proves_nothing():
    """
    Without this, declaring a calculation would be a way to launder the question back as
    an answer — which is the same hole with an extra step.
    """
    outcome = supposing(
        "Yes, you may carry over 25 days.",
        "Can I carry over 25 days?",
        [{"result": 25, "from_numbers": [25], "how": "as you said"}],
    )

    assert not outcome.is_valid


def test_a_supposed_figure_is_not_quotable_without_a_sum_that_uses_it():
    """The premise becomes quotable by being worked with, not merely by being typed."""
    outcome = supposing(
        "You said 40 days, and the limit is 30 days.",
        "If I am off sick for 40 days during probation, what happens?",
    )

    assert not outcome.is_valid
