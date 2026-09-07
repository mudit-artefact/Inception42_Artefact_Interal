"""
Every action the assistant may take, declared in one place.

This list is the reason a new action does not widen the graph. Before it, each action was
its own node with its own intent matching, its own database session and its own way of
formatting a reply, and the five of them between them found five different answers to the
same questions. Adding a sixth meant copying all of that again.

The two fields that carry the most weight are `mutates` and `required_arguments`.

`mutates` separates reading from writing. A read may run freely — looking up which requests
are pending is how "cancel my leave" finds out what to cancel. A write may only run once it
has been through the check in `validate_tool_call`, and nothing in the graph is allowed to
reach one another way.

`required_arguments` is what lets the workflow ask the employee for a missing date instead
of guessing one. A tool that cannot say what it needs cannot be asked for politely.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Callable

from app.domain.enums import QuestionIntent
from app.services.education_allowance_service import get_education_entitlement
from app.services.leave_service import (
    approve_leave_request,
    cancel_leave_request,
    commit_leave_request,
    get_manager_pending_approvals,
    get_pending_leave_requests,
    reject_leave_request,
    validate_leave_policy,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolSpec:
    """One thing the assistant can do, and what has to be true before it does it."""

    name: str
    run: Callable[..., Any]
    mutates: bool
    required_arguments: tuple[str, ...]
    # Shown to the employee while it runs, so a booking is not forty silent seconds.
    describes: tuple[str, str]  # (English, Arabic)


@dataclass(frozen=True)
class ToolOutcome:
    """
    What came back, in a shape the rest of the workflow can rely on.

    A tool that raised and a tool that declined look the same from here: `ok` is False and
    `failure` names a reason. Neither ever carries an exception's own words — those go to
    the log. An employee who is told "IntegrityError: UNIQUE constraint failed" has been
    shown our stack trace, and the answer to a database being briefly unavailable is not to
    teach the employee what SQLAlchemy is.
    """

    ok: bool
    tool_name: str
    result: Any = None
    failure: str = ""


# ── The registry ─────────────────────────────────────────────────────────────

TOOLS: dict[str, ToolSpec] = {
    "check_leave_status": ToolSpec(
        name="check_leave_status",
        run=get_pending_leave_requests,
        mutates=False,
        required_arguments=("employee_id",),
        describes=("Reading your leave requests", "أقرأ طلبات إجازتك"),
    ),
    "list_pending_approvals": ToolSpec(
        name="list_pending_approvals",
        run=get_manager_pending_approvals,
        mutates=False,
        required_arguments=("manager_id",),
        describes=("Reading your team's requests", "أقرأ طلبات فريقك"),
    ),
    "get_education_entitlement": ToolSpec(
        name="get_education_entitlement",
        run=get_education_entitlement,
        mutates=False,
        required_arguments=("employee_id",),
        describes=("Reading your education plan", "أقرأ خطة التعليم الخاصة بك"),
    ),
    "check_leave_against_policy": ToolSpec(
        name="check_leave_against_policy",
        run=validate_leave_policy,
        mutates=False,
        required_arguments=("employee_id", "draft"),
        describes=("Checking this against the policy", "أراجع السياسة"),
    ),
    "apply_for_leave": ToolSpec(
        name="apply_for_leave",
        run=commit_leave_request,
        mutates=True,
        required_arguments=("employee_id", "validation"),
        describes=("Submitting your request", "أرسل طلبك"),
    ),
    "cancel_leave": ToolSpec(
        name="cancel_leave",
        run=cancel_leave_request,
        mutates=True,
        required_arguments=("employee_id", "request_id"),
        describes=("Cancelling your request", "ألغي طلبك"),
    ),
    "approve_leave": ToolSpec(
        name="approve_leave",
        run=approve_leave_request,
        mutates=True,
        required_arguments=("manager_id", "request_id"),
        describes=("Approving the request", "أعتمد الطلب"),
    ),
    "reject_leave": ToolSpec(
        name="reject_leave",
        run=reject_leave_request,
        mutates=True,
        required_arguments=("manager_id", "request_id"),
        describes=("Rejecting the request", "أرفض الطلب"),
    ),
}


# Which tool an understood question reaches for. The model already chose the intent one
# step earlier, so this is a lookup rather than a second question put to the model — a
# question whose answer would be less predictable, on the operations that change records.
#
# CHECK_LEAVE_STATUS is deliberately absent: whether it means "my leave" or "the leave I
# have to approve" depends on whether the asker manages anyone, which the handler settles.
TOOL_FOR_INTENT: dict[str, str] = {
    QuestionIntent.APPLY_LEAVE.value: "apply_for_leave",
    QuestionIntent.CANCEL_LEAVE.value: "cancel_leave",
    QuestionIntent.APPROVE_LEAVE.value: "approve_leave",
    QuestionIntent.REJECT_LEAVE.value: "reject_leave",
}


def tool_for_intent(intent: str | None) -> ToolSpec | None:
    """The tool an intent reaches for, or None when the intent is not an action."""
    name = TOOL_FOR_INTENT.get(intent or "")
    return TOOLS.get(name) if name else None


def evidence_from(outcome: ToolOutcome) -> str:
    """
    A tool's result, written out so the answer check can hold figures against it.

    The check reads every bare numeral out of this text, so no formatting is owed to it —
    what matters is that every figure the reply quotes is in here somewhere. A booking
    receipt saying 5 working days is what makes "5 working days" in the reply sayable, and
    what makes a figure that is in neither the receipt nor the policy documents rejected.

    This is the same trick `rephrase_previous_answer` uses to be checked at all: a branch
    that retrieves nothing supplies the thing its answer was written from.
    """
    if not outcome.ok:
        return f"THE ACTION DID NOT HAPPEN. Reason: {outcome.failure}"

    return json.dumps(_plainly(outcome.result), ensure_ascii=False, default=str)


def _plainly(value: Any) -> Any:
    """Pydantic models, lists and dicts alike, reduced to something JSON will take."""
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return {key: _plainly(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plainly(item) for item in value]
    return value
