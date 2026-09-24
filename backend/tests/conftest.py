"""Shared pytest configuration and fixtures for Keepsake tests.

- Points the app at a test database (TEST_DATABASE_URL) before it is imported
- db_session: every change is rolled back after the test, even if the code under test commits
- client: FastAPI TestClient using the test session and fake providers
- `live` tests (real APIs) are skipped unless RUN_LIVE=1
"""

import os
from collections.abc import Iterator

import pytest

# Set before importing app, which reads DATABASE_URL from config.
# Each branch/agent sets TEST_DATABASE_URL to its own database; CI uses test_ci.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://keepsake:keepsake@127.0.0.1:5433/test_main"
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db import Base, get_session  # noqa: E402
from app.main import app  # noqa: E402
from app.providers import registry  # noqa: E402
from tests.fakes import (  # noqa: E402
    FakeEmbedder,
    FakeFaceRenderer,
    FakeLLM,
    FakeMemoryRecall,
    FakeSpeechToText,
    FakeVoiceSynth,
)

test_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)


def pytest_collection_modifyitems(config, items):
    if os.environ.get("RUN_LIVE") == "1":
        return
    skip_live = pytest.mark.skip(reason="live test: set RUN_LIVE=1 to run against real APIs")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


@pytest.fixture(scope="session")
def _test_tables() -> None:
    with test_engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(test_engine)


@pytest.fixture
def db_session(_test_tables) -> Iterator[Session]:
    """Bound to one connection inside an outer transaction; session.commit() only releases a
    savepoint, so nothing reaches the database for real."""
    connection = test_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture
def fake_stt() -> FakeSpeechToText:
    return FakeSpeechToText()


@pytest.fixture
def fake_voice_synth() -> FakeVoiceSynth:
    return FakeVoiceSynth()


@pytest.fixture
def fake_face_renderer() -> FakeFaceRenderer:
    return FakeFaceRenderer()


@pytest.fixture
def fake_memory_recall() -> FakeMemoryRecall:
    return FakeMemoryRecall()


@pytest.fixture
def client(
    db_session: Session,
    fake_llm: FakeLLM,
    fake_embedder: FakeEmbedder,
    fake_stt: FakeSpeechToText,
    fake_voice_synth: FakeVoiceSynth,
    fake_face_renderer: FakeFaceRenderer,
) -> Iterator[TestClient]:
    """TestClient on the test session, with every registry.get_<kind>() returning a fake.

    Override keys match the get_<kind> names in app/providers/registry.py.
    """
    app.dependency_overrides[get_session] = lambda: db_session
    registry.override(
        llm=fake_llm, stt=fake_stt, embedder=fake_embedder, voice=fake_voice_synth, face=fake_face_renderer
    )
    try:
        # No `with`: the lifespan would run create_all against the app's own engine.
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        registry.clear_overrides()
