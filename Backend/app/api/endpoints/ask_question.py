"""The endpoint the web interface asks questions through."""

import logging

import json
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.core.errors import ApplicationError
from app.core.language_detection import detect_language
from app.core.settings import settings
from app.schemas.answer import AnswerResponse
from app.schemas.ask_question import AskQuestionRequest
from app.services.answer_question_service import answer_question, stream_answer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/hcs01", tags=["Policy & Leave Concierge"])


@router.post(
    "/query",
    response_model=AnswerResponse,
    summary="Ask the concierge a question",
)
async def ask_question(request: Request, question: AskQuestionRequest) -> AnswerResponse:
    """
    Answer one question.

    A conversation that paused to ask the employee something is picked up automatically
    from the conversation_id, so a reply needs nothing more than the new text.
    """
    question_text = question.question_text
    if not question_text:
        raise HTTPException(status_code=422, detail="Query or message cannot be empty.")

    workflow = getattr(request.app.state, "conversation_workflow", None)
    if workflow is None:
        raise HTTPException(status_code=503, detail="The conversation workflow is not ready yet.")

    try:
        return answer_question(
            workflow=workflow,
            employee_question=question_text,
            employee_id=question.employee_id or settings.default_employee_id,
            conversation_id=question.conversation_id,
            requested_language=question.target_language or detect_language(question_text),
        )
    except ApplicationError:
        # These already have handlers that know which status each deserves. Catching them
        # here would turn a clear "the model is unavailable" into an opaque 500.
        raise
    except Exception as error:
        logger.error(f"Could not answer the question: {error}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {error}")


# How much of a finished answer to reveal at a time. Words rather than characters, because
# a word appearing whole reads as writing and a character at a time reads as a teleprinter.
WORDS_PER_CHUNK = 3

# The gap between pieces. Without it the whole answer arrives in one burst and the
# chunking achieves nothing — a wall of text a second after a minute of silence, which is
# what this endpoint exists to avoid. Short enough that nobody waits on it: a long answer
# of sixty pieces takes about a second and a quarter to lay down.
SECONDS_BETWEEN_PIECES = 0.02


@router.post(
    "/query/stream",
    summary="Ask the concierge a question, and watch it work",
    response_class=StreamingResponse,
)
async def ask_question_streaming(request: Request, question: AskQuestionRequest):
    """
    The same answer as `/query`, reported step by step while it is worked out.

    Answers take most of a minute, and the interface had nothing to show for any of it.
    This sends a line for each step the workflow finishes — the record read, the documents
    searched, the clauses found, the figures checked — and then the answer.

    The answer arrives only after it has passed the checks. Streaming the model's words as
    it writes them would be easy and is the one thing we will not do: a figure that cannot
    be traced to the evidence is thrown away, and an employee should never watch a number
    appear and then be taken back.

    `/query` is unchanged and remains the endpoint the evaluation harness measures.
    """
    question_text = question.question_text
    if not question_text:
        raise HTTPException(status_code=422, detail="Query or message cannot be empty.")

    workflow = getattr(request.app.state, "conversation_workflow", None)
    if workflow is None:
        raise HTTPException(status_code=503, detail="The conversation workflow is not ready yet.")

    def events():
        try:
            for kind, payload in stream_answer(
                workflow=workflow,
                employee_question=question_text,
                employee_id=question.employee_id or settings.default_employee_id,
                conversation_id=question.conversation_id,
                requested_language=question.target_language or detect_language(question_text),
            ):
                if kind == "stage":
                    yield _as_event("stage", payload)
                    continue

                for piece in _in_readable_pieces(payload.answer):
                    yield _as_event("answer", {"delta": piece})
                    time.sleep(SECONDS_BETWEEN_PIECES)
                yield _as_event("done", payload.model_dump())
        except ApplicationError as error:
            logger.error(f"Could not answer the question: {error}")
            yield _as_event("error", {"detail": str(error)})
        except Exception as error:
            logger.error(f"Could not answer the question: {error}", exc_info=True)
            yield _as_event("error", {"detail": f"Internal error: {error}"})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Nginx buffers event streams into uselessness unless told not to.
            "X-Accel-Buffering": "no",
        },
    )


def _as_event(name: str, payload: dict) -> str:
    """One server-sent event. The blank line is what ends it, and is not optional."""
    return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _in_readable_pieces(answer: str):
    """
    A finished answer, handed over a few words at a time.

    The text is complete and checked before the first piece leaves here, so this is pacing
    rather than generation — but it is what stops a long reply landing as a wall a second
    after a minute of silence. Newlines stay attached to the word before them so the
    interface can render markdown as it arrives.
    """
    if not answer:
        return
    words = answer.split(" ")
    for start in range(0, len(words), WORDS_PER_CHUNK):
        piece = " ".join(words[start:start + WORDS_PER_CHUNK])
        yield piece if start + WORDS_PER_CHUNK >= len(words) else piece + " "
