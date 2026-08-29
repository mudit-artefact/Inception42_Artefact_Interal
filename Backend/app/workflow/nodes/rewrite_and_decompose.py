"""
Step 2B: reword the question, and split it into the things it actually asks.

Rewording and splitting are one model call rather than two. They need the same reading of
the message — what it refers to, what it abbreviates, where one question ends and the
next begins — so asking twice would pay twice for the same work and risk the two answers
disagreeing.
"""

import logging

from app.workflow.conversation_memory import describe_the_conversation_so_far
from app.workflow.conversation_state import ConversationState
from app.workflow.language_model_client import generate_structured_output
from app.workflow.prompts import QUERY_DECOMPOSITION_INSTRUCTIONS
from app.workflow.structured_outputs import DecomposedQuery

logger = logging.getLogger(__name__)

MOST_PARTS_WORTH_ANSWERING = 5


def rewrite_and_decompose_query(state: ConversationState) -> dict:
    """
    Produce the standalone parts this question will be searched and routed by.

    A message asking one thing comes back as a single part, which is exactly the reworded
    query this step used to return before it could split anything.
    """
    question = state["employee_question"]

    decomposed = generate_structured_output(
        messages=[
            {"role": "system", "content": QUERY_DECOMPOSITION_INSTRUCTIONS},
            {"role": "user", "content": _describe_the_turn_for_search(state)},
        ],
        output_model=DecomposedQuery,
    )

    subqueries = _usable_parts(decomposed.subqueries) or [question]

    if len(subqueries) > 1:
        logger.info(f"Split into {len(subqueries)} parts: {subqueries}")
    else:
        logger.info(f"Search query: '{subqueries[0][:60]}'")

    return {
        "subqueries": subqueries,
        # What the interface shows as the query that was actually searched for. With one
        # part this is the reworded question; with several it is all of them.
        "retrieval_query": " | ".join(subqueries),
    }


def _describe_the_turn_for_search(state: ConversationState) -> str:
    """
    The message to prepare, together with whatever it may be referring back to.

    Without the conversation, "what about sick leave?" is correctly spotted as needing a
    rewrite and then rewritten against nothing — the step could only guess what "what
    about" stood for.
    """
    asked = f'Prepare this for policy search: "{state["employee_question"]}"'

    conversation_so_far = describe_the_conversation_so_far(state.get("remembered_turns"))
    if not conversation_so_far:
        return asked
    return f"{conversation_so_far}\n\n{asked}"


def _usable_parts(subqueries: list[str]) -> list[str]:
    """
    Drop blanks and repeats, and stop at a sensible number.

    A model that splits a rambling message into a dozen parts would otherwise start a
    dozen searches, and every part after the first few is almost always a restatement of
    an earlier one.
    """
    kept: list[str] = []
    for subquery in subqueries:
        cleaned = (subquery or "").strip()
        if not cleaned or cleaned.casefold() in {kept_part.casefold() for kept_part in kept}:
            continue
        kept.append(cleaned)
        if len(kept) == MOST_PARTS_WORTH_ANSWERING:
            logger.info(f"Keeping only the first {MOST_PARTS_WORTH_ANSWERING} parts")
            break
    return kept
