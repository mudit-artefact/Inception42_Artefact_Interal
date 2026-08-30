"""
The streaming endpoint and the plain one must answer the same question the same way.

They are two routes into one workflow, and the whole evaluation harness — the 58
scenarios, every measurement taken today — runs through the plain one. If the interface
quietly starts behaving differently from the thing being measured, the measurement stops
meaning anything, and nobody finds out until a demo.

So the interesting property is not that streaming works. It is that streaming changes
nothing.
"""

from tests.streaming.conftest import read_events


def ask_both_ways(client, question: str, employee_id: str = "EMP001"):
    """The same question down each route, in conversations of its own."""
    plain = client.post(
        "/api/v1/hcs01/query",
        json={"query": question, "employee_id": employee_id, "conversation_id": "plain"},
    ).json()

    with client.stream(
        "POST",
        "/api/v1/hcs01/query/stream",
        json={"query": question, "employee_id": employee_id, "conversation_id": "streamed"},
    ) as response:
        events = read_events(response)

    return plain, events


def only(events, name: str) -> list[dict]:
    return [payload for kind, payload in events if kind == name]


def test_both_routes_give_the_same_answer(
    client, script_understanding, script_routing, fake_language_model
):
    script_understanding()
    script_routing(required_evidence="policy")
    fake_language_model.reply_to_plain_call("Carry-over is capped at 10 days.")

    plain, events = ask_both_ways(client, "What is the carry-over limit?")
    finished = only(events, "done")[0]

    assert finished["answer"] == plain["answer"]
    assert finished["intent"] == plain["intent"]
    assert len(finished["sources"]) == len(plain["sources"])


def test_the_streamed_pieces_rebuild_the_answer_exactly(
    client, script_understanding, script_routing, fake_language_model
):
    """A word lost or duplicated in the chunking would be invisible until someone read it."""
    script_understanding()
    script_routing(required_evidence="policy")
    fake_language_model.reply_to_plain_call(
        "Carry-over is capped at 10 days, and must be taken by 30 April."
    )

    _, events = ask_both_ways(client, "What is the carry-over limit?")
    rebuilt = "".join(piece["delta"] for piece in only(events, "answer"))

    assert rebuilt == only(events, "done")[0]["answer"]


def test_the_stages_arrive_before_any_of_the_answer(
    client, script_understanding, script_routing, fake_language_model
):
    """
    Nothing of the answer may appear until it has been checked.

    This is the reason the model's own words are not streamed. An answer stating a figure
    that cannot be traced to the evidence is discarded and replaced, so text shown early
    is text that might have to be taken back.
    """
    script_understanding()
    script_routing(required_evidence="policy")
    fake_language_model.reply_to_plain_call("Carry-over is capped at 10 days.")

    _, events = ask_both_ways(client, "What is the carry-over limit?")
    order = [kind for kind, _ in events]

    assert "stage" in order and "answer" in order
    assert order.index("stage") < order.index("answer")
    assert order[-1] == "done"
    assert "check" in [payload["step"] for payload in only(events, "stage")]


def test_a_rejected_answer_is_never_streamed(
    client, script_understanding, script_routing, fake_language_model
):
    """
    A figure with nothing behind it must reach the employee as a refusal, not as itself.

    The scripted answer states a number that appears in no evidence, so validation
    discards it. What streams has to be the fallback, whole.
    """
    script_understanding()
    script_routing(required_evidence="policy")
    fake_language_model.reply_to_plain_call("You may carry over 999 days.")

    _, events = ask_both_ways(client, "What is the carry-over limit?")
    streamed = "".join(piece["delta"] for piece in only(events, "answer"))

    assert "999" not in streamed
    assert streamed == only(events, "done")[0]["answer"]


def test_a_question_that_pauses_streams_the_question_it_asks_back(
    client, script_understanding, fake_language_model
):
    """A paused turn ends the same way on both routes: with the question, and no answer."""
    script_understanding(needs_clarification=True, missing_information=["which leave type"])
    fake_language_model.reply_to_structured_call(
        "ClarificationQuestion",
        {"clarification_question": "Which kind of leave do you mean?",
         "missing_information": "leave type"},
    )

    with client.stream(
        "POST",
        "/api/v1/hcs01/query/stream",
        json={"query": "How many leaves can I take?", "employee_id": "EMP001",
              "conversation_id": "paused"},
    ) as response:
        events = read_events(response)

    finished = only(events, "done")[0]

    assert finished["is_awaiting_clarification"] is True
    assert finished["answer"] == "Which kind of leave do you mean?"


def test_no_node_name_reaches_the_wire(
    client, script_understanding, script_routing, fake_language_model
):
    """
    "route_each_subquery" means nothing to an employee.

    Every stage line is written for the person reading it, and a leaked node name is the
    easiest way for that to stop being true.
    """
    script_understanding()
    script_routing(required_evidence="policy")
    fake_language_model.reply_to_plain_call("Carry-over is capped at 10 days.")

    _, events = ask_both_ways(client, "What is the carry-over limit?")

    for payload in only(events, "stage"):
        assert "_" not in payload["text"]
        assert payload["text"][0].isupper() or payload["text"][0].isalpha()


def test_every_stage_event_carries_a_line_to_show(
    client, script_understanding, script_routing, fake_language_model
):
    """
    An event with detail but no sentence is one the interface cannot render.

    That happened: a search step whose next step was missing from the chain sent its
    clauses with nothing to caption them, and the browser threw rather than showing the
    answer at all. The shape has to hold for every event, not most of them.
    """
    script_understanding()
    script_routing(required_evidence="both")
    fake_language_model.reply_to_plain_call("Carry-over is capped at 10 days.")

    _, events = ask_both_ways(client, "What is my carry-over limit?")

    for payload in only(events, "stage"):
        assert payload.get("text"), f"stage event with no line to show: {payload}"
        assert payload.get("step")


def test_the_chain_of_stages_has_no_missing_link():
    """
    Each step names a real step, and the one shown first exists.

    A typo here does not fail anything until a live run reaches that node, which is the
    worst moment to find out.
    """
    from app.workflow.stage_names import FIRST_STAGE, NEXT_AFTER, STAGES

    assert FIRST_STAGE in STAGES
    for follows in NEXT_AFTER.values():
        assert follows in STAGES, f"{follows} is named as a next step but has no line"
