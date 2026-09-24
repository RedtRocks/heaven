"""Contract tests for VoiceSynth providers.

Any class implementing the VoiceSynth protocol must pass these tests.
"""

import pytest

from app.providers import VoiceSynth
from tests.fakes import FakeVoiceSynth


@pytest.fixture(params=[FakeVoiceSynth])
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
