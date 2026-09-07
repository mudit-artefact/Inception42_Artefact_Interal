"""
Workflow test to verify that follow-up questions unrelated to pending leave requests:
1. Do NOT show the Leave Request Sent / confirmation card.
2. Do NOT submit the unconfirmed leave request to the database.
3. Answer the user's question directly and cleanly without lingering action payloads.
"""

import pytest
from app.database.engine import SessionLocal
from app.database.tables import LeaveRequest
from app.services.answer_question_service import answer_question


@pytest.fixture(autouse=True)
def _use_canned_passages(stub_policy_search_service, temporary_database):
    """Ensure database and policy stubs are ready."""


def test_unrelated_follow_up_does_not_trigger_leave_submission(
    conversation_workflow, fake_language_model, script_understanding, script_routing
):
    cid = "test-unrelated-followup-conv"

    # Turn 1: Script QueryUnderstanding (apply_leave) and LeaveApplicationDraft extraction
    script_understanding(intent="apply_leave")
    fake_language_model.reply_to_structured_call(
        "LeaveApplicationDraft",
        {
            "leave_type": "Annual leave",
            "start_date": "2026-11-17",
            "end_date": "2026-11-19",
            "days_requested": 3,
            "reason": "Personal vacation",
            "is_complete": True,
            "missing_fields": [],
        },
    )

    res1 = answer_question(
        conversation_workflow,
        "I want to apply for annual leave from 2026-11-17 to 2026-11-19",
        "EMP001",
        cid,
    )
    assert res1.action_payload is not None
    assert res1.action_payload.get("action_type") == "CONFIRM_LEAVE_APPLICATION"

    # Turn 2: User asks an unrelated question instead of confirming
    script_understanding(
        intent="hr_question",
        is_multi_question=False,
        needs_clarification=False,
    )
    script_routing(required_evidence="policy")
    fake_language_model.reply_to_plain_call(
        "Remote work policy allows 2 days per week subject to line manager approval."
    )

    res2 = answer_question(
        conversation_workflow,
        "Hey, what is the remote work policy, and do I have enough annual leave left for a 2-week vacation?",
        "EMP001",
        cid,
    )

    # Verification: action_payload must be None (no Leave Request Sent card)
    assert res2.action_payload is None
    assert not res2.is_awaiting_clarification

    # Verification: No leave was committed in the database
    db = SessionLocal()
    req = (
        db.query(LeaveRequest)
        .filter_by(employee_id="EMP001", start_date="2026-11-17")
        .first()
    )
    assert req is None
    db.close()


def test_explicit_confirmation_submits_leave_then_subsequent_question_has_no_card(
    conversation_workflow, fake_language_model, script_understanding, script_routing
):
    cid = "test-confirm-then-subsequent-q"

    # Turn 1: Draft leave request
    script_understanding(intent="apply_leave")
    fake_language_model.reply_to_structured_call(
        "LeaveApplicationDraft",
        {
            "leave_type": "Annual leave",
            "start_date": "2026-11-24",
            "end_date": "2026-11-26",
            "days_requested": 3,
            "reason": "Family trip",
            "is_complete": True,
            "missing_fields": [],
        },
    )

    res1 = answer_question(
        conversation_workflow,
        "I want to apply for annual leave from 2026-11-24 to 2026-11-26",
        "EMP001",
        cid,
    )
    assert res1.action_payload.get("action_type") == "CONFIRM_LEAVE_APPLICATION"

    # Turn 2: Explicitly confirm
    res2 = answer_question(conversation_workflow, "Confirm", "EMP001", cid)
    assert res2.action_payload is not None
    assert res2.action_payload.get("action_type") == "LEAVE_SUBMITTED_PENDING_APPROVAL"

    # Turn 3: Subsequent question
    script_understanding(
        intent="hr_question",
        is_multi_question=False,
        needs_clarification=False,
    )
    script_routing(required_evidence="policy")
    fake_language_model.reply_to_plain_call(
        "Sick leave policy provides up to 90 calendar days per year."
    )

    res3 = answer_question(conversation_workflow, "What is the policy on sick leave?", "EMP001", cid)
    assert res3.action_payload is None
