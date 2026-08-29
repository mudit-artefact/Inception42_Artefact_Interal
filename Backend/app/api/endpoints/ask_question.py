"""The endpoint the web interface asks questions through."""

import logging

from fastapi import APIRouter, HTTPException, Request

from app.core.errors import ApplicationError
from app.core.language_detection import detect_language
from app.core.settings import settings
from app.schemas.answer import AnswerResponse
from app.schemas.ask_question import AskQuestionRequest
from app.services.answer_question_service import answer_question

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
