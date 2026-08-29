"""
The workflow's branching decisions.

These were `if` statements inside a hand-written function sitting between two separate
graphs. Now they are plain functions of the state, so every branch can be checked here
without a model, a database, or a graph.
"""

import pytest
from langgraph.types import Send

from app.workflow.routing_rules import (
    MAXIMUM_CLARIFICATION_ROUNDS,
    decide_after_understanding,
    decide_answer_validity,
    fan_out_to_each_subquery,
)


@pytest.mark.parametrize(
    "state, expected_next_step",
    [
        ({"question_intent": "greeting"}, "generate_greeting"),
        ({"question_intent": "out_of_scope"}, "build_safe_fallback"),
        (
            {"question_intent": "hr_question", "needs_clarification": True, "clarification_round": 0},
            "compose_clarification_question",
        ),
        (
            {"question_intent": "hr_question", "needs_clarification": False, "needs_rewrite": True},
            "rewrite_and_decompose_query",
        ),
        (
            {
                "question_intent": "hr_question",
                "needs_clarification": False,
                "needs_rewrite": False,
                "is_multi_question": True,
            },
            "rewrite_and_decompose_query",
        ),
        (
            {"question_intent": "hr_question", "needs_clarification": False, "needs_rewrite": False},
            "route_each_subquery",
        ),
    ],
)
def test_the_first_branch_picks_the_right_next_step(state, expected_next_step):
    assert decide_after_understanding(state) == expected_next_step


def test_a_message_asking_two_things_is_split_even_when_it_is_worded_well():
    """Otherwise the second thing is never searched for, and never answered."""
    well_worded = {
        "question_intent": "hr_question",
        "needs_clarification": False,
        "needs_rewrite": False,
        "is_multi_question": True,
    }

    assert decide_after_understanding(well_worded) == "rewrite_and_decompose_query"


def test_the_employee_is_not_asked_to_clarify_more_than_once():
    """Otherwise a question the model keeps finding vague loops forever."""
    already_asked = {
        "question_intent": "hr_question",
        "needs_clarification": True,
        "clarification_round": MAXIMUM_CLARIFICATION_ROUNDS,
        "needs_rewrite": False,
    }

    assert decide_after_understanding(already_asked) == "route_each_subquery"


def test_a_greeting_is_never_sent_for_clarification():
    state = {"question_intent": "greeting", "needs_clarification": True, "clarification_round": 0}

    assert decide_after_understanding(state) == "generate_greeting"


def _plan(index: int, required_evidence: str, fields: list[str] | None = None) -> dict:
    return {
        "index": index,
        "question": f"part {index}",
        "required_evidence": required_evidence,
        "requested_hr_data_fields": fields or [],
        "routing_reason": "",
    }


def _state_with(*plans: dict) -> dict:
    return {
        "subquery_plans": list(plans),
        "employee_facts": {"employee_id": "EMP001"},
        "requested_language": "en",
    }


@pytest.mark.parametrize("required_evidence", ["policy", "hr_data", "both"])
def test_a_single_part_starts_a_single_branch(required_evidence):
    branches = fan_out_to_each_subquery(_state_with(_plan(1, required_evidence)))

    assert isinstance(branches, list) and len(branches) == 1
    assert isinstance(branches[0], Send)
    assert branches[0].arg["required_evidence"] == required_evidence


def test_every_part_of_a_split_question_starts_its_own_branch():
    """The branches run at the same time, so three parts cost one round of searching."""
    branches = fan_out_to_each_subquery(
        _state_with(
            _plan(1, "policy"),
            _plan(2, "hr_data", ["line_manager"]),
            _plan(3, "both", ["annual_leave_balance"]),
        )
    )

    assert [branch.arg["index"] for branch in branches] == [1, 2, 3]
    assert branches[1].arg["requested_hr_data_fields"] == ["line_manager"]


def test_a_branch_carries_everything_it_needs_on_its_own():
    """A branch started with Send cannot read the rest of the conversation's state."""
    branch = fan_out_to_each_subquery(_state_with(_plan(1, "hr_data", ["line_manager"])))[0]

    assert set(branch.arg) == {
        "index",
        "question",
        "required_evidence",
        "requested_hr_data_fields",
        "employee_facts",
        "requested_language",
    }


def test_a_part_that_cannot_be_served_starts_no_branch():
    branches = fan_out_to_each_subquery(
        _state_with(_plan(1, "policy"), _plan(2, "unsupported"))
    )

    assert [branch.arg["index"] for branch in branches] == [1]


def test_a_question_where_no_part_can_be_served_gathers_nothing_at_all():
    assert (
        fan_out_to_each_subquery(_state_with(_plan(1, "unsupported"), _plan(2, "unsupported")))
        == "build_safe_fallback"
    )


@pytest.mark.parametrize(
    "verdict, expected_next_step",
    [
        ("valid", "finalize_verified_answer"),
        ("invalid", "build_safe_fallback"),
        (None, "build_safe_fallback"),
    ],
)
def test_only_a_valid_answer_is_shown(verdict, expected_next_step):
    assert decide_answer_validity({"answer_verdict": verdict}) == expected_next_step
