"""
What the employee is told while they wait.

Answers take the better part of a minute, and for most of it the interface used to show
nothing. These are the lines that fill that time. They are not a progress bar: each one
names a real step the workflow has just finished, so what the employee reads is what the
system actually did — the record was read, these clauses were found, every figure was
checked. That is the part worth showing, because it is the part that separates this from
a search box.

Node names never reach the wire. "route_each_subquery" means nothing to anybody outside
this repository, and a stage line that leaks it is a bug.
"""

from typing import Optional

from app.domain.enums import RequiredEvidence

# What follows each node, so the line on screen names the work happening now rather than
# the work already finished.
#
# LangGraph reports a node when it completes, and the steps that take time are the model
# calls. Labelling the node that just finished put the wrong sentence on screen for the
# whole of every wait: "Reading your record" sat there for thirty-two seconds while the
# question was being understood. Showing what comes next is what makes the line true.
#
# Branches are self-correcting. A question that turns out to need clarification is
# briefly labelled as being looked up, and the next event a moment later says otherwise.
NEXT_AFTER: dict[str, str] = {
    "load_employee_facts": "understand_query",
    "understand_query": "rewrite_and_decompose_query",
    "rewrite_and_decompose_query": "route_each_subquery",
    "route_each_subquery": "gather_subquery_evidence",
    "gather_subquery_evidence": "assemble_evidence",
    "assemble_evidence": "generate_answer",
    "generate_answer": "validate_answer",
    "merge_clarification_into_question": "understand_query",
}

# The line to show the moment the stream opens, before any node has finished.
FIRST_STAGE = "load_employee_facts"

# node name -> (step, English, Arabic). A node absent from here says nothing, which is
# the right behaviour for the bookkeeping ones.
STAGES: dict[str, tuple[str, str, str]] = {
    "load_employee_facts": ("record", "Reading your record", "أقرأ سجلك الوظيفي"),
    "understand_query": ("understand", "Understanding the question", "أفهم سؤالك"),
    "rewrite_and_decompose_query": ("split", "Working out what to look for", "أحدد ما أبحث عنه"),
    "route_each_subquery": ("route", "Deciding where the answer comes from", "أحدد مصدر الإجابة"),
    "gather_subquery_evidence": ("search", "Searching the policy documents", "أبحث في وثائق السياسات"),
    "assemble_evidence": ("assemble", "Gathering the evidence", "أجمع الأدلة"),
    "generate_answer": ("write", "Writing the answer", "أصيغ الإجابة"),
    "validate_answer": ("check", "Checking every figure against the evidence",
                        "أتحقق من كل رقم مقابل الأدلة"),
    "compose_clarification_question": ("ask", "One thing I need to check with you",
                                       "أحتاج أن أتحقق من أمر معك"),
    "rephrase_previous_answer": ("rework", "Reworking my last answer", "أعيد صياغة إجابتي السابقة"),
}

WHERE_THE_ANSWER_COMES_FROM = {
    RequiredEvidence.POLICY.value: ("Reading the policy documents", "أقرأ وثائق السياسات"),
    RequiredEvidence.HR_DATA.value: ("Reading your record", "أقرأ سجلك"),
    RequiredEvidence.BOTH.value: ("Reading your record against the policy documents",
                                  "أقارن سجلك بوثائق السياسات"),
}


def describe_stage(node_name: str, update: dict, language: str = "en") -> Optional[dict]:
    """
    The line to show now that this node has finished, or None when there is nothing to say.

    Two things are being reported at once and they belong to different nodes. The *detail*
    comes from the node that just finished — which clauses it found, how many parts it
    split the question into. The *sentence* names what happens next, because that is what
    the employee is now waiting for.

    `update` is the finished node's own contribution to the state, which is where the
    detail worth showing lives.
    """
    detail = _detail_from(node_name, update or {}, language)
    stage = STAGES.get(NEXT_AFTER.get(node_name, ""))
    if stage is None:
        # Nothing follows this node — the run is ending, or it is one of the bookkeeping
        # steps. Detail is only worth sending on its own when it carries a sentence: an
        # event with clauses and no line to show is one the interface cannot render.
        return detail if detail.get("text") else None

    step, in_english, in_arabic = stage
    event = {"step": step, "text": in_arabic if language == "ar" else in_english}
    if detail and detail.get("found"):
        event["found"] = detail["found"]
    if detail and detail.get("text"):
        event["text"] = detail["text"]
    return event


def opening_stage(language: str = "en") -> dict:
    """The line shown the instant the stream opens, before any node has finished."""
    step, in_english, in_arabic = STAGES[FIRST_STAGE]
    return {"step": step, "text": in_arabic if language == "ar" else in_english}


def _detail_from(node_name: str, update: dict, language: str) -> dict:
    """
    What the finished node is worth saying about itself.

    Kept apart from the sentence because the two describe different steps: the clauses
    belong to the search that just ran, while the sentence names what is running now.
    """
    if node_name == "rewrite_and_decompose_query":
        parts = update.get("subqueries") or []
        if len(parts) > 1:
            return {"text": (
                f"هذه {len(parts)} أسئلة — سأجيب عنها جميعاً" if language == "ar"
                else f"That is {len(parts)} questions — answering each one"
            )}

    if node_name == "route_each_subquery":
        described = WHERE_THE_ANSWER_COMES_FROM.get(update.get("required_evidence") or "")
        if described:
            return {"text": described[1] if language == "ar" else described[0]}

    if node_name == "gather_subquery_evidence":
        found = _clauses_in(update)
        if found:
            return {"found": found}

    return {}


def _clauses_in(update: dict) -> list[str]:
    """
    The clauses a search step turned up, named the way the citation drawer names them.

    Duplicates are dropped and order is kept: a question split into parts searches more
    than once, and the same clause answering two parts is one finding, not two.
    """
    found: list[str] = []
    for piece in update.get("subquery_evidence") or []:
        for passage in piece.get("policy_passages") or []:
            clause = (passage.get("clause_id") or "").replace("§", " §")
            if clause and clause not in found:
                found.append(clause)
    return found
