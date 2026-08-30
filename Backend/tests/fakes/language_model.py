"""
A stand-in for the real language model.

Every call the application makes to `litellm.completion` is answered from a script
that the test writes up front. Responses are looked up by the name of the Pydantic
model the caller asked for (`response_format=...`), so a test does not have to know
in what order the application happens to make its calls.
"""

import json
from typing import Any


class FakeLanguageModelMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeLanguageModelChoice:
    def __init__(self, content: str) -> None:
        self.message = FakeLanguageModelMessage(content)


class FakeLanguageModelUsage:
    def __init__(self, total_tokens: int) -> None:
        self.total_tokens = total_tokens


class FakeLanguageModelResponse:
    def __init__(self, content: str, total_tokens: int = 42) -> None:
        self.choices = [FakeLanguageModelChoice(content)]
        self.usage = FakeLanguageModelUsage(total_tokens)


class FakeLanguageModel:
    """Answers structured calls by requested output model, plain calls with the free text."""

    def __init__(self) -> None:
        # Either a fixed payload, or a callable answering one call at a time.
        self.structured_replies: dict[str, Any] = {}
        self.plain_reply: str = "This is a generated answer."
        self.recorded_calls: list[dict[str, Any]] = []
        self.failure_to_raise: Exception | None = None

    # ── scripting ────────────────────────────────────────────────────────────
    def reply_to_structured_call(self, output_model_name: str, payload: dict[str, Any]) -> None:
        self.structured_replies[output_model_name] = payload

    def reply_to_structured_calls_in_turn(self, output_model_name: str, next_payload) -> None:
        """
        Answer each call for this model differently.

        Needed since one question can be split into parts that are routed one at a time:
        a single fixed payload would send every part down the same route, which is
        exactly what the splitting is supposed to make possible to avoid.
        """
        self.structured_replies[output_model_name] = next_payload

    def reply_to_plain_call(self, answer_text: str) -> None:
        """
        The text the assistant will answer with.

        Named for the call it used to be. Drafting an answer now asks for a shape —
        `AnswerWithWorking`, the reply plus any figures it worked out — but from a test's
        point of view the interesting part is still the words, so this keeps serving that
        call and every test that scripts it reads the same as before. A test that cares
        about the working scripts `AnswerWithWorking` directly.
        """
        self.plain_reply = answer_text

    def fail_every_call_with(self, error: Exception) -> None:
        self.failure_to_raise = error

    # ── the seam the application calls ───────────────────────────────────────
    def complete(self, **keyword_arguments: Any) -> FakeLanguageModelResponse:
        requested_output_model = keyword_arguments.get("response_format")
        requested_output_model_name = getattr(requested_output_model, "__name__", None)
        self.recorded_calls.append(
            {
                "model": keyword_arguments.get("model"),
                "response_format": requested_output_model_name,
                "messages": keyword_arguments.get("messages"),
            }
        )

        if self.failure_to_raise is not None:
            raise self.failure_to_raise

        if requested_output_model_name is None:
            return FakeLanguageModelResponse(self.plain_reply)

        # The answer step asks for a shape, and almost every test only cares about the
        # words in it. Without this, adding the working to the answer would have meant
        # rewriting fifteen tests that have nothing to do with arithmetic.
        if (
            requested_output_model_name == "AnswerWithWorking"
            and requested_output_model_name not in self.structured_replies
        ):
            return FakeLanguageModelResponse(
                json.dumps({"answer": self.plain_reply, "calculations": []})
            )

        if requested_output_model_name not in self.structured_replies:
            raise AssertionError(
                f"The application asked for {requested_output_model_name}, but the test "
                f"only scripted {sorted(self.structured_replies)}."
            )
        scripted = self.structured_replies[requested_output_model_name]
        payload = scripted(**keyword_arguments) if callable(scripted) else scripted
        return FakeLanguageModelResponse(json.dumps(payload))

    # ── assertions ───────────────────────────────────────────────────────────
    @property
    def call_count(self) -> int:
        return len(self.recorded_calls)

    def count_calls_for(self, output_model_name: str) -> int:
        return sum(1 for call in self.recorded_calls if call["response_format"] == output_model_name)
