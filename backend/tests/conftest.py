"""Shared test fixtures.

Per docs/agents/common-rules.md section 7: DB tests use ONLY this branch's own test
database (test_memory), never the `keepsake` database that other agents' processes use.
We point a dedicated engine at it directly rather than relying on .env / Settings, so
these tests can't accidentally hit the real database.
"""

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.archive import models as _archive_models  # noqa: F401  (registers tables on Base)
from app.db import Base
from app.people import models as _people_models  # noqa: F401  (registers tables on Base)

TEST_DATABASE_URL = "postgresql+psycopg://keepsake:keepsake@127.0.0.1:5433/test_memory"


@pytest.fixture(scope="session")
def db_engine():
    engine = create_engine(TEST_DATABASE_URL)
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(db_engine) -> Iterator[Session]:
    """A session whose writes are rolled back after each test, so tests don't collide."""

    connection = db_engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
