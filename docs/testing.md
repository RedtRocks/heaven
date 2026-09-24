# Testing Guide

This document describes how to run Keepsake tests, use the test fakes, and write contract tests for new provider implementations.

## Quick Start

Run all tests:

```bash
# Windows (PowerShell)
.\scripts\test.ps1

# Linux/macOS (bash)
bash scripts/test.sh

# Or just backend tests
cd backend && uv run pytest -q
```

## Test Organization

### `backend/tests/fakes.py`

Deterministic fake implementations of all Keepsake provider protocols:

- **FakeLLM**: Returns scripted replies (queue or callable). Records all calls.
- **FakeEmbedder**: Returns stable hash-based vectors of fixed dimension (default 768). Same text always produces same vector.
- **FakeSpeechToText**: Returns pre-set text.
- **FakeVoiceSynth**: Returns minimal but valid WAV bytes (RIFF header + silence).
- **FakeFaceRenderer**: Returns minimal but valid MP4 bytes (ftyp + mdat boxes).
- **FakeMemoryRecall**: Returns pre-configured memories, with simple substring matching.

All fakes record their calls in a `.calls` list for test assertions:

```python
fake_llm = FakeLLM(replies=["yes", "no"])
fake_llm.complete([ChatMessage("user", "test")])
assert len(fake_llm.calls) == 1
assert fake_llm.calls[0]["messages"][0].content == "test"
```

### `backend/tests/conftest.py`

Shared pytest fixtures:

- **db_session**: Creates test tables, yields a session, and rolls back per test.
- **client**: FastAPI TestClient with dependency overrides (uses test DB and fakes).
- **fake_llm**, **fake_embedder**, **fake_stt**, **fake_voice_synth**, **fake_face_renderer**, **fake_memory_recall**: Individual fake fixtures.

Usage:

```python
def test_example(client, fake_llm):
    response = client.get("/health")
    assert response.status_code == 200
    assert fake_llm.calls == []  # LLM was not called
```

### `backend/tests/contracts/`

Reusable contract test suites. Each module tests a protocol (LLM, Embedder, SpeechToText, VoiceSynth, FaceRenderer, MemoryRecall).

Example: `backend/tests/contracts/test_llm.py` verifies that any LLM implementation:

- Returns a string from `complete()`
- Accepts messages and optional system prompt
- Handles multi-turn conversations
- Handles edge cases (empty message list)

**To add a new provider implementation**, simply parametrize the contract tests:

```python
# In backend/tests/contracts/test_llm.py
from app.providers.llm_myimpl import MyLLM

@pytest.fixture(params=[FakeLLM, MyLLM])  # Add MyLLM here
def llm_provider(request):
    return request.param()
```

Now `pytest` will run all LLM contract tests against both FakeLLM and MyLLM.

## Pytest Markers

Three markers organize tests by type:

- `@pytest.mark.unit`: No database, no network. Fast, run by default.
- `@pytest.mark.db`: Requires test database. Included by default.
- `@pytest.mark.slow`: Long-running tests. Skipped by default.

Skip slow tests:

```bash
cd backend && uv run pytest -q  # Skips @slow tests (default)
cd backend && uv run pytest -q -m slow  # Run only @slow tests
cd backend && uv run pytest -q -m "not slow"  # Run all except @slow
```

Mark a test:

```python
@pytest.mark.slow
def test_long_operation():
    pass

@pytest.mark.db
def test_with_database(db_session):
    pass
```

## Test Database

Tests use a dedicated test database to avoid touching the live `keepsake` database:

```
postgresql+psycopg://keepsake:keepsake@127.0.0.1:5433/test_main
```

(By rule: `test_<branch>` where `<branch>` is your branch name with `feat/` removed and `-` replaced by `_`. This branch is `feat/test-infra`, so it's `test_main`.)

The test database exists and has pgvector enabled. Each test:

1. Creates all tables from `app.db.Base.metadata`
2. Wraps the test in a transaction (savepoint)
3. Rolls back the transaction after the test

This is fast (no table drops) and isolates each test.

## Architecture Tests

`backend/tests/test_architecture.py` uses AST to verify:

1. **No vendor SDK imports outside `app/providers/`**: The following are forbidden outside `app/providers/`:
   - `google` (google-genai)
   - `openai`
   - `groq`
   - `pipecat`
   - `chatterbox`
   - `kaggle`
   - `torch`
   - etc.

2. **All app modules import without error**: Catches syntax, missing deps, and circular imports.

This runs automatically with `pytest -q`.

## Contract Test Template

To add a contract for a new protocol:

1. Create `backend/tests/contracts/test_<protocol>.py`
2. Import your protocol and fake
3. Create a parametrized fixture over all implementations
4. Write tests that any implementation must pass

Example:

```python
# backend/tests/contracts/test_myprotocol.py
import pytest
from app.providers import MyProtocol
from tests.fakes import FakeMyProtocol

@pytest.fixture(params=[FakeMyProtocol])
def my_provider(request):
    return request.param()

def test_my_protocol_returns_value(my_provider: MyProtocol):
    result = my_provider.do_something()
    assert result is not None
```

Later, when you add a real implementation, just add it to `params`:

```python
@pytest.fixture(params=[FakeMyProtocol, RealMyProtocol])
def my_provider(request):
    return request.param()
```

## Rule: Every New Module Ships With Tests

Before merging:

- Add tests for your new module in `backend/tests/test_<module>.py`
- Mark appropriately with `@pytest.mark.unit`, `@pytest.mark.db`, or `@pytest.mark.slow`
- Ensure all tests pass with `cd backend && uv run pytest -q`
- No real API keys in tests; use fakes

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`) runs:

1. Backend tests on Python 3.13 with pgvector service
2. Web tests (if `web/package.json` exists): lint and build

Triggered on push to `main`, `feat/*`, `bugfix/*`, `docs/*` and PRs to `main`.

## Common Patterns

### Test with a specific fake

```python
def test_llm_usage(client, fake_llm):
    fake_llm._replies = ["custom response"]
    response = client.post("/llm/ping", json={"message": "hello"})
    assert response.status_code == 200
    assert len(fake_llm.calls) == 1
```

### Test database transactions

```python
def test_person_created(db_session):
    from app.people.models import Person
    person = Person(name="Alice")
    db_session.add(person)
    db_session.commit()
    
    # Test sees the committed change
    assert db_session.query(Person).count() == 1
    
    # After test, rollback reverts it
```

### Test memory recall

```python
def test_memory_search(client, db_session):
    from app.conversation.contracts import RecalledMemory
    from datetime import date
    
    # Set up fake memories
    memories = [
        RecalledMemory(id=1, text="Went to beach", happened_on=date(2024, 1, 1)),
    ]
    # (Inject via dependency override; details depend on your routes)
    
    response = client.get("/memories?q=beach")
    assert response.status_code == 200
```

## Troubleshooting

**`psycopg` connection refused**: Ensure `postgres:5433` is running (see docker-compose.yml).

**`DATABASE_URL` not overridden**: `conftest.py` sets it before importing `app`. If you import `app` before `conftest.py` runs, the override won't take effect. Run tests from `backend/` dir: `cd backend && uv run pytest`.

**Import errors in architecture test**: Module might be importing a vendor SDK outside `app/providers/`. Check `test_architecture.py` output; move the import into a function if you need it elsewhere.

**Fakes not recording calls**: Ensure you're using the fixture, not creating your own instance.

---

For more, see `docs/agents/common-rules.md` and the ADRs in `docs/adr/`.
