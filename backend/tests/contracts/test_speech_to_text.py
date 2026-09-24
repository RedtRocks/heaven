"""Contract tests for SpeechToText providers.

Any class implementing the SpeechToText protocol must pass these tests.
"""

import pytest

from app.providers import SpeechToText
from tests.fakes import FakeSpeechToText


@pytest.fixture(params=[FakeSpeechToText])
def stt_provider(request):
    """Parametrize tests over all SpeechToText implementations.

    Add more implementations by importing them here and adding to params.
    Example: params=[FakeSpeechToText, GroqSpeechToText]
    """
    return request.param()


def test_stt_transcribe_returns_string(stt_provider: SpeechToText):
    """SpeechToText.transcribe() must return a string."""
    audio = b"dummy audio data"
    result = stt_provider.transcribe(audio)
    assert isinstance(result, str)


def test_stt_transcribe_accepts_filename(stt_provider: SpeechToText):
    """SpeechToText.transcribe() must accept an optional filename."""
    audio = b"dummy audio data"
    result = stt_provider.transcribe(audio, filename="test.wav")
    assert isinstance(result, str)


def test_stt_transcribe_handles_empty_audio(stt_provider: SpeechToText):
    """SpeechToText.transcribe() must handle empty audio (edge case)."""
    result = stt_provider.transcribe(b"")
    assert isinstance(result, str)


def test_stt_transcribe_handles_large_audio(stt_provider: SpeechToText):
    """SpeechToText.transcribe() must handle large audio data."""
    # 1MB of dummy audio
    audio = b"\x00" * (1024 * 1024)
    result = stt_provider.transcribe(audio)
    assert isinstance(result, str)
