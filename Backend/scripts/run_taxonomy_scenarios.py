"""
Runs every benchmark case through the real assistant and grades the answer.

The benchmark that ships with the application scores retrieval only — did the right
document come back — because it runs without a language model and has to stay free and
deterministic. That measures the library, not the librarian. This runs the whole thing:
the real workflow, the real model, the real employee records, one conversation per case.

Grading is deterministic even though the answers are not. A case names the facts its
answer must contain and, where it matters, the facts it must NOT — the figure that was
replaced by the one being asked about, or a colleague's balance. Matching for those is
plain text comparison, so nothing here needs a model to judge a model.

    python scripts/run_taxonomy_scenarios.py
    python scripts/run_taxonomy_scenarios.py --only TC-02 TC-16
    python scripts/run_taxonomy_scenarios.py --dimension reasoning_type
"""

import argparse
import logging
import re
import sys
import time
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PASS, FAIL, GAP = "PASS", "FAIL", "GAP"


@dataclass
class Outcome:
    """What happened when one case was put to the assistant."""

    case_id: str
    verdict: str
    case: object
    answer: str = ""
    reasons: list[str] = field(default_factory=list)
    cited: list[str] = field(default_factory=list)
    intent: str = ""
    seconds: float = 0.0
    awaiting_clarification: bool = False


def _flatten(text: str) -> str:
    """Comparable text: one line, normalised Arabic, lowercase."""
    return " ".join(unicodedata.normalize("NFKC", text or "").split()).lower()


def _as_a_number(text: str) -> str:
    """450, 450.0 and 450 are one figure. Matches how the answer check compares them."""
    try:
        return f"{float(text.replace(',', '')):g}"
    except ValueError:
        return text


def contains_fact(answer: str, fact: str) -> bool:
    """
    Whether the answer states a fact the case requires.

    A bare number is compared as a number, not as text. "450" is stated by an answer
    saying "AED 450.0", and is not stated by one that only mentions 2450 — matching on
    the characters gets both of those wrong, in opposite directions.
    """
    haystack, needle = _flatten(answer), _flatten(fact)
    if not needle:
        return True

    if re.fullmatch(r"[\d,.]+", needle):
        wanted = _as_a_number(needle)
        return any(
            _as_a_number(found) == wanted
            for found in re.findall(r"\d[\d,]*(?:\.\d+)?", haystack)
        )
    return needle in haystack


def looks_like_a_refusal(answer: str, intent: str) -> bool:
    """
    Whether the assistant declined rather than answered.

    The wire response carries `intent` but not the internal answer status, so an
    out-of-scope refusal is visible directly and every other kind is recognised by what
    the fixed messages actually say.
    """
    if intent == "not_in_scope":
        return True
    declining = [
        "cannot assist", "outside", "not able to", "contact people & culture",
        "people@hcservices.ae", "not yet published", "in drafting", "cannot provide",
        "i do not have", "unable to",
    ]
    flattened = _flatten(answer)
    return any(phrase in flattened for phrase in declining)


def ask(client, question: str, employee_id: str, conversation_id: str) -> dict:
    response = client.post(
        "/api/v1/hcs01/query",
        json={"query": question, "employee_id": employee_id, "conversation_id": conversation_id},
    )
    response.raise_for_status()
    return response.json()


def run_case(client, case) -> Outcome:
    """Put one case to the assistant, in its own conversation, and grade the reply."""
    outcome = Outcome(case_id=case.id, verdict=PASS, case=case)

    conversation = f"scenario-{case.id}"
    started = time.time()

    # A multi-turn case is graded on its last turn; the earlier ones set the context.
    turns = [turn.query for turn in case.turns] or [case.query]
    final_facts = (case.turns[-1].expected_facts if case.turns else []) or case.expected_facts

    body = {}
    for question in turns:
        body = ask(client, question, case.employee_id, conversation)

    outcome.seconds = time.time() - started
    outcome.answer = body.get("answer", "")
    outcome.intent = body.get("intent", "")
    outcome.awaiting_clarification = bool(body.get("is_awaiting_clarification"))
    outcome.cited = sorted({source.get("source", "") for source in body.get("sources", [])})

    if case.should_ask_clarification and not case.turns:
        if not outcome.awaiting_clarification:
            outcome.verdict = FAIL
            outcome.reasons.append("did not ask anything back")
        return outcome

    if case.should_abstain:
        if not looks_like_a_refusal(outcome.answer, outcome.intent):
            outcome.verdict = FAIL
            outcome.reasons.append("answered instead of declining")
    else:
        missing = [fact for fact in final_facts if not contains_fact(outcome.answer, fact)]
        if missing:
            outcome.verdict = FAIL
            outcome.reasons.append(f"missing: {missing}")

        wanted = set(case.expected_doc_sources)
        if wanted and case.minimum_hops > 1:
            found = wanted & set(outcome.cited)
            if len(found) < case.minimum_hops:
                outcome.reasons.append(
                    f"cited {sorted(found) or 'nothing expected'} of {sorted(wanted)}"
                )
                outcome.verdict = FAIL

    stated = [fact for fact in case.forbidden_facts if contains_fact(outcome.answer, fact)]
    if stated:
        outcome.verdict = FAIL
        outcome.reasons.append(f"stated what it must not: {stated}")

    return outcome


