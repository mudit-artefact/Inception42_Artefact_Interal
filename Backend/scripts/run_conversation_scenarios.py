"""
Runs every scenario through the real assistant as one conversation, and grades every turn.

The benchmark runner next door puts each question to a fresh conversation and grades the
last turn of a case. This does the opposite: one conversation per scenario, held open
across every turn, with each turn graded on its own expectations. What that finds and the
other cannot is everything that only goes wrong in context — a follow-up bound to the
wrong antecedent, a version boundary answered correctly on its own and wrongly three turns
later, one half of a two-part message dropped without trace.

Grading is deterministic even though the answers are not: the comparisons live in
`app/evaluation/grading.py` and are shared with the benchmark runner, so the two cannot
develop different ideas about whether "AED 450.0" states the fact "450".

A turn carrying `known_gap` describes something the system has never been able to do. It
is scored as a gap rather than a failure and left out of the headline count, so a missing
capability does not read as a regression.

    python scripts/run_conversation_scenarios.py
    python scripts/run_conversation_scenarios.py --only S3 S4
    python scripts/run_conversation_scenarios.py --dimension reasoning_type
    python scripts/run_conversation_scenarios.py --markdown
"""

import argparse
import logging
import sys
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.evaluation.grading import contains_fact, looks_like_a_refusal  # noqa: E402

PASS, FAIL, GAP = "PASS", "FAIL", "GAP"

DIMENSIONS = {
    "source_type": ("By where the answer must come from", lambda turn: turn.source_type),
    "reasoning_type": ("By what has to be done with it", lambda turn: turn.reasoning_type),
    "conversation_type": ("By the shape of the exchange", lambda turn: turn.conversation_type),
    "modality": ("By language and form", lambda turn: turn.modality),
}


@dataclass
class TurnOutcome:
    """What happened when one turn was put to the assistant."""

    scenario_id: str
    position: int          # 1-based, within the scenario
    turn: object
    verdict: str
    answer: str = ""
    reasons: list[str] = field(default_factory=list)
    cited: list[str] = field(default_factory=list)
    intent: str = ""
    seconds: float = 0.0
    awaiting_clarification: bool = False

    @property
    def label(self) -> str:
        return f"{self.scenario_id}.{self.position}"


# One retry, on server errors only. A single 500 from an overloaded model API used to end
# the whole scenario and take the four turns after it with it — so a transient blip cost
# more measurement than the failure it represented. A 4xx is not retried: that is our bug,
# and repeating it only hides it.
RETRY_AFTER_SECONDS = 5


def ask(client, question: str, employee_id: str, conversation_id: str) -> dict:
    for attempt in (1, 2):
        response = client.post(
            "/api/v1/hcs01/query",
            json={"query": question, "employee_id": employee_id,
                  "conversation_id": conversation_id},
        )
        if response.status_code < 500 or attempt == 2:
            response.raise_for_status()
            return response.json()
        print(f"       server error {response.status_code}, retrying once…")
        time.sleep(RETRY_AFTER_SECONDS)
    raise AssertionError("unreachable")


def grade(outcome: TurnOutcome) -> None:
    """Score one reply against what the turn said a correct one contains."""
    turn = outcome.turn

    if turn.should_ask_clarification:
        if not outcome.awaiting_clarification:
            outcome.verdict = FAIL
            outcome.reasons.append("did not ask anything back")
        return

    if turn.should_abstain:
        if not looks_like_a_refusal(outcome.answer, outcome.intent):
            outcome.verdict = FAIL
            outcome.reasons.append("answered instead of declining")
    else:
        missing = [fact for fact in turn.expected_facts
                   if not contains_fact(outcome.answer, fact)]
        if missing:
            outcome.verdict = FAIL
            outcome.reasons.append(f"missing: {missing}")

        wanted = set(turn.expected_doc_sources)
        if wanted and turn.minimum_hops > 1:
            found = wanted & set(outcome.cited)
            if len(found) < turn.minimum_hops:
                outcome.verdict = FAIL
                outcome.reasons.append(
                    f"cited {sorted(found) or 'none of them'} of {sorted(wanted)}"
                )

    # Checked whether or not the turn was meant to be answered: an abstention that
    # nonetheless leaks the figure it was declining to give is not an abstention.
    stated = [fact for fact in turn.forbidden_facts if contains_fact(outcome.answer, fact)]
    if stated:
        outcome.verdict = FAIL
        outcome.reasons.append(f"stated what it must not: {stated}")


