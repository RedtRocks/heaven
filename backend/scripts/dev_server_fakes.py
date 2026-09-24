"""Run the backend with fake providers, for UI work and browser testing without API keys.

    cd backend && uv run python scripts/dev_server_fakes.py

Uses the real local database, but every LLM/STT/embedding/voice/face call returns canned
output from tests/fakes.py. Never use this for real Memories.
"""

import sys
from pathlib import Path

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402
from app.providers import registry  # noqa: E402
from tests.fakes import (  # noqa: E402
    FakeEmbedder,
    FakeFaceRenderer,
    FakeLLM,
    FakeSpeechToText,
    FakeVoiceSynth,
)

CANNED_REPLY = (
    "Hey! It's so good to hear from you. Honestly, I was just thinking about that trip "
    "we kept planning and never took. We should still do it, you know."
)

registry.override(
    llm=FakeLLM(reply=CANNED_REPLY),
    stt=FakeSpeechToText(text="Today I finally finished the project and felt proud."),
    embedder=FakeEmbedder(),
    voice=FakeVoiceSynth(),
    face=FakeFaceRenderer(),
)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
