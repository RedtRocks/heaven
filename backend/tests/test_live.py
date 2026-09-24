"""Tests for live mode (ADR 0003: Memory Assistant, Stock Voice, never /clone).

No real API key exists in this environment, so these tests exercise the WebSocket relay,
tool execution and Sealed-filtering against FakeLiveSession (tests/fakes.py). A single
`@pytest.mark.live` test at the bottom exercises the real Gemini Live connection and only
runs with RUN_LIVE=1 and a real GEMINI_API_KEY set.
"""

import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.archive.models import Entry, Memory
from app.live.recall import filter_sealed, recall_for_live
from app.providers import LiveAudioChunk, LiveSessionEnded, LiveToolCall, LiveTranscript, LiveTurnComplete
from app.providers.registry import get_live
from tests.fakes import FakeEmbedder, FakeLiveSession, fake_live_factory


def _make_memory(db_session: Session, text: str, *, sealed: bool = False) -> Memory:
    entry = Entry(text=text)
    db_session.add(entry)
    db_session.flush()
    memory = Memory(
        text=text,
        entry_id=entry.id,
        embedding=FakeEmbedder().embed([text])[0],
        sealed=sealed,
        proposed_visibility="private",
        release_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db_session.add(memory)
    db_session.commit()
    db_session.refresh(memory)
    return memory


# --- Sealed filtering (the safety net: recall_for_live must never surface Sealed Memories) ---


@pytest.mark.db
def test_recall_for_live_drops_sealed_memories(db_session: Session):
    _make_memory(db_session, "The trip to the beach was wonderful", sealed=False)
    _make_memory(db_session, "The beach trip is where I hid the money", sealed=True)

    results = recall_for_live(db_session, FakeEmbedder(), "beach trip")

    assert results, "expected at least one visible memory"
    assert all("hid the money" not in m.text for m in results)


@pytest.mark.db
def test_filter_sealed_removes_only_sealed_ids(db_session: Session):
    visible = _make_memory(db_session, "Ordinary memory", sealed=False)
    sealed = _make_memory(db_session, "Sealed memory", sealed=True)

    from app.conversation.contracts import RecalledMemory

    recalled = [
        RecalledMemory(id=visible.id, text=visible.text, happened_on=None),
        RecalledMemory(id=sealed.id, text=sealed.text, happened_on=None),
    ]
    filtered = filter_sealed(db_session, recalled)

    assert [m.id for m in filtered] == [visible.id]


# --- WebSocket relay + tool execution, against FakeLiveSession ---


@pytest.mark.db
def test_relay_streams_audio_and_transcripts_from_fake_live_session(client, fake_embedder):
    from app.providers import registry

    session = FakeLiveSession(
        events=[
            LiveTranscript(text="hello", speaker="model", final=False),
            LiveAudioChunk(pcm=b"\x01\x02\x03\x04"),
            LiveTurnComplete(),
            LiveSessionEnded(reason="test done"),
        ]
    )
    registry.override(live=fake_live_factory(session))

    with client.websocket_connect("/live/assistant") as ws:
        ws.send_bytes(b"\x00\x00" * 10)  # mic audio

        msg1 = ws.receive_json()
        assert msg1 == {"type": "transcript", "speaker": "model", "text": "hello", "final": False}

        audio = ws.receive_bytes()
        assert audio == b"\x01\x02\x03\x04"

        msg2 = ws.receive_json()
        assert msg2 == {"type": "turn_complete"}

        msg3 = ws.receive_json()
        assert msg3 == {"type": "session_ended", "reason": "test done"}

    assert session.audio_sent == b"\x00\x00" * 10
    assert session.closed


@pytest.mark.db
def test_relay_executes_recall_memories_tool_call_excluding_sealed(client, db_session: Session):
    from app.providers import registry

    _make_memory(db_session, "Went hiking with Sam", sealed=False)
    _make_memory(db_session, "Secret affair details", sealed=True)

    session = FakeLiveSession(
        events=[
            LiveToolCall(call_id="call-1", name="recall_memories", args={"query": "hiking"}),
            LiveSessionEnded(reason="done"),
        ]
    )
    registry.override(live=fake_live_factory(session))

    with client.websocket_connect("/live/assistant") as ws:
        msg = ws.receive_json()
        assert msg == {"type": "session_ended", "reason": "done"}

    assert len(session.tool_results) == 1
    call_id, result = session.tool_results[0]
    assert call_id == "call-1"
    texts = [m["text"] for m in result["memories"]]
    assert any("hiking" in t for t in texts)
    assert all("affair" not in t for t in texts)


@pytest.mark.db
def test_relay_reports_unknown_tool_call(client):
    from app.providers import registry

    session = FakeLiveSession(
        events=[
            LiveToolCall(call_id="call-2", name="delete_everything", args={}),
            LiveSessionEnded(reason="done"),
        ]
    )
    registry.override(live=fake_live_factory(session))

    with client.websocket_connect("/live/assistant") as ws:
        ws.receive_json()

    assert session.tool_results == [("call-2", {"error": "Unknown tool 'delete_everything'"})]


# --- Real Gemini Live connection: no API key in this environment, so this only runs
# with RUN_LIVE=1 and a real GEMINI_API_KEY (see tests/conftest.py, docs/testing.md). ---


@pytest.mark.live
@pytest.mark.asyncio
async def test_real_gemini_live_session_connects():
    from app.config import Settings

    settings = Settings(gemini_api_key=os.environ.get("GEMINI_API_KEY", ""))
    assert settings.gemini_api_key, "GEMINI_API_KEY must be set for this test"

    live = await get_live(
        system_instruction="You are a test assistant. Say hello.",
        tools=[],
        settings=settings,
    )
    try:
        await live.send_audio(b"\x00\x00" * 1600)  # 100ms of silence at 16kHz
        async for event in live.receive():
            assert event is not None
            break
    finally:
        await live.close()
