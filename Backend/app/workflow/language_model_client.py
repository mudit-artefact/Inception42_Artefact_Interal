"""
The single place the language model is called.

Before this, `litellm.completion` was called from five different modules, each with its
own retry rules and its own copy of the provider quirks — and each wrapped in an `except`
that turned a failure into a plausible-looking default. There was no seam to substitute
in tests, so the only way to exercise the system was to pay for real calls.

Failures raise LanguageModelUnavailableError. They are not converted into a default
answer: an unreachable model must not look like a confident one.
"""

import json
import logging
from typing import Type, TypeVar

import litellm
import tenacity
from pydantic import BaseModel

from app.core.settings import settings
from app.core.errors import LanguageModelUnavailableError

logger = logging.getLogger(__name__)

StructuredOutput = TypeVar("StructuredOutput", bound=BaseModel)

MAXIMUM_ATTEMPTS = 3
GROUNDED_ANSWER_TEMPERATURE = 0.1


def supports_temperature_setting() -> bool:
    """
    Whether this provider accepts a temperature.

    Gemini rejects the parameter, so it is left off for those models. This was previously
    decided by searching the model name for "gemini" in three separate files.
    """
    return "gemini" not in settings.llm_model.lower()


@tenacity.retry(
    stop=tenacity.stop_after_attempt(MAXIMUM_ATTEMPTS),
    wait=tenacity.wait_exponential(multiplier=1, min=1, max=4),
    reraise=True,
)
def _request_completion(**keyword_arguments):
    return litellm.completion(**keyword_arguments)


def generate_text(messages: list[dict], maximum_tokens: int | None = None) -> tuple[str, int]:
    """Ask the model for prose. Returns the text and how many tokens it cost."""
    request = {
        "model": settings.llm_model,
        "messages": messages,
        "max_tokens": maximum_tokens or settings.max_tokens,
    }
    if supports_temperature_setting():
        request["temperature"] = GROUNDED_ANSWER_TEMPERATURE

    try:
        response = _request_completion(**request)
    except Exception as error:
        logger.error(f"The language model could not be reached: {error}")
        raise LanguageModelUnavailableError(error) from error

    answer = response.choices[0].message.content or ""
    tokens_used = response.usage.total_tokens if response.usage else 0
    return answer, tokens_used


def generate_structured_output(
    messages: list[dict],
    output_model: Type[StructuredOutput],
    report_usage: bool = False,
) -> StructuredOutput | tuple[StructuredOutput, int]:
    """
    Ask the model for an answer shaped like `output_model`.

    A reply that does not fit the shape is a failure, not something to paper over.

    `report_usage` adds the token count to the return, matching what `generate_text`
    gives back. It is opt-in so that the steps which only ever needed the shape — reading
    a question, splitting it, routing it — keep the single return value they were written
    against. Only the step that drafts the answer reports usage, because that is the
    figure the web interface shows.
    """
    try:
        response = _request_completion(
            model=settings.llm_model,
            messages=messages,
            response_format=output_model,
        )
    except Exception as error:
        logger.error(f"The language model could not be reached: {error}")
        raise LanguageModelUnavailableError(error) from error

    raw_reply = response.choices[0].message.content or ""
    try:
        structured_reply = output_model.model_validate_json(raw_reply)
    except Exception as error:
        logger.error(f"The model's reply did not fit {output_model.__name__}: {raw_reply[:200]}")
        raise LanguageModelUnavailableError(error) from error

    if report_usage:
        return structured_reply, (response.usage.total_tokens if response.usage else 0)
    return structured_reply
