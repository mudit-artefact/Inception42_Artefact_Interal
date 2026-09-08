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


def test_a_dirham_figure_written_the_english_way_is_still_checked():
    """
    Every unit follows its number — "15 days", "45,000 درهم" — except the currency code
    in English, which comes first. "AED 45,000" was therefore not a quantity as far as
    this check was concerned, and so was held against nothing at all.

    That is the exact shape of the education allowance answer that shipped: a dirham
    ceiling, written the way anybody writes it in English, in an answer marked verified.
    """
    outcome = validate_answer(
        answer="Your education allowance is up to AED 45,000 per eligible child.",
        evidence_text='{"plan_name": "Education Allowance - Standard", "annual_limit_aed": 25000}',
        employee_id="EMP001",
        requested_language="en",
        has_any_evidence=True,
    )

    assert not outcome.is_valid
    assert "AED 45,000" in outcome.unsupported_claims


def test_the_employees_own_dirham_ceiling_passes():
    """The same sentence, with the figure their own record holds."""
    outcome = validate_answer(
        answer="Your education allowance is up to AED 25,000 per eligible child.",
        evidence_text='{"plan_name": "Education Allowance - Standard", "annual_limit_aed": 25000}',
        employee_id="EMP001",
        requested_language="en",
        has_any_evidence=True,
    )

    assert outcome.is_valid, outcome.reason


# ── One fact, written two ways ───────────────────────────────────────────────
#
# Both of these threw away a correct answer in the seven-conversation test round, and
# both told the employee "I could not confirm this from the current policy documents"
# over a figure that was sitting in the evidence in a different notation.


def test_a_percentage_may_stand_on_the_fraction_it_means():
    """
    Shamma is part-time. Her record prints "Works 0.6 of full time"; the sentence anybody
    would write is "you work 60% of full time". Rejecting it told a part-time employee
    that her own working pattern could not be confirmed.
    """
    outcome = validate_answer(
        answer="You work 60% of full time, so your entitlement is pro-rata.",
        evidence_text="Job title: Facilities Supervisor. Works 0.6 of full time.",
        employee_id="EMP007",
        requested_language="en",
        has_any_evidence=True,
    )

    assert outcome.is_valid, outcome.reason


def test_only_a_percentage_may_do_that():
    """
    The narrowness is the point. If a fraction could ground any unit, a 0.3 anywhere in
    the evidence would license "you may carry over 30 days" — the invented figure this
    whole check exists to catch.
    """
    outcome = validate_answer(
        answer="You may carry over 30 days.",
        evidence_text="Job title: Facilities Supervisor. Works 0.3 of full time.",
        employee_id="EMP007",
        requested_language="en",
        has_any_evidence=True,
    )

    assert not outcome.is_valid
    assert outcome.unsupported_claims == ["30 days"]


def test_a_figure_the_policy_wrote_in_words_still_counts_as_that_figure():
    """
    HC-PC-002 §2.2.1 in Arabic sets the sick leave window as "فترة اثني عشر شهراً" — a
    twelve-month period, containing no 12. An answer quoting it as "12 شهراً" was quoting
    the policy, and was rejected for inventing.
    """
    outcome = validate_answer(
        answer="يُحتسب الاستحقاق على مدى فترة 12 شهراً متحركة.",
        evidence_text="يُحتسب استحقاق التسعين يوماً على مدى فترة اثني عشر شهراً متحركة.",
        employee_id="EMP001",
        requested_language="ar",
        has_any_evidence=True,
    )

    assert outcome.is_valid, outcome.reason


def test_the_same_holds_in_english():
    outcome = validate_answer(
        answer="The entitlement is counted over a 12 month rolling period.",
        evidence_text="The entitlement is counted over a twelve-month rolling period.",
        employee_id="EMP001",
        requested_language="en",
        has_any_evidence=True,
    )

    assert outcome.is_valid, outcome.reason


def test_a_number_word_in_ordinary_prose_grounds_nothing():
    """
    Which is why a number word only counts where a unit follows it, exactly as a digit
    does. Otherwise the "one" in "one of the following" would ground any "1 day" an
    answer cared to state, and the word is everywhere.
    """
    outcome = validate_answer(
        answer="You must give 1 day of notice.",
        evidence_text="Approval is required in one of the following circumstances.",
        employee_id="EMP001",
        requested_language="en",
        has_any_evidence=True,
    )

    assert not outcome.is_valid
    assert outcome.unsupported_claims == ["1 day"]


def test_the_arabic_decimal_mark_is_read_as_a_decimal_point():
    """Before this, "14٫4 يوماً" parsed as the number 4 and was checked against that."""
    outcome = validate_answer(
        answer="رصيدك المتبقي هو 14٫4 يوماً.",
        evidence_text="الرصيد السنوي المتبقي: 14.4 يوماً",
        employee_id="EMP007",
        requested_language="ar",
        has_any_evidence=True,
    )

    assert outcome.is_valid, outcome.reason


def test_a_rejection_names_the_figure_that_caused_it():
    """
    A rejection that says only "the answer states figures that are not in the evidence"
    cannot be diagnosed from a log — which is how two false rejections sat unnoticed
    through a whole test round.
    """
    outcome = checked("You may carry over 30 days and 12 hours.")

    assert not outcome.is_valid
    assert outcome.unsupported_claims == ["30 days", "12 hours"]
