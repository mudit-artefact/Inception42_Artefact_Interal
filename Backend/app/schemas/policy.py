"""The policy catalogue and the result of rebuilding the policy index."""

from pydantic import BaseModel


class PolicySummary(BaseModel):
    """One entry of GET /api/v1/hcs01/policies."""

    id: str
    title: str
    section: str
    topics: list[str]
    pdf_url: str
    url: str
    diagram_page: int


class ReindexPoliciesResponse(BaseModel):
    """The result of rebuilding the searchable policy index."""

    status: str  # "success" | "skipped"
    chunks_indexed: int
    message: str
