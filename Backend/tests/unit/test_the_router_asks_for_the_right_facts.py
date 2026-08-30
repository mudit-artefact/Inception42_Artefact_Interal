"""
A field that is not asked for is not read.

Routing names which of the employee's facts an answer may use, and anything unnamed is
left out of the prompt entirely. When the model named nothing at all, the fallback used
to be the profile — job title, department, grade — whatever the question was about. So
"how does my balance compare with last year" was answered from a record deliberately
stripped of the balances, and the assistant reported the information was unavailable.
"""

import pytest

from app.domain.enums import HrDataField
from app.workflow.nodes.route_subqueries import _fields_the_question_points_at


@pytest.mark.parametrize(
    "question, needed",
    [
        ("How does my leave balance this year compare with last year?",
         HrDataField.ANNUAL_LEAVE_BALANCE),
        ("How many sick days do I have left?", HrDataField.SICK_LEAVE_BALANCE),
        ("Who approved my January leave?", HrDataField.RECENT_LEAVE_REQUESTS),
        ("Which of my expense claims did Fatima approve?", HrDataField.RECENT_EXPENSE_CLAIMS),
        ("Who is my line manager?", HrDataField.LINE_MANAGER),
        ("Am I still on probation?", HrDataField.PROBATION_STATUS),
        ("Can I fly business class?", HrDataField.EMPLOYEE_PROFILE),
        ("كم رصيدي من الإجازات؟", HrDataField.ANNUAL_LEAVE_BALANCE),
    ],
)
def test_the_guess_covers_what_the_question_is_about(question, needed):
    assert needed in _fields_the_question_points_at(question)


def test_something_unrecognised_still_reads_the_profile():
    """A guess that returns nothing would read no record at all."""
    assert _fields_the_question_points_at("tell me about myself") == [
        HrDataField.EMPLOYEE_PROFILE
    ]


def test_every_field_the_routing_prompt_describes_is_a_field_that_exists():
    """
    The instructions describe each label so the model can choose between them. A label
    described but not defined would be requested and then silently dropped.
    """
    from app.workflow.prompts import SOURCE_ROUTING_INSTRUCTIONS

    for field in HrDataField:
        assert f"- {field.value}:" in SOURCE_ROUTING_INSTRUCTIONS, (
            f"{field.value} is readable but the router is never told what is in it"
        )
