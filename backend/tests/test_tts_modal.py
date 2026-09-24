"""Tests for ModalVoiceSynth/FallbackVoiceSynth (app/providers/tts_modal.py) and the
VOICE_PROVIDER=modal registry wiring.

Uses httpx's MockTransport instead of a real network call, per docs/testing.md ("no real
API keys ... use fakes"). The Modal app itself (deploy/modal_voice/app.py) can't be tested
here - it only runs once deployed to a real Modal account, which this environment doesn't
have. See docs/agents/reports/feat-modal-voice.md for what's verified vs. left to the Owner.
"""

import base64
from pathlib import Path

import httpx
import pytest

from app.config import Settings
from app.providers import registry
from app.providers.tts_modal import FallbackVoiceSynth, ModalVoiceError, ModalVoiceSynth
from tests.fakes import FakeVoiceSynth

MINIMAL_WAV = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"


def _client_returning(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def _reset_voice_singleton():
    """get_voice() caches a singleton across calls; tests that change VOICE_PROVIDER need a
    clean slate so an earlier test's provider choice doesn't leak into a later one."""
    registry._voice_singleton = None
    yield
    registry._voice_singleton = None
    registry.clear_overrides()


@pytest.mark.unit
def test_modal_voice_synth_success_returns_audio_bytes():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=MINIMAL_WAV)

    synth = ModalVoiceSynth(
        "https://example.modal.run/speak",
        "secrettoken",
        Path("does-not-exist.wav"),
        client=_client_returning(handler),
    )
    result = synth.speak("hello")
    assert result == MINIMAL_WAV


@pytest.mark.unit
def test_modal_voice_synth_sends_bearer_token_header():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers.get("authorization")
        return httpx.Response(200, content=MINIMAL_WAV)

    synth = ModalVoiceSynth(
        "https://example.modal.run/speak",
        "my-secret-token",
        Path("does-not-exist.wav"),
        client=_client_returning(handler),
    )
    synth.speak("hello")
    assert seen["authorization"] == "Bearer my-secret-token"


@pytest.mark.unit
def test_modal_voice_synth_sends_reference_wav_when_present(tmp_path):
    reference = tmp_path / "reference.wav"
    reference.write_bytes(MINIMAL_WAV)
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        seen["body"] = json.loads(request.content)
        return httpx.Response(200, content=MINIMAL_WAV)

    synth = ModalVoiceSynth(
        "https://example.modal.run/speak",
        "token",
        reference,
        client=_client_returning(handler),
    )
    synth.speak("hello")
    assert seen["body"]["text"] == "hello"
    assert base64.b64decode(seen["body"]["reference_wav_b64"]) == MINIMAL_WAV


@pytest.mark.unit
def test_modal_voice_synth_omits_reference_when_file_missing():
    def handler(request: httpx.Request) -> httpx.Response:
        import json

        assert "reference_wav_b64" not in json.loads(request.content)
        return httpx.Response(200, content=MINIMAL_WAV)

    synth = ModalVoiceSynth(
        "https://example.modal.run/speak",
        "token",
        Path("does-not-exist.wav"),
        client=_client_returning(handler),
    )
    synth.speak("hello")


@pytest.mark.unit
def test_modal_voice_synth_raises_on_non_200():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="invalid token")

    synth = ModalVoiceSynth(
        "https://example.modal.run/speak",
        "wrong-token",
        Path("does-not-exist.wav"),
        client=_client_returning(handler),
    )
    with pytest.raises(ModalVoiceError):
        synth.speak("hello")


@pytest.mark.unit
def test_modal_voice_synth_raises_on_transport_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out")

    synth = ModalVoiceSynth(
        "https://example.modal.run/speak",
        "token",
        Path("does-not-exist.wav"),
        client=_client_returning(handler),
    )
    with pytest.raises(ModalVoiceError):
        synth.speak("hello")


@pytest.mark.unit
def test_modal_voice_synth_requires_url():
    with pytest.raises(ValueError):
        ModalVoiceSynth("", "token", Path("does-not-exist.wav"))


@pytest.mark.unit
def test_fallback_voice_synth_uses_primary_on_success():
    primary = FakeVoiceSynth()
    fallback = FakeVoiceSynth()
    synth = FallbackVoiceSynth(primary, fallback)

    synth.speak("hello")

    assert len(primary.calls) == 1
    assert len(fallback.calls) == 0


@pytest.mark.unit
def test_fallback_voice_synth_falls_back_on_primary_failure():
    class BrokenVoiceSynth:
        def speak(self, text: str) -> bytes:
            raise ModalVoiceError("boom")

    fallback = FakeVoiceSynth()
    synth = FallbackVoiceSynth(BrokenVoiceSynth(), fallback)

    result = synth.speak("hello")

    assert len(fallback.calls) == 1
    assert result.startswith(b"RIFF")


@pytest.mark.unit
def test_fallback_voice_synth_falls_back_on_timeout():
    class TimingOutVoiceSynth:
        def speak(self, text: str) -> bytes:
            raise httpx.TimeoutException("timed out")

    fallback = FakeVoiceSynth()
    synth = FallbackVoiceSynth(TimingOutVoiceSynth(), fallback)

    result = synth.speak("hello")

    assert len(fallback.calls) == 1
    assert result.startswith(b"RIFF")


@pytest.mark.unit
def test_get_voice_picks_local_by_default():
    from app.providers.tts_chatterbox import ChatterboxVoiceSynth

    settings = Settings(voice_provider="local")
    assert isinstance(registry.get_voice(settings), ChatterboxVoiceSynth)


@pytest.mark.unit
def test_get_voice_picks_modal_wrapped_in_fallback():
    settings = Settings(
        voice_provider="modal",
        modal_voice_url="https://example.modal.run/speak",
        modal_voice_token="token",
    )
    voice = registry.get_voice(settings)

    assert isinstance(voice, FallbackVoiceSynth)
    assert isinstance(voice._primary, ModalVoiceSynth)


@pytest.mark.unit
def test_get_voice_override_still_wins_over_modal():
    fake = FakeVoiceSynth()
    registry.override(voice=fake)
    settings = Settings(voice_provider="modal", modal_voice_url="https://x", modal_voice_token="t")

    assert registry.get_voice(settings) is fake
