"""Building and rebuilding the searchable policy index."""

import logging

from app.indexing.policy_chunk_builder import build_all_policy_passages
from app.indexing.text_embedder import embed_many_texts
from app.repositories import policy_vector_repository

logger = logging.getLogger(__name__)


def reindex_policies(force: bool = False) -> int:
    """
    Index every policy passage and return how many were indexed.

    Does nothing and returns 0 when the index already holds passages, unless `force` is
    set. This parameter used to be missing while two callers passed it, so rebuilding the
    index always failed with a TypeError.
    """
    policy_vector_repository.ensure_collection_exists()

    already_indexed = policy_vector_repository.count_indexed_passages()
    if already_indexed > 0 and not force:
        logger.info(f"The policy index already holds {already_indexed} passages; leaving it alone")
        return 0

    if force and already_indexed > 0:
        logger.info("Rebuilding the policy index from scratch")
        policy_vector_repository.delete_all_passages()

    passages = build_all_policy_passages()
    if not passages:
        logger.warning("No policy passages were produced, so nothing was indexed")
        return 0

    vectors = embed_many_texts([passage["text"] for passage in passages])
    indexed_count = policy_vector_repository.store_passages(passages, vectors)
    logger.info(f"Indexed {indexed_count} policy passages")
    return indexed_count


def prepare_index_if_empty() -> int:
    """
    Build the index only if it is empty. Called once when the application starts.

    Indexing on start-up, rather than partway through somebody's question, is deliberate:
    it used to happen inside the search call, so the first person to ask anything after a
    restart waited for the whole catalogue to be embedded.
    """
    policy_vector_repository.ensure_collection_exists()
    if policy_vector_repository.count_indexed_passages() > 0:
        return 0
    return reindex_policies(force=False)
