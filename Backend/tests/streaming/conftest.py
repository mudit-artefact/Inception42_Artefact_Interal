"""Fixtures for the streaming endpoint, driven through HTTP with a scripted model."""

import pytest

# Imported rather than declared as a plugin: `pytest_plugins` is only honoured in the
# root conftest, and declaring it here breaks collection for the whole suite. Importing
# the fixture functions registers them just the same.
from tests.workflow.conftest import (  # noqa: F401
    script_routing,
    script_understanding,
)


@pytest.fixture
def client(temporary_database, stub_policy_search_service):
    """
    The application, started, with the fake language model already in place.

    `temporary_database` comes first deliberately. Unlike `api_client` in the root
    conftest, this fixture starts the application's lifespan, and the lifespan seeds
    employees and indexes policies for real — so without the temporary database pointed
    at first, running the streaming tests rewrote the developer's own records.
    """
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as started:
        yield started


def read_events(response) -> list[tuple[str, dict]]:
    """The server-sent events of one response, in order, as (name, payload) pairs."""
    import json

    events: list[tuple[str, dict]] = []
    name = ""
    for line in response.iter_lines():
        if line.startswith("event:"):
            name = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            events.append((name, json.loads(line.split(":", 1)[1].strip())))
    return events
