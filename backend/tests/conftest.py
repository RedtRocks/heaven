"""Shared test setup. Uses the branch's own Postgres test database (never the
main `keepsake` database), per docs/agents/common-rules.md.
"""

import os

TEST_DATABASE_URL = "postgresql+psycopg://keepsake:keepsake@127.0.0.1:5433/test_seed"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

import pytest  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.db import Base  # noqa: E402
from app.people import models as _people_models  # noqa: E402,F401
from app.persona import models as _persona_models  # noqa: E402,F401


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
def db_session(db_engine):
    connection = db_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
