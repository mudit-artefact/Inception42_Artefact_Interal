"""The service's own status."""

from pydantic import BaseModel


class HealthStatusResponse(BaseModel):
    """The body of GET /api/v1/hcs01/health."""

    status: str  # "ok" | "degraded"
    service: str
    version: str
    qdrant_connected: bool
    vectors_indexed: int
    llm_model: str
    embedding_model: str


class ServiceBannerResponse(BaseModel):
    """The body of GET / — a pointer to the docs for anyone who lands on the root."""

    service: str
    docs: str
    health: str
    chat: str
