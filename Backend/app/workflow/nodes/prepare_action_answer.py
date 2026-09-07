"""
What an action says, made checkable.

Seven of the twelve ways a turn could end used to reach the employee without passing the
check that every other answer passes — the four leave actions, school verification, the
greeting and the document-upload prompt. Between them they are every branch that states a
figure or changes a record. The one branch that was checked was the one that had already
answered from retrieved documents.

They could not simply be wired into the check as they were. The check reads `draft_answer`
and holds every quantity in it against `checkable_evidence`, and these branches write
`final_answer` and gather nothing, so the first thing the check would have said about all
of them is that there was no evidence at all.

This node supplies both. It is the same move `rephrase_previous_answer` makes: a branch
that retrieves nothing hands over the thing its answer was actually written from.

In the next step this becomes `interpret_tool_result` and takes the tool's own output
directly rather than reading it back out of the card.
"""

import json
import logging

from app.workflow.conversation_state import ConversationState

logger = logging.getLogger(__name__)


def prepare_action_answer(state: ConversationState) -> dict:
    """Hand the check the answer and the data that answer was written from."""
    answer = state.get("final_answer", "")
    payload = state.get("action_payload")

    if payload:
        # The card the employee is shown and the figures in the sentence above it come
        # from the same data. A number in the sentence that is not in the card is exactly
        # what wants catching: it came from somewhere neither of us can point at.
        evidence = json.dumps(payload, ensure_ascii=False, default=str)
    else:
        # No data behind it, because there is none to have: a refusal, a confirmation, a
        # greeting. These are approved fixed sentences, so the sentence is its own
        # evidence — which grounds nothing, and is why a separate test forbids approved
        # fixed text from carrying a figure at all. That test is the real guard here.
        evidence = answer

    return {"draft_answer": answer, "checkable_evidence": evidence}
