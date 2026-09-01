"""
Every setting the application reads, in one place.

Replaces app/config.py. Settings that nothing read have been removed rather than left to
look meaningful: four paths and two chunking sizes were declared here and never used,
while the code that needed those paths worked them out for itself.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIRECTORY = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # An absolute path, so the values do not change with the directory the server
        # happens to be started from.
        env_file=BACKEND_DIRECTORY / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Model access ──────────────────────────────────────────────
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")

    embedding_model: str = Field(default="text-embedding-3-large", alias="EMBEDDING_MODEL")
    embedding_dim: int = Field(default=3072, alias="EMBEDDING_DIM")
    llm_model: str = Field(default="gpt-5.1", alias="LLM_MODEL")
    max_tokens: int = Field(default=4096, alias="MAX_TOKENS")
    # Zero, because none of the five model calls in a turn wants variety. Four of them are
    # classifications — what is being asked, how it splits, which sources it needs — and the
    # fifth extracts figures from documents. Sampling was left at the provider's default
    # until now, which is why the same question could be answered differently twice in a
    # row and why a one-point change in a benchmark score meant nothing.
    llm_temperature: float = Field(default=0.0, alias="LLM_TEMPERATURE")

    # ── Search index ──────────────────────────────────────────────
    qdrant_host: str = Field(default="localhost", alias="QDRANT_HOST")
    qdrant_port: int = Field(default=6333, alias="QDRANT_PORT")
    qdrant_collection: str = Field(default="hcs01_policies", alias="QDRANT_COLLECTION")
    qdrant_in_memory: bool = Field(default=False, alias="QDRANT_IN_MEMORY")
    rag_top_k: int = Field(default=5, alias="RAG_TOP_K")

    # ── Web server ────────────────────────────────────────────────
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")

    # ── LangSmith Tracing ─────────────────────────────────────────
    langchain_tracing_v2: bool = Field(default=False, alias="LANGCHAIN_TRACING_V2")
    langchain_api_key: str = Field(default="", alias="LANGCHAIN_API_KEY")
    langchain_project: str = Field(default="hcs01-hr-assistant", alias="LANGCHAIN_PROJECT")

    # ── Employees ─────────────────────────────────────────────────
    default_employee_id: str = Field(default="EMP001", alias="DEFAULT_EMPLOYEE_ID")


@lru_cache
def get_settings() -> Settings:
    """The settings, read once. Call get_settings.cache_clear() in tests."""
    s = Settings()
    if s.langchain_tracing_v2 and s.langchain_api_key:
        import os
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = s.langchain_api_key
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_API_KEY"] = s.langchain_api_key
        os.environ["LANGCHAIN_PROJECT"] = s.langchain_project
        os.environ["LANGSMITH_PROJECT"] = s.langchain_project
    return s


settings = get_settings()
