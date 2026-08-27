"""
app/config.py — Centralised settings loaded from .env
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── API Keys ──────────────────────────────────────────────────
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")

    # ── Models ────────────────────────────────────────────────────
    embedding_model: str = Field(default="text-embedding-3-large", alias="EMBEDDING_MODEL")
    embedding_dim: int = Field(default=3072, alias="EMBEDDING_DIM")
    llm_model: str = Field(default="gpt-4o", alias="LLM_MODEL")

    # ── Qdrant ────────────────────────────────────────────────────
    qdrant_host: str = Field(default="localhost", alias="QDRANT_HOST")
    qdrant_port: int = Field(default=6333, alias="QDRANT_PORT")
    qdrant_collection: str = Field(default="hcs01_policies", alias="QDRANT_COLLECTION")
    qdrant_in_memory: bool = Field(default=False, alias="QDRANT_IN_MEMORY")

    # ── API ───────────────────────────────────────────────────────
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")

    # ── RAG ───────────────────────────────────────────────────────
    rag_top_k: int = Field(default=5, alias="RAG_TOP_K")
    chunk_size: int = Field(default=512, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=64, alias="CHUNK_OVERLAP")
    max_tokens: int = Field(default=4096, alias="MAX_TOKENS")

    # ── Paths ─────────────────────────────────────────────────────
    policies_en_dir: str = "data/policies_en"
    policies_ar_dir: str = "data/policies_ar"
    synthetic_users_path: str = "data/synthetic_users.json"


# Singleton instance — import this everywhere
settings = Settings()
