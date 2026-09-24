"""Voice clone via Chatterbox running on a Modal GPU (see deploy/modal_voice/app.py).

Modal gives $30/month of free credit and scales to zero, so a T4/L4-backed endpoint costs
nothing at Keepsake's traffic (docs/notes/voice-gpu.md). This provider is a thin HTTP client
for that endpoint: it POSTs {text, reference_wav_b64} to `settings.modal_voice_url` with a
shared-secret Authorization header and returns the WAV bytes.

`get_voice()` (app/providers/registry.py) wraps this in a fallback: if the Modal endpoint
fails (network error, non-2xx, timeout), it logs a warning and speaks locally with
`ChatterboxVoiceSynth` instead, so the Clone can always speak. The fallback lives in the
registry (not here) so this class stays a pure, easily-testable HTTP client — see
FallbackVoiceSynth below for the wrapper that does the falling back.

Vendor import: only `httpx`, which is a normal (non-optional) dependency, not a vendor SDK
behind an extra, so no import-inside-method dance is needed here — but this file still lives
under app/providers/ per the "one place for network/vendor calls" rule.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


class ModalVoiceError(RuntimeError):
    """The Modal voice endpoint could not be reached or returned an error."""


class ModalVoiceSynth:
    """Speaks text in the Owner's cloned voice via the Modal-hosted Chatterbox endpoint."""

    def __init__(
        self,
        url: str,
        token: str,
        reference_wav_path: Path,
        timeout_seconds: float = 30.0,
        client: httpx.Client | None = None,
    ):
        if not url:
            raise ValueError("ModalVoiceSynth requires a non-empty url (MODAL_VOICE_URL)")
        self._url = url
        self._token = token
        self._reference_wav_path = reference_wav_path
        self._timeout_seconds = timeout_seconds
        self._client = client  # allows tests to inject a mock transport

    def speak(self, text: str) -> bytes:
        payload: dict[str, str] = {"text": text}
        if self._reference_wav_path.exists():
            payload["reference_wav_b64"] = base64.b64encode(
                self._reference_wav_path.read_bytes()
            ).decode("ascii")

        headers = {"Authorization": f"Bearer {self._token}"} if self._token else {}

        try:
            if self._client is not None:
                response = self._client.post(self._url, json=payload, headers=headers)
            else:
                response = httpx.post(
                    self._url, json=payload, headers=headers, timeout=self._timeout_seconds
                )
        except httpx.HTTPError as exc:
            raise ModalVoiceError(f"Modal voice request failed: {exc}") from exc

        if response.status_code != 200:
            raise ModalVoiceError(
                f"Modal voice endpoint returned {response.status_code}: {response.text[:500]}"
            )
        return response.content


class FallbackVoiceSynth:
    """VoiceSynth that tries a primary provider and falls back to a secondary on any failure.

    Used to wire ModalVoiceSynth (fast, needs the network) with ChatterboxVoiceSynth (slow,
    always available) as its fallback, so a Modal outage or timeout never stops the Clone
    from speaking (ADR 0003: cloned voice only, but it must still work).
    """

    def __init__(self, primary, fallback):
        self._primary = primary
        self._fallback = fallback

    def speak(self, text: str) -> bytes:
        try:
            return self._primary.speak(text)
        except Exception as exc:  # noqa: BLE001 - any primary failure should fall back
            logger.warning("Modal voice provider failed (%s); falling back to local Chatterbox", exc)
            return self._fallback.speak(text)