def report(outcomes: list[Outcome]) -> None:
    from app.domain.enums import ConversationType, Modality, ReasoningType, SourceType

    passed = [o for o in outcomes if o.verdict == PASS]
    failed = [o for o in outcomes if o.verdict == FAIL]
    gaps = [o for o in outcomes if o.verdict == GAP]

    print("\n" + "=" * 78)
    print(f"{len(passed)}/{len(outcomes)} passed   {len(failed)} failed   {len(gaps)} not supported")
    print("=" * 78)

    def breakdown(title: str, of) -> None:
        print(f"\n{title}")
        counts: dict = defaultdict(lambda: [0, 0])
        for outcome in outcomes:
            value = of(outcome.case)
            if value is None:
                continue
            counts[str(value)][1] += 1
            if outcome.verdict == PASS:
                counts[str(value)][0] += 1
        for value in sorted(counts):
            good, total = counts[value]
            bar = "█" * good + "░" * (total - good)
            print(f"  {value:16} {good}/{total}  {bar}")

    breakdown("By where the answer must come from", lambda c: c.source_type)
    breakdown("By what has to be done with it", lambda c: c.reasoning_type)
    breakdown("By the shape of the exchange", lambda c: c.conversation_type)
    breakdown("By language and form", lambda c: c.modality)

    if failed:
        print("\n" + "-" * 78)
        print("FAILURES")
        print("-" * 78)
        for outcome in failed:
            case = outcome.case
            tags = f"{case.source_type}/{case.reasoning_type}"
            if case.conversation_type:
                tags += f"/{case.conversation_type}"
            print(f"\n{outcome.case_id}  [{tags}]  as {case.employee_id}  {outcome.seconds:.1f}s")
            print(f'  asked   : "{case.query}"')
            for reason in outcome.reasons:
                print(f"  problem : {reason}")
            print(f"  cited   : {outcome.cited or 'nothing'}")
            answer = " ".join(outcome.answer.split())
            print(f"  answered: {answer[:260]}")

    if gaps:
        print("\n" + "-" * 78)
        print("NOT SUPPORTED BY THE SYSTEM AT ALL")
        print("-" * 78)
        for outcome in gaps:
            print(f"  {outcome.case_id}  {outcome.reasons[0]}")

    print("\n" + "-" * 78)
    print("UNCOVERED BY ANY SCENARIO")
    print("-" * 78)
    print("  Scan  — evidence on a scanned or image-only page. Nothing in this system")
    print("          reads an image: pages are read with a text extractor only, so no")
    print("          scenario can exercise it and none is written. It is a missing")
    print("          capability, not a failing test.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="*", help="run just these case ids")
    arguments = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)
    for noisy in ("httpx", "LiteLLM", "litellm"):
        logging.getLogger(noisy).setLevel(logging.ERROR)

    from fastapi.testclient import TestClient

    from app.evaluation.benchmark_cases import GOLDEN_BENCHMARK_CASES
    from app.main import app

    cases = GOLDEN_BENCHMARK_CASES
    if arguments.only:
        wanted = set(arguments.only)
        cases = [case for case in cases if case.id in wanted]

    print(f"Putting {len(cases)} scenarios to the assistant. Starting it up first…")
    outcomes: list[Outcome] = []

    with TestClient(app) as client:
        for position, case in enumerate(cases, start=1):
            try:
                outcome = run_case(client, case)
            except Exception as error:  # a crash is a result too
                outcome = Outcome(case_id=case.id, verdict=FAIL, case=case,
                                  reasons=[f"{type(error).__name__}: {str(error)[:160]}"])
            outcomes.append(outcome)
            mark = {PASS: "ok  ", FAIL: "FAIL", GAP: "gap "}[outcome.verdict]
            print(f"  [{position:2}/{len(cases)}] {mark} {case.id:8} {case.query[:58]}")

    report(outcomes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
