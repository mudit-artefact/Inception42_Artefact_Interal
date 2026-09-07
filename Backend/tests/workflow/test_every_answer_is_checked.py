"""
No answer reaches the employee without being checked.

Seven of the twelve ways a turn could end used to edge straight to the end of the graph:
the greeting, the document-upload prompt, the four leave actions and school verification.
Between them they were every branch that states a figure or changes a record, and the one
branch that *was* checked was the one that had already answered from retrieved documents.

That is how an answer quoting an allowance figure nobody could point at reached the
employee marked verified. The step that exists to catch exactly that was the one step it
never passed through.
"""

from app.workflow.conversation_workflow import build_conversation_workflow
from app.workflow.nodes.prepare_action_answer import prepare_action_answer
from app.workflow.nodes.validate_answer import validate_answer

# The two steps that may speak to the employee. Both sit downstream of the check.
ALLOWED_TO_END_A_TURN = {"finalize_verified_answer", "build_safe_fallback"}


def test_nothing_reaches_the_employee_without_passing_the_check():
    """
    A structural guard, not a behavioural one. Wiring a new branch straight to the end is
    a one-line change that no other test would notice, because every other test asserts on
    what an answer says rather than on how it got out.
    """
    graph = build_conversation_workflow()

    reaches_the_end = {
        start for start, end in graph.edges if end == "record_conversation_turn"
    }
    assert reaches_the_end == ALLOWED_TO_END_A_TURN, (
        f"{sorted(reaches_the_end - ALLOWED_TO_END_A_TURN)} can answer the employee "
        "without passing validate_answer"
    )


def test_every_branch_that_answers_without_searching_is_still_checked():
    """The seven branches all arrive at the check, by way of one shared step."""
    graph = build_conversation_workflow()

    # `handle_leave_application` is not here: it decides what to ask next rather than
    # answering, and the step that finally answers for that branch is
    # `submit_leave_application`. Every other action now answers through `run_action`.
    answers_without_searching = {
        "generate_greeting",
        "generate_document_upload_prompt",
        "submit_leave_application",
        "run_action",
    }
    prepared = {start for start, end in graph.edges if end == "prepare_action_answer"}
    assert answers_without_searching <= prepared

    assert ("prepare_action_answer", "validate_answer") in graph.edges


def test_an_action_may_not_state_a_figure_its_own_result_does_not_carry():
    """
    The figures in the sentence and the figures on the card come from the same data. One
    that appears in neither the card nor the policy documents came from somewhere neither
    the employee nor we can point at, which is the whole reason the check exists.
    """
    state = {
        "employee_id": "EMP001",
        "employee_question": "cancel my leave request",
        "requested_language": "en",
        "final_answer": "Cancelled. 12 working days have been put back on your balance.",
        "action_payload": {"action_type": "LEAVE_CANCELLED_BY_USER", "restored_days": 3},
    }
    state.update(prepare_action_answer(state))

    outcome = validate_answer(state)

    assert outcome["answer_verdict"] == "invalid"
    assert "12 working days" in outcome["unsupported_claims"]


def test_an_action_whose_figures_match_its_result_is_shown():
    """The same answer, with the figure the action actually produced, passes."""
    state = {
        "employee_id": "EMP001",
        "employee_question": "cancel my leave request",
        "requested_language": "en",
        "final_answer": "Cancelled. 3 working days have been put back on your balance.",
        "action_payload": {"action_type": "LEAVE_CANCELLED_BY_USER", "restored_days": 3},
    }
    state.update(prepare_action_answer(state))

    outcome = validate_answer(state)

    assert outcome["answer_verdict"] == "valid", outcome["validation_reason"]


def test_an_action_answered_in_the_wrong_language_is_not_shown():
    """
    Approving and rejecting had no Arabic wording at all, so an Arabic-speaking manager
    was answered in English. Routing these branches through the check is what turns that
    from something nobody notices into something that fails.
    """
    state = {
        "employee_id": "EMP001",
        "employee_question": "اعتمد إجازة هند",
        "requested_language": "ar",
        "final_answer": "Leave request has been approved. The employee has been notified.",
        "action_payload": {"action_type": "MANAGER_APPROVED_SUCCESS", "result": {}},
    }
    state.update(prepare_action_answer(state))

    outcome = validate_answer(state)

    assert outcome["answer_verdict"] == "invalid"
    assert "language" in outcome["validation_reason"]
