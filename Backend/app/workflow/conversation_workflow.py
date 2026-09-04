"""
The workflow, assembled.

One graph, matching the designed flow end to end:

    understand the question
      ├─ greeting                    -> greet
      ├─ out of scope                -> decline
      ├─ too vague                   -> ask back, PAUSE, then read it again
      ├─ about the last reply        -> rework that reply, no searching
      ├─ needs rewording or splitting-> reword and split, then route
      └─ clear enough                -> route

    route every part of the question
      ├─ policy                      -> search the policy documents
      ├─ the employee's own facts    -> read their record
      ├─ both                        -> do both
      └─ neither                     -> gather nothing for that part

    every part gathers at once, then the parts are put back in order

    write one answer covering every part -> check it
      ├─ passes                      -> show it with its sources
      └─ fails                       -> decline safely, sources still attached

A message asking two things is split once, in step 2B, and stays split from there:
each part is routed on its own and gathers on its own branch. That is what lets one
answer serve a part from the policy documents while declining another, instead of
answering the first thing asked and silently dropping the rest.

Nothing here is compiled when this module is imported. The graph is built once when the
application starts, so the place to save paused conversations can be handed to it. The two
graphs this replaces each compiled themselves at import time, which left nowhere to
inject one.
"""

import logging

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from app.workflow.conversation_state import ConversationState
from app.workflow.nodes.clarification import (
    compose_clarification_question,
    merge_clarification_into_question,
    wait_for_clarification,
)
from app.workflow.nodes.finish_turn import (
    build_safe_fallback,
    finalize_verified_answer,
    generate_document_upload_prompt,
    generate_greeting,
    record_conversation_turn,
)
from app.workflow.nodes.gather_evidence import assemble_evidence, gather_subquery_evidence
from app.workflow.nodes.generate_answer import generate_answer
from app.workflow.nodes.load_employee_facts import load_employee_facts
from app.workflow.nodes.rephrase_previous_answer import rephrase_previous_answer
from app.workflow.nodes.rewrite_and_decompose import rewrite_and_decompose_query
from app.workflow.nodes.route_subqueries import route_each_subquery
from app.workflow.nodes.understand_query import understand_query
from app.workflow.nodes.validate_answer import validate_answer
from app.workflow.routing_rules import (
    GATHER_EVIDENCE_FOR_ONE_PART,
    decide_after_understanding,
    decide_answer_validity,
    fan_out_to_each_subquery,
)

logger = logging.getLogger(__name__)


def build_conversation_workflow() -> StateGraph:
    """Lay out the steps and the branches between them. No side effects."""
    workflow = StateGraph(ConversationState)

    workflow.add_node("load_employee_facts", load_employee_facts)
    workflow.add_node("understand_query", understand_query)
    workflow.add_node("generate_greeting", generate_greeting)
    workflow.add_node("generate_document_upload_prompt", generate_document_upload_prompt)
    workflow.add_node("compose_clarification_question", compose_clarification_question)
    workflow.add_node("wait_for_clarification", wait_for_clarification)
    workflow.add_node("merge_clarification_into_question", merge_clarification_into_question)
    workflow.add_node("rephrase_previous_answer", rephrase_previous_answer)
    workflow.add_node("rewrite_and_decompose_query", rewrite_and_decompose_query)
    workflow.add_node("route_each_subquery", route_each_subquery)
    workflow.add_node(GATHER_EVIDENCE_FOR_ONE_PART, gather_subquery_evidence)
    workflow.add_node("assemble_evidence", assemble_evidence)
    workflow.add_node("generate_answer", generate_answer)
    workflow.add_node("validate_answer", validate_answer)
    workflow.add_node("finalize_verified_answer", finalize_verified_answer)
    workflow.add_node("build_safe_fallback", build_safe_fallback)
    workflow.add_node("record_conversation_turn", record_conversation_turn)

    workflow.add_edge(START, "load_employee_facts")
    workflow.add_edge("load_employee_facts", "understand_query")

    workflow.add_conditional_edges(
        "understand_query",
        decide_after_understanding,
        {
            "generate_greeting": "generate_greeting",
            "generate_document_upload_prompt": "generate_document_upload_prompt",
            "build_safe_fallback": "build_safe_fallback",
            "compose_clarification_question": "compose_clarification_question",
            "rephrase_previous_answer": "rephrase_previous_answer",
            "rewrite_and_decompose_query": "rewrite_and_decompose_query",
            "route_each_subquery": "route_each_subquery",
        },
    )

    # Ask the employee something, pause, then read their answer together with the
    # original question.
    workflow.add_edge("compose_clarification_question", "wait_for_clarification")
    workflow.add_edge("wait_for_clarification", "merge_clarification_into_question")
    workflow.add_edge("merge_clarification_into_question", "understand_query")

    workflow.add_edge("rewrite_and_decompose_query", "route_each_subquery")

    # One branch per part of the question, all running at the same time. They rejoin at
    # `assemble_evidence`, which does not run until every one of them has finished.
    workflow.add_conditional_edges(
        "route_each_subquery",
        fan_out_to_each_subquery,
        [GATHER_EVIDENCE_FOR_ONE_PART, "build_safe_fallback"],
    )

    workflow.add_edge(GATHER_EVIDENCE_FOR_ONE_PART, "assemble_evidence")
    workflow.add_edge("assemble_evidence", "generate_answer")
    workflow.add_edge("generate_answer", "validate_answer")

    # A reworked reply is checked like any other answer. It retrieves nothing, so it
    # supplies the reply it reworked as the evidence its figures are held against —
    # which is why it joins the graph here rather than going straight to the end the way
    # a greeting does. A greeting has nothing to check; this does.
    workflow.add_edge("rephrase_previous_answer", "validate_answer")

    workflow.add_conditional_edges(
        "validate_answer",
        decide_answer_validity,
        {
            "finalize_verified_answer": "finalize_verified_answer",
            "build_safe_fallback": "build_safe_fallback",
        },
    )

    workflow.add_edge("generate_greeting", "record_conversation_turn")
    workflow.add_edge("generate_document_upload_prompt", "record_conversation_turn")
    workflow.add_edge("finalize_verified_answer", "record_conversation_turn")
    workflow.add_edge("build_safe_fallback", "record_conversation_turn")
    workflow.add_edge("record_conversation_turn", END)

    return workflow


def compile_conversation_workflow(checkpointer: BaseCheckpointSaver):
    """Make the workflow runnable, saving its state as it goes."""
    compiled = build_conversation_workflow().compile(checkpointer=checkpointer)
    logger.info("The conversation workflow is ready")
    return compiled
