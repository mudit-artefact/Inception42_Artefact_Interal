"""
Shared test setup.

Two guarantees hold for every test in this suite:
  1. No test reaches the network. Real language-model and embedding calls raise.
  2. No test touches the developer's own database. Each test gets a freshly seeded
     temporary SQLite file.
"""

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tests.fakes.language_model import FakeLanguageModel
from tests.fakes.policy_index import DEFAULT_POLICY_PASSAGES

BACKEND_DIRECTORY = Path(__file__).resolve().parent.parent
if str(BACKEND_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIRECTORY))


@pytest.fixture(autouse=True)
def fake_language_model(monkeypatch) -> FakeLanguageModel:
    """
    Replaces every language-model call with a scripted fake, and makes any embedding
    call fail loudly. This is what keeps the suite free, fast and deterministic.
    """
    import litellm

    fake = FakeLanguageModel()
    monkeypatch.setattr(litellm, "completion", fake.complete)

    def refuse_embedding_call(*arguments, **keyword_arguments):
        raise AssertionError(
            "A test tried to create real embeddings. Use the fake_embedding_model "
            "fixture, or stub the policy search instead."
        )

    monkeypatch.setattr(litellm, "embedding", refuse_embedding_call)
    return fake


@pytest.fixture
def fake_embedding_model(monkeypatch):
    """
    Deterministic vectors derived from the text itself, for tests that need to exercise
    real indexing and search code without paying for embeddings.
    """
    import hashlib

    import litellm

    from app.core.settings import settings

    def build_vector_for(text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        repeated = (digest * (settings.embedding_dim // len(digest) + 1))[: settings.embedding_dim]
        return [(byte_value - 128) / 128.0 for byte_value in repeated]

    class FakeEmbeddingResponse:
        def __init__(self, texts: list[str]) -> None:
            self.data = [{"embedding": build_vector_for(text)} for text in texts]

    def create_embeddings(model: str, input, **keyword_arguments):
        texts = input if isinstance(input, list) else [input]
        return FakeEmbeddingResponse(texts)

    monkeypatch.setattr(litellm, "embedding", create_embeddings)
    return create_embeddings


@pytest.fixture
def temporary_database(monkeypatch, tmp_path):
    """
    Points every module that holds a session factory at a fresh temporary database,
    seeded with the standard five employees.

    Web requests receive their session through a dependency, but the workflow opens its
    own, so the session factory is rebound on every module that holds one.
    """
    from app.database import engine as engine_module
    from app.database.tables import Base

    database_file = tmp_path / "omni_hr_for_tests.db"
    engine = create_engine(
        f"sqlite:///{database_file}",
        connect_args={"check_same_thread": False},
        echo=False,
    )
    Base.metadata.create_all(bind=engine)
    temporary_session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    monkeypatch.setattr(engine_module, "engine", engine)
    monkeypatch.setattr(engine_module, "SessionLocal", temporary_session_factory)
    for imported_module in list(sys.modules.values()):
        if getattr(imported_module, "__name__", "").startswith("app.") and hasattr(
            imported_module, "SessionLocal"
        ):
            monkeypatch.setattr(imported_module, "SessionLocal", temporary_session_factory)

    engine_module.init_and_seed_db()
    return temporary_session_factory


@pytest.fixture
def conversation_workflow():
    """The single conversation workflow, saving paused conversations in memory."""
    from langgraph.checkpoint.memory import InMemorySaver

    from app.workflow.conversation_workflow import compile_conversation_workflow

    return compile_conversation_workflow(InMemorySaver())


@pytest.fixture
def api_client(temporary_database, conversation_workflow):
    """
    A client for the running application, answering through the conversation workflow.

    The application's lifespan is deliberately not started: it would seed the real
    database and index policies for real. Both are handled by fixtures instead.
    """
    from fastapi.testclient import TestClient

    from app.main import app

    # Nothing to empty between tests any more: what a conversation remembers now lives
    # in its saved state, and each test gets its own in-memory store from the
    # conversation_workflow fixture. Isolation is structural rather than swept up after.
    app.state.conversation_workflow = conversation_workflow
    return TestClient(app)


@pytest.fixture
def stub_policy_search_service(monkeypatch):
    """Canned passages for the workflow's own search step."""
    from app.domain.policy_passage import PolicyPassage
    from app.workflow.nodes import gather_evidence

    canned_passages = [
        PolicyPassage(
            text="Employees accrue 25 working days of paid annual leave per calendar year.",
            policy_code="HC-PC-001",
            title="Annual Leave Policy",
            section="Section 1.1",
            page_number=1,
            pdf_url="/api/v1/hcs01/policies/pdf/01_annual_leave_policy.pdf",
            language="en",
            has_image=False,
            relevance_score=0.94,
            semantic_similarity=0.81,
        ),
        PolicyPassage(
            text="Carry-over is capped at 10 working days and must be used before 31 March.",
            policy_code="HC-PC-001",
            title="Annual Leave Policy",
            section="Section 1.3",
            page_number=1,
            pdf_url="/api/v1/hcs01/policies/pdf/01_annual_leave_policy.pdf",
            language="en",
            has_image=False,
            relevance_score=0.88,
            semantic_similarity=0.74,
        ),
    ]

    def search(query, top_k=5, language=None):
        return list(canned_passages)

    from app.services import policy_search_service
    monkeypatch.setattr(gather_evidence, "search_policies", search)
    monkeypatch.setattr(policy_search_service, "search_policies", search)
    return canned_passages


@pytest.fixture
def isolated_policy_index(monkeypatch, fake_embedding_model):
    """
    A private, empty vector database for one test, built with deterministic fake vectors.

    Exercises the real indexing and search code end to end without any network call.
    """
    from app.repositories import policy_vector_repository

    policy_vector_repository.reset_vector_database_client()
    monkeypatch.setattr(
        __import__("app.core.settings", fromlist=["settings"]).settings, "qdrant_in_memory", True
    )
    yield policy_vector_repository
    policy_vector_repository.reset_vector_database_client()
