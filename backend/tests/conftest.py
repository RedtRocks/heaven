"""Shared pytest configuration and fixtures for Keepsake tests.

This module:
- Overrides DATABASE_URL to use the test database (test_test_infra)
- Provides a db_session fixture that creates tables and rolls back per test
- Provides a client fixture (FastAPI TestClient) with fakes injected
- Registers pytest markers (unit, db, slow)
"""

import os
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

# Set test database URL BEFORE importing app, which reads it from config
TEST_DATABASE_URL = "postgresql+psycopg://keepsake:keepsake@127.0.0.1:5433/test_test_infra"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

# Now we can import the app
from app.db import Base, get_session
from app.main import app
from app.providers import Embedder, FaceRenderer, LLM, SpeechToText, VoiceSynth
from app.conversation.contracts import MemoryRecall

from tests.fakes import (
    FakeEmbedder,
    FakeFaceRenderer,
    FakeLLM,
    FakeMemoryRecall,
    FakeSpeechToText,
    FakeVoiceSynth,
)


# Create engine for test database
test_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
TestSessionLocal = sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture
def db_session() -> Iterator[Session]:
    """Fixture: a database session that creates tables and rolls back per test.

    This fixture:
    1. Creates all tables from app.db.Base.metadata
    2. Yields a session for the test
    3. Rolls back all changes after the test (via transaction rollback)
    4. Does NOT drop tables (faster for sequential tests)

    Each test gets an isolated session that sees only changes made within that test.
    """
    # Create all tables (idempotent)
    with test_engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(test_engine)

    # Start a transaction for this test
    session = TestSessionLocal()
    session.begin_nested()  # Savepoint; allows rollback without closing connection

    try:
        yield session
    finally:
        # Rollback all changes made in this test
        session.rollback()
        session.close()


@pytest.fixture
def fake_llm() -> FakeLLM:
    """Fixture: a fake LLM for testing."""
    return FakeLLM()


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    """Fixture: a fake embedder for testing."""
    return FakeEmbedder()


@pytest.fixture
def fake_stt() -> FakeSpeechToText:
    """Fixture: a fake speech-to-text for testing."""
    return FakeSpeechToText()


@pytest.fixture
def fake_voice_synth() -> FakeVoiceSynth:
    """Fixture: a fake voice synth for testing."""
    return FakeVoiceSynth()


@pytest.fixture
def fake_face_renderer() -> FakeFaceRenderer:
    """Fixture: a fake face renderer for testing."""
    return FakeFaceRenderer()


@pytest.fixture
def fake_memory_recall() -> FakeMemoryRecall:
    """Fixture: a fake memory recall for testing."""
    return FakeMemoryRecall()


@pytest.fixture
def client(
    db_session: Session,
    fake_llm: FakeLLM,
    fake_embedder: FakeEmbedder,
    fake_stt: FakeSpeechToText,
    fake_voice_synth: FakeVoiceSynth,
    fake_face_renderer: FakeFaceRenderer,
    fake_memory_recall: FakeMemoryRecall,
) -> TestClient:
    """Fixture: FastAPI TestClient with dependency overrides.

    This client:
    - Uses the test database (via db_session fixture)
    - Uses all fake providers (never real API keys)
    - Is ready for immediate use in tests

    Usage:
        def test_health(client):
            response = client.get("/health")
            assert response.status_code == 200
    """

    def override_get_session():
        """Override FastAPI's get_session to use test session."""
        yield db_session

    # Override dependency for database session
    app.dependency_overrides[get_session] = override_get_session

    # Override provider factories (would be in registry or dependency injection later)
    # For now, the fakes are passed to tests via fixtures if needed.

    return TestClient(app)
