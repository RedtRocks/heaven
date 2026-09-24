"""Contract tests for FaceRenderer providers.

Any class implementing the FaceRenderer protocol must pass these tests.
"""

import pytest

from app.providers import FaceRenderer
from tests.fakes import FakeFaceRenderer, FakeVoiceSynth


@pytest.fixture(params=[FakeFaceRenderer])
def face_renderer_provider(request):
    """Parametrize tests over all FaceRenderer implementations.

    Add more implementations by importing them here and adding to params.
    Example: params=[FakeFaceRenderer, LivePortraitRenderer]
    """
    return request.param()


def test_face_renderer_render_returns_bytes(face_renderer_provider: FaceRenderer):
    """FaceRenderer.render() must return bytes."""
    # Create a valid WAV file first
    voice_synth = FakeVoiceSynth()
    wav_data = voice_synth.speak("Hello world")

    result = face_renderer_provider.render(wav_data)
    assert isinstance(result, bytes)


def test_face_renderer_render_returns_mp4(face_renderer_provider: FaceRenderer):
    """FaceRenderer.render() must return MP4 bytes (ftyp header)."""
    voice_synth = FakeVoiceSynth()
    wav_data = voice_synth.speak("Hello world")

    result = face_renderer_provider.render(wav_data)
    # All MP4 files contain an ftyp box
    assert b"ftyp" in result


def test_face_renderer_render_handles_empty_audio(face_renderer_provider: FaceRenderer):
    """FaceRenderer.render() must handle empty audio (edge case)."""
    result = face_renderer_provider.render(b"")
    assert isinstance(result, bytes)
    assert b"ftyp" in result


def test_face_renderer_render_handles_various_audio_sizes(face_renderer_provider: FaceRenderer):
    """FaceRenderer.render() must handle audio of various sizes."""
    # Small audio
    result = face_renderer_provider.render(b"\x00" * 100)
    assert isinstance(result, bytes)

    # Large audio
    result = face_renderer_provider.render(b"\x00" * (1024 * 1024))
    assert isinstance(result, bytes)
