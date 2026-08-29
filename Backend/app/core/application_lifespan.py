"""
What happens when the application starts and stops.

Three things have to be ready before the first question arrives: the employee database,
the policy search index, and the workflow together with somewhere to save conversations
that pause.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.repositories.policy_vector_repository import count_indexed_passages
from app.services.policy_indexing_service import prepare_index_if_empty
from app.workflow.conversation_checkpointer import create_conversation_checkpointer
from app.workflow.conversation_workflow import compile_conversation_workflow

logger = logging.getLogger(__name__)


@asynccontextmanager
async def application_lifespan(application: FastAPI):
    """Prepare everything the application needs, then clean up on the way out."""
    logger.info("Policy & Leave Concierge starting up")

    _prepare_employee_database()
    _prepare_policy_index()
    checkpointer = _prepare_conversation_workflow(application)

    yield

    connection = getattr(checkpointer, "conn", None)
    if connection is not None:
        connection.close()
    logger.info("Policy & Leave Concierge shutting down")


def _prepare_employee_database() -> None:
    from app.database.engine import init_and_seed_db

    try:
        init_and_seed_db()
        logger.info("Employee database ready")
    except Exception as error:
        logger.error(f"The employee database could not be prepared: {error}")


def _prepare_policy_index() -> None:
    """
    Index the policies now rather than partway through somebody's question.

    This used to happen inside the search call, so the first person to ask anything after
    a restart waited for the whole catalogue to be embedded.
    """
    try:
        newly_indexed = prepare_index_if_empty()
        if newly_indexed:
            logger.info(f"Indexed {newly_indexed} policy passages")
        else:
            logger.info(f"Policy index ready with {count_indexed_passages()} passages")
    except Exception as error:
        logger.error(f"The policy index could not be prepared: {error}")
        logger.warning("The service will start, but questions cannot be answered from policy.")


def _prepare_conversation_workflow(application: FastAPI):
    """
    Build the workflow once, here, so it can be given somewhere to save conversations.

    The two graphs this replaced each compiled themselves when their module was imported,
    which left no opportunity to hand them a place to save anything.
    """
    try:
        checkpointer = create_conversation_checkpointer()
        application.state.conversation_workflow = compile_conversation_workflow(checkpointer)
        logger.info("Conversation workflow ready")
        return checkpointer
    except Exception as error:
        application.state.conversation_workflow = None
        logger.error(f"The conversation workflow could not be built: {error}")
        return None
