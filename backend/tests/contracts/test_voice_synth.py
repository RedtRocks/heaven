"""Contract tests for VoiceSynth providers.

Any class implementing the VoiceSynth protocol must pass these tests.
"""

from pathlib import Path

import httpx
import pytest

from app.providers import VoiceSynth
from tests.fakes import FakeVoiceSynth

try:
    import chatterbox  # noqa: F401

    HAS_CHATTERBOX = True
except ImportError:
    HAS_CHATTERBOX = False

# A minimal but valid WAV: RIFF/WAVE header, fmt chunk, empty data chunk.
_MINIMAL_WAV = (
    b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00"
    b"\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
)


def _make_chatterbox():
    from app.providers.tts_chatterbox import ChatterboxVoiceSynth

    # No reference clip needed for the contract test: ChatterboxVoiceSynth falls back to
    # the model's default voice when the reference path doesn't exist.
    return ChatterboxVoiceSynth(Path("does-not-exist.wav"))


def _make_modal_voice_synth():
    from app.providers.tts_modal import ModalVoiceSynth

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_MINIMAL_WAV)

    # Real HTTP semantics (headers, JSON body, status handling) via a fake transport - no
    # real Modal endpoint is reachable from this environment. See
    # backend/tests/test_tts_modal.py for the fuller unit tests (auth header, timeouts,
    # fallback behaviour).
    return ModalVoiceSynth(
        "https://example.modal.run/speak",
        "token",
        Path("does-not-exist.wav"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


@pytest.fixture(
    params=[
        FakeVoiceSynth,
        pytest.param(
            _make_chatterbox,
            marks=[
                pytest.mark.slow,
                pytest.mark.skipif(not HAS_CHATTERBOX, reason="voice extra (chatterbox-tts) not installed"),
            ],
            id="ChatterboxVoiceSynth",
        ),
        pytest.param(_make_modal_voice_synth, id="ModalVoiceSynth"),
    ]
)
def voice_synth_provider(request):
    """Parametrize tests over all VoiceSynth implementations.

    Add more implementations by importing them here and adding to params.
    Example: params=[FakeVoiceSynth, ElevenLabsVoiceSynth]
    """
    return request.param()


def test_voice_synth_speak_returns_bytes(voice_synth_provider: VoiceSynth):
    """VoiceSynth.speak() must return bytes."""
    result = voice_synth_provider.speak("Hello world")
    assert isinstance(result, bytes)


def test_voice_synth_speak_returns_wav(voice_synth_provider: VoiceSynth):
    """VoiceSynth.speak() must return WAV bytes (RIFF header)."""
    result = voice_synth_provider.speak("Hello world")
    # All WAV files start with RIFF magic number
    assert result.startswith(b"RIFF")


def test_voice_synth_speak_handles_empty_text(voice_synth_provider: VoiceSynth):
    """VoiceSynth.speak() must handle empty text."""
    result = voice_synth_provider.speak("")
    assert isinstance(result, bytes)
    assert result.startswith(b"RIFF")


def test_voice_synth_speak_handles_long_text(voice_synth_provider: VoiceSynth):
    """VoiceSynth.speak() must handle long text."""
    long_text = "Hello world. " * 100  # Repeat to make it long
    result = voice_synth_provider.speak(long_text)
    assert isinstance(result, bytes)
    assert result.startswith(b"RIFF")
