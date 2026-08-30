"""
Everything one turn of a conversation carries as it moves through the workflow.

This is saved after every step, so a conversation that pauses to ask the employee
something can pick up exactly where it left off — even on a later request.

A turn is carried as a list of parts, not as a single question. A message that asks two
things is split in step 2B, and from there each part is routed and gathered for on its
own, so one part can be answered from the policy documents while another is declined.

Almost everything here belongs to one question and is emptied before the next one. The
exceptions are `remembered_turns` and `previous_reply`, which belong to the conversation:
they are written at the end of a turn and read at the start of the next.
"""

from typing import Annotated, TypedDict

# Raise this when the fields below change. It is part of the saved-state key, so old
# saved conversations start fresh instead of resuming into steps that expect new fields.
CONVERSATION_STATE_VERSION = 4


def thread_name_for(conversation_id: str) -> str:
    """
    What a conversation is saved under.

    The version is part of the name so that changing the shape of a conversation's state
    starts new conversations rather than resuming old ones into steps that expect fields
    they do not have.

    It lives here, beside the version it embeds, because the two only make sense
    together — the name was previously built in the service layer and its result written
    out by hand in three tests, so every version bump broke three strings that looked
    unrelated to the change.
    """
    return f"{conversation_id}:state-v{CONVERSATION_STATE_VERSION}"


def collect_from_every_subquery(existing: list | None, incoming: list | None) -> list:
    """
    Gather what the parallel branches found, one entry per part of the question.

    The branches run at the same time and each returns only its own findings, so entries
    are appended rather than overwritten. `None` empties the list, which is how the end
    of a turn stops one turn's evidence from being carried into the next: returning an
    empty list would append nothing and leave the old entries in place.
    """
    if incoming is None:
        return []
    return list(existing or []) + list(incoming)


class SubqueryTask(TypedDict):
    """
    One part of the question, handed to a branch that runs on its own.

    A branch started with Send does not see the rest of the conversation's state, so
    everything it needs to do its work is in here.
    """

    index: int
    question: str
    required_evidence: str
    requested_hr_data_fields: list[str]
    employee_facts: dict
    requested_language: str


class ConversationState(TypedDict, total=False):
    # What the conversation has already said. These outlive the question that wrote
    # them — see WORKED_OUT_FRESH_EACH_QUESTION in nodes/load_employee_facts.
    remembered_turns: list[dict]
    # The most recent reply, kept whole: {"text", "citations", "language"}. Remembered
    # turns are clipped short and flattened onto one line, which is right for working out
    # what a follow-up refers to and useless for rewriting a reply — you cannot shorten
    # what you can only see 300 characters of, or re-bullet a list whose line breaks are
    # gone. One reply, in full, is what "make that shorter" needs.
    previous_reply: dict

    # What the employee asked
    conversation_id: str
    employee_id: str
    employee_question: str
    requested_language: str  # "en" | "ar"
    started_at_seconds: float

    # Who they are
    employee_facts: dict
    employee_profile: dict

    # Step 1 — understanding the question
    question_intent: str
    intent_confidence: float
    needs_clarification: bool
    needs_rewrite: bool
    is_multi_question: bool
    missing_information: list[str]

    # Step 2A — asking something back
    original_question: str | None
    clarification_question: str | None
    employee_clarification_reply: str | None
    is_awaiting_clarification: bool
    clarification_round: int

    # Step 2B — the question, reworded and split into standalone parts
    subqueries: list[str]
    retrieval_query: str

    # Step 3 — where each part must be answered from, and the same for the turn as a whole
    subquery_plans: list[dict]
    required_evidence: str
    requested_hr_data_fields: list[str]
    routing_reason: str

    # Step 4 — what each branch found, and the merged view the rest of the turn reads
    subquery_evidence: Annotated[list[dict], collect_from_every_subquery]
    subquery_statuses: list[dict]
    policy_passages: list[dict]
    hr_data_facts: dict
    evidence_summary: str
    # What the answer's figures are held against. The evidence alone, with none of the
    # question text that `evidence_summary` carries for the model's benefit.
    checkable_evidence: str

    # Step 5 — the drafted answer
    draft_answer: str
    # Each figure the answer worked out rather than quoted, and what it worked it out
    # from. Read only by the check that follows, to tell arithmetic from invention.
    declared_calculations: list[dict]
    tokens_used: int

    # The check before the answer is allowed out
    answer_verdict: str  # "valid" | "invalid"
    unsupported_claims: list[str]
    validation_reason: str

    # What the employee finally receives
    final_answer: str
    citations: list[dict]
    answer_status: str
    fallback_reason: str | None
    latency_milliseconds: int
