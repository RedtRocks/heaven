"""API tests for archive endpoints, with fake LLM/Embedder/STT and the test_memory DB."""

from datetime import timedelta

from fastapi.testclient import TestClient

from app.archive.api import embedder_dependency, llm_dependency, stt_dependency
from app.archive.models import Entry
from app.config import get_settings
from app.db import get_session
from app.main import app

from .fakes import FakeEmbedder, FakeLLM, memories_payload


class FakeSTT:
    def __init__(self, text: str):
        self._text = text

    def transcribe(self, audio: bytes, filename: str = "audio.wav") -> str:
        return self._text


def _client(db_session, llm=None, embedder=None, stt=None) -> TestClient:
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[llm_dependency] = lambda: llm or FakeLLM(memories_payload({"text": "Something happened."}))
    app.dependency_overrides[embedder_dependency] = lambda: embedder or FakeEmbedder()
    if stt is not None:
        app.dependency_overrides[stt_dependency] = lambda: stt
    client = TestClient(app)
    return client


def test_post_entries_creates_entry_and_memories(db_session):
    llm = FakeLLM(memories_payload({"text": "Went for a walk.", "participants": ["Riya"]}))
    client = _client(db_session, llm=llm)

    response = client.post("/entries", json={"text": "Went for a walk with Riya."})

    assert response.status_code == 200
    body = response.json()
    assert "entry_id" in body
    assert len(body["memories"]) == 1
    assert body["memories"][0]["text"] == "Went for a walk."
    app.dependency_overrides.clear()


def test_post_entries_audio_transcribes_then_splits(db_session):
    llm = FakeLLM(memories_payload({"text": "Talked about work."}))
    stt = FakeSTT("Talked about work today.")
    client = _client(db_session, llm=llm, stt=stt)

    response = client.post("/entries/audio", files={"file": ("note.wav", b"fake-audio-bytes", "audio/wav")})

    assert response.status_code == 200
    body = response.json()
    assert len(body["memories"]) == 1
    assert body["memories"][0]["text"] == "Talked about work."

    entry = db_session.get(Entry, body["entry_id"])
    assert entry.audio_path is not None
    assert entry.text == "Talked about work today."
    app.dependency_overrides.clear()


def test_get_memories_returns_owners_full_view_including_sealed(db_session):
    llm = FakeLLM(memories_payload({"text": "Doctor visit.", "sensitive_category": "health"}))
    client = _client(db_session, llm=llm)
    client.post("/entries", json={"text": "Doctor visit."})

    response = client.get("/memories")

    assert response.status_code == 200
    [memory] = response.json()
    assert memory["sealed"] is True
    assert memory["sensitive_category"] == "health"
    app.dependency_overrides.clear()


def test_patch_memory_updates_sealed_and_visibility(db_session):
    llm = FakeLLM(memories_payload({"text": "A private thought."}))
    client = _client(db_session, llm=llm)
    created = client.post("/entries", json={"text": "A private thought."}).json()
    memory_id = created["memories"][0]["id"]

    response = client.patch(f"/memories/{memory_id}", json={"proposed_visibility": "all_visitors", "owner_reviewed": True})

    assert response.status_code == 200
    body = response.json()
    assert body["proposed_visibility"] == "all_visitors"
    assert body["owner_reviewed"] is True
    app.dependency_overrides.clear()


def test_patch_memory_rejects_invalid_visibility(db_session):
    llm = FakeLLM(memories_payload({"text": "A thought."}))
    client = _client(db_session, llm=llm)
    created = client.post("/entries", json={"text": "A thought."}).json()
    memory_id = created["memories"][0]["id"]

    response = client.patch(f"/memories/{memory_id}", json={"proposed_visibility": "public"})

    assert response.status_code == 422
    app.dependency_overrides.clear()


def test_patch_memory_missing_returns_404(db_session):
    client = _client(db_session)
    response = client.patch("/memories/999999", json={"owner_reviewed": True})
    assert response.status_code == 404
    app.dependency_overrides.clear()


def test_get_digest_lists_upcoming_releases(db_session):
    llm = FakeLLM(memories_payload({"text": "Something to review."}))
    client = _client(db_session, llm=llm)
    client.post("/entries", json={"text": "Something to review."})

    response = client.get("/digest")

    assert response.status_code == 200
    body = response.json()
    holding_days = get_settings().holding_period_days
    digest_window = get_settings().digest_window_days
    if holding_days <= digest_window:
        assert len(body["items"]) == 1
        assert "Something to review." in body["text"]
    else:
        assert body["items"] == []
    app.dependency_overrides.clear()


def test_assistant_chat_says_so_plainly_when_nothing_matches(db_session):
    client = _client(db_session)

    response = client.post("/assistant/chat", json={"message": "what did I do yesterday?", "history": []})

    assert response.status_code == 200
    body = response.json()
    assert body["citations"] == []
    assert "don't have a memory" in body["reply"].lower()
    app.dependency_overrides.clear()


def test_assistant_chat_cites_recalled_memories(db_session):
    llm = FakeLLM(memories_payload({"text": "Went hiking with Riya.", "participants": ["Riya"]}))
    client = _client(db_session, llm=llm)
    created = client.post("/entries", json={"text": "Went hiking with Riya."}).json()
    memory_id = created["memories"][0]["id"]

    llm.response = f"You went hiking with Riya. [Memory {memory_id}]"
    response = client.post("/assistant/chat", json={"message": "what did I do?", "history": []})

    assert response.status_code == 200
    body = response.json()
    assert body["citations"] == [memory_id]
    app.dependency_overrides.clear()
