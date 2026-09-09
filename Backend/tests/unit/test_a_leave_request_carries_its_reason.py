"""
Why somebody is asking for leave, and who gets to read it.

A manager decided on a name, a leave type and two dates. The reason was collected — the
draft has a field for it, the extraction prompt fills it, the service writes it — and then
shown to nobody: `ManagerApprovalCard` declared the field and never drew it.

Worse, most requests had no reason to show. Anyone using the calendar picker could not
supply one, because the sentence the picker composes never carried it, and the column was
filled with "Submitted via Policy & Leave Concierge agent" instead — words nobody typed,
sitting exactly where a manager looks to find out why.

The reason stays optional. HC-PC-001 asks for one only for emergency leave (§1.4.3), and
requiring it everywhere would mean asking somebody to justify being ill.
"""

import pytest

from app.database.tables import LeaveRequest
from app.services import leave_service

pytestmark = pytest.mark.usefixtures("temporary_database")

# Seeded: EMP011 reports to EMP001, and already has a request awaiting her.
ASKER = "EMP011"
DECIDER = "EMP001"


def a_request(session, notes="", decision_note=""):
    request = LeaveRequest(
        employee_id=ASKER, leave_type="Annual Leave", start_date="2026-05-04",
        end_date="2026-05-08", days_requested=5, status="Pending",
        approver_name="Alia Al Suwaidi", notes=notes, decision_note=decision_note,
    )
    session.add(request)
    session.commit()
    return request


def test_the_manager_is_given_the_reason(temporary_database):
    session = temporary_database()
    written = "My brother's wedding in Amman"
    a_request(session, notes=written)

    waiting = leave_service.get_manager_pending_approvals(DECIDER, session=session)

    assert written in [item["notes"] for item in waiting]
    session.close()


def test_no_reason_is_stored_rather_than_a_placeholder(temporary_database):
    """
    It used to read "Submitted via Policy & Leave Concierge agent". A manager reading that
    learns nothing, and cannot tell it from something the employee wrote.
    """
    session = temporary_database()
    request = a_request(session, notes="")

    assert request.notes == ""
    assert "Concierge" not in request.notes
    session.close()


def test_a_rejection_does_not_overwrite_what_the_employee_wrote(temporary_database):
    """
    Both notes used to share one column, joined by a pipe. Once a real reason was in there,
    one field held two people's words and neither could be shown without the other.
    """
    session = temporary_database()
    request = a_request(session, notes="My brother's wedding in Amman")

    leave_service.reject_leave_request(
        manager_id=DECIDER, request_id=request.id,
        reason="Two others are already away that week", session=session,
    )
    session.refresh(request)

    assert request.notes == "My brother's wedding in Amman", "the employee's words survive"
    assert request.decision_note == "Two others are already away that week"
    assert "|" not in request.notes
    session.close()


def test_the_reason_is_kept_exactly_as_written(temporary_database):
    """Not trimmed to a summary, not tidied. It is what the employee chose to say."""
    session = temporary_database()
    written = "Father's surgery on the 6th — I need to be at the hospital both days"

    assert a_request(session, notes=written).notes == written
    session.close()
