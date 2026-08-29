"""
Where a paused conversation is stored.

This is what makes the clarification pause real. Without somewhere to save a
conversation's state, a question that pauses to ask the employee something cannot be
resumed on the next request, and the web interface has to hold that state instead.
"""

import logging
import sqlite3
from pathlib import Path

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver

logger = logging.getLogger(__name__)

BACKEND_DIRECTORY = Path(__file__).resolve().parent.parent.parent
DEFAULT_CHECKPOINT_FILE = BACKEND_DIRECTORY / "data" / "conversation_checkpoints.sqlite"


def create_conversation_checkpointer(
    checkpoint_file: Path | None = DEFAULT_CHECKPOINT_FILE,
) -> BaseCheckpointSaver:
    """
    Somewhere to save paused conversations.

    Falls back to memory when no file is given, which is what tests use. A file-backed
    store is what lets a pause survive a restart.
    """
    if checkpoint_file is None:
        logger.info("Saving conversations in memory only; a restart will forget them")
        return InMemorySaver()

    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
    except ImportError:
        logger.warning(
            "langgraph-checkpoint-sqlite is not installed, so conversations are held in "
            "memory only and a restart will forget any paused clarification."
        )
        return InMemorySaver()

    checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False because the web server answers requests on several threads.
    connection = sqlite3.connect(str(checkpoint_file), check_same_thread=False, timeout=30)
    # Write-ahead logging so a reader is not blocked by a writer.
    connection.execute("PRAGMA journal_mode=WAL")

    checkpointer = SqliteSaver(connection)
    checkpointer.setup()
    logger.info(f"Saving paused conversations in {checkpoint_file}")
    return checkpointer
