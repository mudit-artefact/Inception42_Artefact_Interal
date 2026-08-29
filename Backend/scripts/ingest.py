"""
Build the policy search index from the command line.

    python scripts/ingest.py            # only if the index is empty
    python scripts/ingest.py --force    # rebuild it from scratch
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from app.repositories.policy_vector_repository import count_indexed_passages  # noqa: E402
from app.services.policy_indexing_service import reindex_policies  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the policy search index")
    parser.add_argument(
        "--force", action="store_true", help="rebuild even if the index already has passages"
    )
    arguments = parser.parse_args()

    already_indexed = count_indexed_passages()
    print(f"The index currently holds {already_indexed} passages.")

    indexed_count = reindex_policies(force=arguments.force)
    if indexed_count == 0 and not arguments.force:
        print("Nothing to do. Pass --force to rebuild from scratch.")
        return 0

    print(f"Indexed {indexed_count} policy passages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
