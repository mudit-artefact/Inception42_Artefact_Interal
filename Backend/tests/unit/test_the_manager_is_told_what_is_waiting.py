"""
A manager's inbox names who is waiting, and for what.

"You can review and click Approve Leave or Reject on the card below" was the whole reply
to "what leave requests do I need to approve?" — and to "who asked for it and for how
long?" asked immediately after it. It names nobody, states nothing, and answers neither
question. A manager asked twice and got the same sentence both times.

Every fact it should have said is already in hand: `get_manager_pending_approvals`
returns the name, the leave type, the dates, the day count and the request id for each
row, and the card below the sentence is drawn from that same list.
"""

import json

from app.workflow.answer_validation import validate_answer
from app.workflow.nodes.handle_leave_action import _describe_pending_approvals

ONE_REQUEST = [
    {
        "request_id": 17,
        "employee_id": "EMP011",
        "employee_name": "Hessa Al Shamsi",
        "leave_type": "Annual Leave",
        "start_date": "2026-10-05",
        "end_date": "2026-10-16",
        "days_requested": 10,
    }
]

TWO_REQUESTS = ONE_REQUEST + [
    {
        "request_id": 18,
        "employee_id": "EMP004",
        "employee_name": "Omar Al Suwaidi",
        "leave_type": "Sick Leave",
        "start_date": "2026-11-02",
        "end_date": "2026-11-04",
        "days_requested": 3,
    }
]


def test_it_names_who_asked_and_for_how_long():
    said = _describe_pending_approvals(ONE_REQUEST, "en")

    assert "Hessa Al Shamsi" in said
    assert "10 days" in said
    assert "annual leave" in said
    assert "5 October 2026" in said and "16 October 2026" in said
    assert "#17" in said


def test_every_waiting_request_is_named_not_just_the_first():
    said = _describe_pending_approvals(TWO_REQUESTS, "en")

    assert "Hessa Al Shamsi" in said and "Omar Al Suwaidi" in said
    assert "10 days" in said and "3 days" in said
    assert "2 leave requests" in said


def test_the_arabic_reply_says_the_same_things():
    said = _describe_pending_approvals(ONE_REQUEST, "ar")

    assert "Hessa Al Shamsi" in said
    assert "إجازة سنوية" in said
    assert "5 أكتوبر 2026" in said
    assert "17" in said


def test_arabic_counts_its_nouns_the_way_arabic_counts_them():
    """
    Three to ten take the plural, eleven upwards goes back to the singular, and two is
    the dual. "3 يوماً" is the shape a machine writes and a reader notices.
    """
    def days_line(count):
        rows = [dict(ONE_REQUEST[0], days_requested=count)]
        return _describe_pending_approvals(rows, "ar")

    assert "يوم واحد" in days_line(1)
    assert "يومان" in days_line(2)
    assert "3 أيام" in days_line(3)
    assert "12 يوماً" in days_line(12)


def test_the_figures_it_states_are_the_ones_on_the_card():
    """
    The sentence goes through the same check as every other answer, against the card it
    sits above. A day count in the sentence that is not in the card is exactly what that
    check exists to catch — so this both proves the reply is valid and proves it is being
    checked at all.
    """
    for language in ("en", "ar"):
        outcome = validate_answer(
            answer=_describe_pending_approvals(TWO_REQUESTS, language),
            evidence_text=json.dumps(
                {"action_type": "MANAGER_PENDING_APPROVALS", "pending_approvals": TWO_REQUESTS},
                ensure_ascii=False,
                default=str,
            ),
            employee_id="EMP001",
            requested_language=language,
            has_any_evidence=True,
        )

        assert outcome.is_valid, f"{language}: {outcome.reason} {outcome.unsupported_claims}"


def test_a_date_it_cannot_read_is_passed_through_rather_than_dropped():
    rows = [dict(ONE_REQUEST[0], start_date="as soon as possible")]

    assert "as soon as possible" in _describe_pending_approvals(rows, "en")
