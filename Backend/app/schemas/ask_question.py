"""What a caller sends to ask the assistant a question."""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.settings import get_settings


class AskQuestionRequest(BaseModel):
    """
    The body of POST /api/v1/hcs01/query.

    `query` and `message` carry the same text; the web interface sends both. The
    clarification fields arrive as an explicit null when no clarification is pending,
    so every field has to stay optional.
    """

    # Unknown fields are ignored rather than rejected, so a newer web interface can add
    # a field without failing every request for everybody.
    model_config = ConfigDict(extra="ignore")

    query: Optional[str] = None
    message: Optional[str] = None
    employee_id: str = Field(default_factory=lambda: get_settings().default_employee_id)
    conversation_id: Optional[str] = None
    target_language: Optional[Literal["en", "ar"]] = None
    original_question: Optional[str] = None
    user_clarification: Optional[str] = None

    @property
    def question_text(self) -> str:
        """The asked question, whichever field the caller used to send it."""
        return (self.query or self.message or "").strip()
