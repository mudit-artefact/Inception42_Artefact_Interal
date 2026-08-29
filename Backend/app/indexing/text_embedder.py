"""Turns text into vectors. The only place embeddings are requested."""

import litellm

from app.core.settings import settings

EMBEDDING_BATCH_SIZE = 20


def embed_one_text(text: str) -> list[float]:
    """The vector for a single piece of text."""
    return embed_many_texts([text])[0]


def embed_many_texts(texts: list[str]) -> list[list[float]]:
    """Vectors for many pieces of text, requested in batches."""
    vectors: list[list[float]] = []
    for batch_start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = [
            text.replace("\n", " ") for text in texts[batch_start : batch_start + EMBEDDING_BATCH_SIZE]
        ]
        response = litellm.embedding(model=settings.embedding_model, input=batch)
        vectors.extend(item["embedding"] for item in response.data)
    return vectors
