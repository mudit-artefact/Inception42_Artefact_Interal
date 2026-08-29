"""
All access to the vector database.

Nothing else in the application talks to Qdrant directly.
"""

import logging
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.core.settings import settings

logger = logging.getLogger(__name__)

_vector_database_client: Optional[QdrantClient] = None


def get_vector_database_client() -> QdrantClient:
    """The shared connection to the vector database."""
    global _vector_database_client
    if _vector_database_client is None:
        if settings.qdrant_in_memory:
            logger.info("Using an in-memory vector database (no Docker needed)")
            _vector_database_client = QdrantClient(":memory:")
        else:
            logger.info(
                f"Connecting to the vector database at {settings.qdrant_host}:{settings.qdrant_port}"
            )
            _vector_database_client = QdrantClient(
                host=settings.qdrant_host, port=settings.qdrant_port, timeout=10
            )
    return _vector_database_client


def reset_vector_database_client() -> None:
    """Drops the shared connection. Used between tests."""
    global _vector_database_client
    _vector_database_client = None


def ensure_collection_exists() -> None:
    """Create the passage collection if this is a fresh database."""
    client = get_vector_database_client()
    existing_names = [collection.name for collection in client.get_collections().collections]
    if settings.qdrant_collection in existing_names:
        return
    client.create_collection(
        collection_name=settings.qdrant_collection,
        vectors_config=VectorParams(size=settings.embedding_dim, distance=Distance.COSINE),
    )
    logger.info(f"Created the vector collection '{settings.qdrant_collection}'")


def count_indexed_passages() -> int:
    """How many passages are indexed, or zero if the collection is not there yet."""
    try:
        collection = get_vector_database_client().get_collection(settings.qdrant_collection)
        return collection.points_count or 0
    except Exception:
        return 0


def delete_all_passages() -> None:
    """Empty the collection so it can be rebuilt from scratch."""
    client = get_vector_database_client()
    try:
        client.delete_collection(settings.qdrant_collection)
    except Exception as error:
        logger.warning(f"Could not delete the existing collection: {error}")
    ensure_collection_exists()


def store_passages(passage_payloads: list[dict], vectors: list[list[float]]) -> int:
    """Write passages and their vectors into the collection. Returns how many were written."""
    points = [
        PointStruct(id=position, vector=vector, payload=payload)
        for position, (payload, vector) in enumerate(zip(passage_payloads, vectors))
    ]
    get_vector_database_client().upsert(collection_name=settings.qdrant_collection, points=points)
    return len(points)


def search_by_vector(
    query_vector: list[float],
    limit: int,
    language: Optional[str] = None,
) -> list:
    """The closest passages to a query vector, optionally restricted to one language."""
    language_filter = None
    if language:
        language_filter = Filter(
            must=[FieldCondition(key="language", match=MatchValue(value=language))]
        )

    return get_vector_database_client().query_points(
        collection_name=settings.qdrant_collection,
        query=query_vector,
        limit=limit,
        query_filter=language_filter,
        with_payload=True,
    ).points