def run_scenario(client, scenario, run_token: str) -> list[TurnOutcome]:
    """
    Hold one conversation from start to finish, grading as it goes.

    The conversation id carries a per-run token. Checkpoints are persisted in
    `data/conversation_checkpoints.sqlite`, so a fixed id would make the second run of a
    scenario resume the first run's memory and grade a conversation nobody had.
    """
    conversation = f"scenario-{scenario.id}-{run_token}"
    outcomes: list[TurnOutcome] = []

    for position, turn in enumerate(scenario.turns, start=1):
        outcome = TurnOutcome(scenario_id=scenario.id, position=position, turn=turn,
                              verdict=PASS)
        started = time.time()
        try:
            body = ask(client, turn.query, scenario.employee_id, conversation)
        except Exception as error:  # a crash is a result too
            outcome.seconds = time.time() - started
            outcome.verdict = FAIL
            outcome.reasons.append(f"{type(error).__name__}: {str(error)[:160]}")
            outcomes.append(outcome)
            # The conversation is now in an unknown state, so the later turns would be
            # graded against context that never happened.
            break

        outcome.seconds = time.time() - started
        outcome.answer = body.get("answer", "")
        outcome.intent = body.get("intent", "")
        outcome.awaiting_clarification = bool(body.get("is_awaiting_clarification"))
        outcome.cited = sorted({source.get("source", "") for source in body.get("sources", [])})

        grade(outcome)
        if turn.known_gap:
            # Always a gap, never a pass. Declining gracefully is the best available
            # outcome and it is still not the capability, so counting it as a pass would
            # report the taxonomy as covered when one cell of it is unreachable.
            if outcome.verdict == PASS:
                outcome.reasons.append("declined cleanly — the capability is still absent")
            outcome.verdict = GAP

        outcomes.append(outcome)

    return outcomes


def breakdown(outcomes: list[TurnOutcome], title: str, of) -> None:
    """A pass rate per value of one taxonomy dimension, over turns rather than cases."""
    counts: dict = defaultdict(lambda: [0, 0])
    for outcome in outcomes:
        if outcome.verdict == GAP:
            continue
        value = of(outcome.turn)
        if value is None:
            continue
        counts[str(value)][1] += 1
        if outcome.verdict == PASS:
            counts[str(value)][0] += 1

    print(f"\n{title}")
    for value in sorted(counts):
        good, total = counts[value]
        print(f"  {value:16} {good}/{total}  {'█' * good}{'░' * (total - good)}")


