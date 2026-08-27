"""
scripts/ingest.py — Standalone ingestion script.
Run this to (re-)index all policy documents into Qdrant.

Usage:
    python scripts/ingest.py            # Skip if already ingested
    python scripts/ingest.py --force    # Force re-ingestion
"""
import sys
import os
import argparse
import logging

# Add project root to path so `app` package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env before importing app modules
from dotenv import load_dotenv
load_dotenv()

from app import vector_store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="HCS-01 Policy Ingestion Script")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-ingestion even if Qdrant already has vectors.",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("HCS-01 Policy Ingestion")
    logger.info("=" * 60)

    # Ensure collection exists
    vector_store.ensure_collection()

    current_count = vector_store.collection_count()
    logger.info(f"Current vector count in Qdrant: {current_count}")

    if current_count > 0 and not args.force:
        logger.info(
            "Collection already populated. Use --force to re-ingest.\n"
            "Tip: python scripts/ingest.py --force"
        )
        return

    n = vector_store.ingest_policies(force=args.force)
    logger.info("=" * 60)
    logger.info(f"✅ Done! {n} chunks indexed into Qdrant.")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
