"""Unit tests for the voice loop's turn logic (scripts/voice_loop.py), with fake providers.

No mic, no speaker, no model: run_turn() is the hardware-free core of the push-to-talk loop.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from voice_loop import run_turn  # noqa: E402

from app.conversation.contracts import RecalledMemory
from app.providers import ChatMessage
from tests.fakes import FakeLLM, FakeMemoryRecall, FakeSpeechToText, FakeVoiceSynth


@pytest.mark.db
def test_run_turn_wires_stt_llm_recall_and_voice_together(db_session):
    fake_stt = FakeSpeechToText(text="what's my favourite food")
    fake_llm = FakeLLM(reply="You always say it's biryani.")
    fake_voice = FakeVoiceSynth()
    fake_recall = FakeMemoryRecall(
        [RecalledMemory(id=1, text="what's my favourite food: it's biryani, always has been", happened_on=None)]
    )
    history: list[ChatMessage] = []

    heard, reply, wav_bytes = run_turn(
        b"raw-audio-bytes",
        llm=fake_llm,
        stt=fake_stt,
        voice=fake_voice,
        recall=fake_recall,
        session=db_session,
        history=history,
    )

    assert heard == "what's my favourite food"
    assert reply == "You always say it's biryani."
    assert wav_bytes.startswith(b"RIFF")

    # STT got the raw audio.
    assert fake_stt.calls[0]["audio_len"] == len(b"raw-audio-bytes")
    # Recall was queried with the transcribed text, as the Owner (visitor_id=None).
    assert fake_recall.calls == [{"query": "what's my favourite food", "visitor_id": None, "k": 8}]
    # The LLM got a Clone system prompt mentioning the recalled Memory, plus the history.
    assert len(fake_llm.calls) == 1
    assert "biryani" in fake_llm.calls[0]["system"]
    assert fake_llm.calls[0]["messages"] == [ChatMessage("user", "what's my favourite food")]
    # The reply was spoken.
    assert fake_voice.calls == [{"text": "You always say it's biryani."}]
    # History now holds both turns, for the next call.
    assert history == [
        ChatMessage("user", "what's my favourite food"),
        ChatMessage("assistant", "You always say it's biryani."),
    ]


@pytest.mark.db
def test_run_turn_carries_history_across_calls(db_session):
    fake_stt = FakeSpeechToText(text="and what else")
    fake_llm = FakeLLM(reply="Just that.")
    fake_voice = FakeVoiceSynth()
    fake_recall = FakeMemoryRecall([])
    history: list[ChatMessage] = [ChatMessage("user", "hi"), ChatMessage("assistant", "hello")]

    run_turn(
        b"more-audio",
        llm=fake_llm,
        stt=fake_stt,
        voice=fake_voice,
        recall=fake_recall,
        session=db_session,
        history=history,
    )

    assert fake_llm.calls[0]["messages"] == [
        ChatMessage("user", "hi"),
        ChatMessage("assistant", "hello"),
        ChatMessage("user", "and what else"),
    ]
