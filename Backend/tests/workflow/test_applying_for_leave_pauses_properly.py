"""
Applying for leave asks two things, and each pause has to survive the answer given to it.

Both used to be `interrupt()` calls inside one step. Resuming re-runs a step from its
beginning, so each answer replayed everything in front of the pause — and the service
treated both pauses as though they were the same question, wanting yes or no.
"""

import pytest

from app.database.tables import LeaveRequest
from app.services.answer_question_service import answer_question


@pytest.fixture(autouse=True)
def _ready(stub_policy_search_service, temporary_database):
    """Database and policy stubs in place."""


def _drafts(fake_language_model, *payloads):
    """Answer each request-reading call with the next payload in turn."""
    remaining = list(payloads)

    def next_draft(**_call):
        return remaining.pop(0) if len(remaining) > 1 else remaining[0]

    fake_language_model.reply_to_structured_calls_in_turn("LeaveApplicationDraft", next_draft)


INCOMPLETE = {
    "leave_type": "Annual leave",
    "start_date": None,
    "end_date": None,
    "days_requested": 0,
    "reason": "",
    "is_complete": False,
    "missing_fields": ["start_date", "end_date"],
}

COMPLETE = {
    "leave_type": "Annual leave",
    "start_date": "2026-10-12",
    "end_date": "2026-10-15",
    "days_requested": 4,
    "reason": "Family visit",
    "is_complete": True,
    "missing_fields": [],
}


def test_dates_typed_by_hand_carry_the_request_forward(
    conversation_workflow, fake_language_model, script_understanding
):
    """
    The calendar used to work only because the web page slips the word "apply" into the
    message it sends, and "apply" happens to be on the list of words meaning yes. An
    employee typing their dates instead was told they had asked something new, and the
    request they had started was dropped without a word.
    """
    conversation = "typed-dates"
    script_understanding(intent="apply_leave")
    _drafts(fake_language_model, INCOMPLETE, COMPLETE)

    asked = answer_question(
        conversation_workflow, "I want to book some annual leave", "EMP001", conversation
    )
    assert asked.action_payload["action_type"] == "SHOW_LEAVE_CALENDAR_PICKER"

    understood_before = fake_language_model.count_calls_for("QueryUnderstanding")

    # No calendar, no injected keyword — just the dates, as anyone would type them.
    resumed = answer_question(
        conversation_workflow, "12 October to 15 October", "EMP001", conversation
    )

    # Reading the question again is the tell that the pause was thrown away and the dates
    # were treated as a brand new request. A resumed conversation picks up where it
    # stopped and never revisits step one.
    assert fake_language_model.count_calls_for("QueryUnderstanding") == understood_before, (
        "the paused request was abandoned and the dates were read as a new question"
    )

    assert resumed.action_payload is not None, "the request was dropped"
    assert resumed.action_payload["action_type"] == "CONFIRM_LEAVE_APPLICATION"


def test_a_new_request_does_not_confirm_the_one_already_on_screen(
    temporary_database, conversation_workflow, fake_language_model, script_understanding,
    script_routing,
):
    """
    "apply for 5 days sick leave in June", typed while an annual leave card is open,
    contains the word "apply" and used to confirm the annual leave card — committing a
    request the employee never agreed to and losing the one they had just asked for.
    """
    conversation = "stale-card"
    script_understanding(intent="apply_leave")
    _drafts(fake_language_model, COMPLETE)

    shown = answer_question(
        conversation_workflow,
        "apply for annual leave 12 October to 15 October",
        "EMP001",
        conversation,
    )
    assert shown.action_payload["action_type"] == "CONFIRM_LEAVE_APPLICATION"

    session = temporary_database()
    try:
        before = session.query(LeaveRequest).count()
    finally:
        session.close()

    script_understanding(intent="apply_leave")
    _drafts(fake_language_model, COMPLETE)
    answer_question(
        conversation_workflow, "apply for 5 days sick leave in June", "EMP001", conversation
    )

    session = temporary_database()
    try:
        annual_leave_committed = (
            session.query(LeaveRequest)
            .filter(
                LeaveRequest.leave_type == "Annual leave",
                LeaveRequest.start_date == "2026-10-12",
            )
            .count()
        )
        after = session.query(LeaveRequest).count()
    finally:
        session.close()

    assert annual_leave_committed == 0, (
        "the annual leave card was confirmed by a message asking for sick leave"
    )
    assert after == before, "nothing should have been committed by that message"


def test_saying_no_leaves_the_balance_alone(
    temporary_database, conversation_workflow, fake_language_model, script_understanding
):
    """Declining is a decision too, and it must not commit anything."""
    conversation = "declined"
    script_understanding(intent="apply_leave")
    _drafts(fake_language_model, COMPLETE)

    answer_question(
        conversation_workflow,
        "apply for annual leave 12 October to 15 October",
        "EMP001",
        conversation,
    )

    session = temporary_database()
    try:
        before = session.query(LeaveRequest).count()
    finally:
        session.close()

    declined = answer_question(conversation_workflow, "no", "EMP001", conversation)

    session = temporary_database()
    try:
        after = session.query(LeaveRequest).count()
    finally:
        session.close()

    assert after == before
    assert declined.action_payload["action_type"] == "LEAVE_CANCELLED_BY_USER"
