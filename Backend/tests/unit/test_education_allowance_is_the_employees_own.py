"""
The education allowance answer states the asker's own ceiling, not a fixed one.

It used to be a paragraph typed into the workflow: "up to AED 45,000 per eligible child",
returned to everyone, marked verified, with no source. AED 45,000 is a real figure — the
Enhanced plan's ceiling — but six of the twelve seeded employees are on Standard at
AED 25,000 and one is on no plan at all.
"""

from app.database.tables import Employee
from app.workflow.nodes.handle_school_verification import handle_school_verification


def _someone_on(plan_code: str, session) -> str:
    employee = (
        session.query(Employee).filter(Employee.benefit_plan_code == plan_code).first()
    )
    assert employee is not None, f"the seed has nobody on {plan_code}"
    return employee.user_id


def test_the_standard_plan_is_told_its_own_lower_ceiling(temporary_database):
    session = temporary_database()
    try:
        employee_id = _someone_on("EDU_STANDARD", session)
    finally:
        session.close()

    answer = handle_school_verification(
        {"employee_id": employee_id, "requested_language": "en"}
    )["final_answer"]

    assert "25000 AED" in answer
    assert "45000" not in answer, "the Enhanced ceiling is not this employee's"


def test_the_enhanced_plan_is_told_its_own_higher_ceiling(temporary_database):
    session = temporary_database()
    try:
        employee_id = _someone_on("EDU_ENHANCED", session)
    finally:
        session.close()

    answer = handle_school_verification(
        {"employee_id": employee_id, "requested_language": "en"}
    )["final_answer"]

    assert "45000 AED" in answer


def test_somebody_on_no_plan_is_told_so_rather_than_given_a_number(temporary_database):
    """The worst version of the old answer: a ceiling quoted to someone with no plan."""
    session = temporary_database()
    try:
        employee_id = _someone_on("NONE", session)
    finally:
        session.close()

    result = handle_school_verification(
        {"employee_id": employee_id, "requested_language": "en"}
    )

    assert "no education allowance" in result["final_answer"].lower()
    assert "25000" not in result["final_answer"]
    assert "45000" not in result["final_answer"]


def test_the_invented_age_band_is_gone(temporary_database):
    """
    "between ages 4 and 18" was in the old answer and in no plan rule, no database column
    and no policy document. There is no age rule to state.
    """
    session = temporary_database()
    try:
        employee_id = _someone_on("EDU_ENHANCED", session)
    finally:
        session.close()

    answer = handle_school_verification(
        {"employee_id": employee_id, "requested_language": "en"}
    )["final_answer"]

    assert "4 and 18" not in answer
    assert "ages" not in answer.lower()


def test_every_figure_in_the_answer_survives_the_check(temporary_database):
    """
    The whole point of reading the plan: the answer now has evidence behind it, so it
    passes the same check every other answer passes.
    """
    from app.workflow.nodes.prepare_action_answer import prepare_action_answer
    from app.workflow.nodes.validate_answer import validate_answer

    session = temporary_database()
    try:
        employee_id = _someone_on("EDU_STANDARD", session)
    finally:
        session.close()

    state = {
        "employee_id": employee_id,
        "employee_question": "how much education allowance do I get?",
        "requested_language": "en",
    }
    state.update(handle_school_verification(state))
    state.update(prepare_action_answer(state))

    outcome = validate_answer(state)

    assert outcome["answer_verdict"] == "valid", (
        f"{outcome['validation_reason']} — {outcome['unsupported_claims']}"
    )
