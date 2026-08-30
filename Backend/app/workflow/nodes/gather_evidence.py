"""
Step 4: collect the evidence each part of the question will be answered from.

Every part runs in its own branch, all of them at once, so a message asking three things
costs one round of searching rather than three. A branch writes only what it found;
`assemble_evidence` waits for them all and puts the parts back in order.
"""

import logging

from app.core.settings import settings

from app.core.errors import PolicyIndexEmptyError
from app.domain.employee_facts import EmployeeFacts
from app.domain.enums import RequiredEvidence
from app.services.policy_search_service import search_policies
from app.workflow.conversation_state import ConversationState, SubqueryTask
from app.workflow.evidence_formatting import (
    build_checkable_evidence,
    build_evidence_block,
    format_employee_facts,
)

logger = logging.getLogger(__name__)

PASSAGES_TO_RETRIEVE = settings.rag_top_k
FEWEST_USEFUL_PASSAGES = 2
# How close the best match has to be before a language-filtered search is trusted.
# Compared against the vector similarity, not the displayed relevance: the displayed
# number comes from rank position, so even the worst result in a bad set scores highly.
CLOSE_ENOUGH_TO_TRUST = 0.35


def gather_subquery_evidence(task: SubqueryTask) -> dict:
    """
    One part of the question, gathered on a branch of its own.

    Steps 4A and 4B both run here, one after the other, because 4B only reads a record
    that is already in memory — there is no second round trip to overlap with the search.
    The parts running beside each other are where the real waiting is saved.
    """
    required_evidence = task["required_evidence"]
    wants_policy = required_evidence in (RequiredEvidence.POLICY, RequiredEvidence.BOTH)
    wants_hr_data = required_evidence in (RequiredEvidence.HR_DATA, RequiredEvidence.BOTH)

    passages = _search_policy_documents(task) if wants_policy else []
    authorised_fields = task["requested_hr_data_fields"] if wants_hr_data else []
    employee_facts_text = _read_hr_data(task, authorised_fields) if wants_hr_data else ""

    return {
        "subquery_evidence": [
            {
                "index": task["index"],
                "question": task["question"],
                "required_evidence": required_evidence,
                "requested_hr_data_fields": authorised_fields,
                "policy_passages": [passage.as_dictionary() for passage in passages],
                "employee_facts_text": employee_facts_text,
            }
        ]
    }


def _search_policy_documents(task: SubqueryTask) -> list:
    """
    Step 4A: find the policy extracts that bear on this part.

    When a language-filtered search comes back thin, or comes back with nothing that
    resembles the question, the search is repeated without the filter. Not every policy
    is published in every language, so a question about one that is not should be
    answered from the edition that exists rather than refused.

    The second condition is the one that matters. This used to test only how *many*
    passages came back, and the Arabic side of the index was full of passages holding no
    Arabic at all — enough of them to fill every result slot, so the fallback never fired
    and the answer was built from nonsense. Counting results says nothing about whether
    any of them is about the question.
    """
    query = task["question"]
    requested_language = task.get("requested_language", "en")

    try:
        passages = search_policies(query=query, top_k=PASSAGES_TO_RETRIEVE, language=requested_language)

        if _too_little_to_answer_from(passages):
            logger.info(
                f"Nothing close enough in {requested_language} "
                f"({len(passages)} passages, best {_closest_match(passages):.2f}); "
                f"searching across all languages instead"
            )
            passages = search_policies(query=query, top_k=PASSAGES_TO_RETRIEVE, language=None)
    except PolicyIndexEmptyError:
        logger.warning("The policy index is empty, so no extracts could be retrieved")
        passages = []

    logger.info(f"Part {task['index']} retrieved {len(passages)} policy extracts")
    return passages


def _too_little_to_answer_from(passages: list) -> bool:
    """Too few results, or none of them close enough to the question to be worth reading."""
    return (
        len(passages) < FEWEST_USEFUL_PASSAGES
        or _closest_match(passages) < CLOSE_ENOUGH_TO_TRUST
    )


def _closest_match(passages: list) -> float:
    """How close the best passage actually is to the question."""
    return max((passage.semantic_similarity for passage in passages), default=0.0)


def _read_hr_data(task: SubqueryTask, authorised_fields: list[str]) -> str:
    """
    Step 4B: read the employee's own facts — only the ones the routing step authorised.

    This reads from the record already loaded at the start of the turn. There is no query
    to build and no way to reach any other employee's data.
    """
    facts = EmployeeFacts.from_dictionary(task["employee_facts"])
    logger.info(
        f"Part {task['index']} read {len(authorised_fields)} authorised fields "
        f"from the employee record"
    )
    return format_employee_facts(facts, authorised_fields)


def assemble_evidence(state: ConversationState) -> dict:
    """
    Put the parts back in order and write out the evidence the answer is built from.

    A part routed as unsupported never started a branch, so it arrives here with nothing
    against it. It is still listed: step 5 has to see the part it cannot answer in order
    to say so, rather than quietly leaving the employee's question half addressed.
    """
    plans = state.get("subquery_plans") or []
    findings_by_part = {
        finding["index"]: finding for finding in (state.get("subquery_evidence") or [])
    }

    parts: list[dict] = []
    merged_passages: list[dict] = []
    already_cited: set[tuple] = set()
    authorised_fields: list[str] = []

    for plan in plans:
        finding = findings_by_part.get(plan["index"], {})
        passages = finding.get("policy_passages") or []
        fields = finding.get("requested_hr_data_fields") or []

        parts.append(
            {
                "index": plan["index"],
                "question": plan["question"],
                "required_evidence": plan["required_evidence"],
                "employee_facts_text": finding.get("employee_facts_text", ""),
                "policy_passages": passages,
                "has_evidence": bool(passages) or bool(fields),
            }
        )

        for passage in passages:
            # The same extract can be the best match for two parts of one question. It is
            # worth reading once and citing once.
            origin = (passage.get("source"), passage.get("section"), passage.get("page_number"))
            if origin in already_cited:
                continue
            already_cited.add(origin)
            merged_passages.append(passage)

        for field in fields:
            if field not in authorised_fields:
                authorised_fields.append(field)

    facts = state.get("employee_facts") or {}
    merged_facts_text = (
        format_employee_facts(EmployeeFacts.from_dictionary(facts), authorised_fields)
        if authorised_fields
        else ""
    )

    answered = sum(1 for part in parts if part["has_evidence"])
    if len(parts) > 1:
        logger.info(f"Gathered evidence for {answered} of {len(parts)} parts")

    return {
        "subquery_statuses": [
            {
                "index": part["index"],
                "question": part["question"],
                "required_evidence": part["required_evidence"],
                "has_evidence": part["has_evidence"],
            }
            for part in parts
        ],
        "policy_passages": merged_passages,
        "hr_data_facts": {"fields": authorised_fields, "formatted": merged_facts_text},
        "evidence_summary": build_evidence_block(parts),
        # The same evidence without the questions, because the questions are not
        # evidence — see build_checkable_evidence.
        "checkable_evidence": build_checkable_evidence(parts),
    }
