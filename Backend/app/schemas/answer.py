"""What the assistant returns for one asked question."""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ChartDataPoint(BaseModel):
    """One data point in a chart."""

    label: str
    value: float
    value2: Optional[float] = None  # Second value for grouped charts


class ChartDataSet(BaseModel):
    """Alternative dataset for dropdown switching (e.g., different leave types)."""

    label: str  # e.g., "Annual Leave", "Sick Leave"
    data: list[ChartDataPoint] = []
    title: Optional[str] = None  # Optional override title


class ChartData(BaseModel):
    """Chart visualization data for numeric comparisons."""

    chart_type: Literal["horizontal_bar", "grouped_bar", "stacked_bar", "nested_bar", "progress", "line"]
    title: str
    data: list[ChartDataPoint] = []
    series_names: list[str] = []  # e.g., ["Entitled", "Used"]
    unit: Optional[str] = None
    max_value: Optional[float] = None  # For progress charts
    # Optional: alternative datasets for dropdown (different leave types)
    datasets: Optional[list[ChartDataSet]] = None


class SourceCitation(BaseModel):
    """
    One piece of evidence behind an answer: either a policy passage or the employee's
    own record in the HR database.
    """

    id: Optional[str] = None
    title: str = ""
    source: str
    source_type: Optional[str] = "policy"  # "policy" | "database"
    table_name: Optional[str] = None
    section: str
    page_number: Optional[int] = 1
    # Kept between 0 and 1: the web interface renders this as a percentage.
    score: float
    language: str = "en"
    snippet: Optional[str] = None
    url: Optional[str] = "#"
    pdf_url: Optional[str] = None
    has_image: Optional[bool] = False


class AnswerResponse(BaseModel):
    """The body of POST /api/v1/hcs01/query."""

    answer: str
    sources: list[SourceCitation] = Field(default_factory=list)
    conversation_id: str
    employee_profile: dict = Field(default_factory=dict)
    target_language: str = "en"
    latency_ms: int = 0
    tokens_used: int = 0
    intent: Optional[str] = "policy_inquiry"
    rewritten_query: Optional[str] = None
    confidence_score: Optional[float] = 1.0

    # When the question was too vague to answer, the assistant asks something back and
    # waits. The web interface needs `is_awaiting_clarification` and `original_question`
    # to both be present before it will send the employee's reply as a follow-up.
    original_question: Optional[str] = None
    clarifying_question: Optional[str] = None
    is_awaiting_clarification: bool = False

    # Agentic Action Payload (e.g. Leave Confirmation Card, Submitted details)
    action_payload: Optional[dict] = None
    is_action_required: bool = False

    # Optional chart visualization for numeric breakdowns
    chart: Optional[ChartData] = None