def report(scenarios, outcomes: list[TurnOutcome], dimension: str | None) -> None:
    graded = [o for o in outcomes if o.verdict != GAP]
    passed = [o for o in graded if o.verdict == PASS]
    failed = [o for o in graded if o.verdict == FAIL]
    gaps = [o for o in outcomes if o.verdict == GAP]

    print("\n" + "=" * 78)
    print(f"{len(passed)}/{len(graded)} turns passed   {len(failed)} failed"
          f"   {len(gaps)} not supported at all")
    print("=" * 78)

    print("\nBy scenario")
    by_scenario = {scenario.id: scenario for scenario in scenarios}
    for scenario_id in [s.id for s in scenarios]:
        mine = [o for o in graded if o.scenario_id == scenario_id]
        if not mine:
            continue
        good = sum(1 for o in mine if o.verdict == PASS)
        print(f"  {scenario_id:4} {good}/{len(mine)}  {'█' * good}{'░' * (len(mine) - good)}"
              f"  {by_scenario[scenario_id].title}")

    wanted = [dimension] if dimension else list(DIMENSIONS)
    for name in wanted:
        title, of = DIMENSIONS[name]
        breakdown(outcomes, title, of)

    if failed:
        print("\n" + "-" * 78)
        print("FAILURES")
        print("-" * 78)
        for outcome in failed:
            turn = outcome.turn
            tags = f"{turn.source_type}/{turn.reasoning_type}"
            if turn.conversation_type:
                tags += f"/{turn.conversation_type}"
            print(f"\n{outcome.label}  [{tags}]  {outcome.seconds:.1f}s")
            print(f'  asked    : "{turn.query}"')
            for reason in outcome.reasons:
                print(f"  problem  : {reason}")
            if turn.failure_mode:
                print(f"  expected : {' '.join(turn.failure_mode.split())[:200]}")
            print(f"  cited    : {outcome.cited or 'nothing'}")
            print(f"  answered : {' '.join(outcome.answer.split())[:260]}")

    if gaps:
        print("\n" + "-" * 78)
        print("NOT SUPPORTED BY THE SYSTEM AT ALL")
        print("-" * 78)
        for outcome in gaps:
            print(f"\n{outcome.label}  \"{outcome.turn.query}\"")
            print(f"  why  : {' '.join((outcome.turn.known_gap or '').split())}")
            for reason in outcome.reasons:
                print(f"  saw  : {reason}")


def markdown(scenarios, outcomes: list[TurnOutcome]) -> None:
    """A results table for the log at the end of CONVERSATION_SCENARIOS.md."""
    marks = {PASS: "pass", FAIL: "**FAIL**", GAP: "gap"}
    print("\n" + "-" * 78)
    print("MARKDOWN")
    print("-" * 78 + "\n")
    print("| Turn | Taxonomy | Result | Note |")
    print("|---|---|---|---|")
    for outcome in outcomes:
        turn = outcome.turn
        tags = f"{turn.source_type} / {turn.reasoning_type}"
        if turn.conversation_type:
            tags += f" / {turn.conversation_type}"
        note = "; ".join(outcome.reasons).replace("|", "\\|")[:120]
        print(f"| {outcome.label} | {tags} | {marks[outcome.verdict]} | {note} |")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="*", help="run just these scenario ids, e.g. S3 S4")
    parser.add_argument("--dimension", choices=sorted(DIMENSIONS),
                        help="show only one taxonomy breakdown")
    parser.add_argument("--markdown", action="store_true",
                        help="also print a results table to paste into the document")
    arguments = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)
    for noisy in ("httpx", "LiteLLM", "litellm"):
        logging.getLogger(noisy).setLevel(logging.ERROR)

    from fastapi.testclient import TestClient

    from app.evaluation.scenario_cases import CONVERSATION_SCENARIOS
    from app.main import app

    scenarios = CONVERSATION_SCENARIOS
    if arguments.only:
        wanted = {name.upper() for name in arguments.only}
        scenarios = [s for s in scenarios if s.id.upper() in wanted]
        if not scenarios:
            print(f"No scenario matches {sorted(wanted)}.")
            return 1

    turn_count = sum(len(s.turns) for s in scenarios)
    print(f"Holding {len(scenarios)} conversations, {turn_count} turns. "
          f"Starting the assistant first…")

    run_token = uuid.uuid4().hex[:8]
    outcomes: list[TurnOutcome] = []

    with TestClient(app) as client:
        for scenario in scenarios:
            print(f"\n{scenario.id}  {scenario.title}   (as {scenario.employee_id})")
            for outcome in run_scenario(client, scenario, run_token):
                outcomes.append(outcome)
                mark = {PASS: "ok  ", FAIL: "FAIL", GAP: "gap "}[outcome.verdict]
                print(f"  [{outcome.position:2}/{len(scenario.turns)}] {mark} "
                      f"{outcome.turn.query[:62]}")

    report(scenarios, outcomes, arguments.dimension)
    if arguments.markdown:
        markdown(scenarios, outcomes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
