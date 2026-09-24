"""Provider interfaces. Nothing outside this package imports a vendor SDK (see ADR 0002)."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Literal, Protocol


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["user", "assistant"]
    content: str


class LLM(Protocol):
    def complete(self, messages: list[ChatMessage], system: str | None = None) -> str: ...


class Embedder(Protocol):
    dimensions: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class SpeechToText(Protocol):
    def transcribe(self, audio: bytes, filename: str = "audio.wav") -> str: ...


class VoiceSynth(Protocol):
    """Speaks text in the Owner's cloned voice. Returns WAV bytes."""

    def speak(self, text: str) -> bytes: ...


class FaceRenderer(Protocol):
    """Renders the Owner's face saying the given audio. Returns MP4 bytes."""

    def render(self, audio_wav: bytes) -> bytes: ...


# --- Live mode (Memory Assistant only, Stock Voice - see ADR 0003) ---


@dataclass(frozen=True)
class LiveAudioChunk:
    """A chunk of model speech audio: 16-bit PCM, little-endian, mono."""

    pcm: bytes
    sample_rate_hz: int = 24000


@dataclass(frozen=True)
class LiveTranscript:
    """A piece of transcript text, either what the user said or what the model said."""

    text: str
    speaker: Literal["user", "model"]
    final: bool = True


@dataclass(frozen=True)
class LiveToolCall:
    """The model asking to run a server-side tool. Reply with `send_tool_result`."""

    call_id: str
    name: str
    args: dict = field(default_factory=dict)


@dataclass(frozen=True)
class LiveTurnComplete:
    """The model has finished its turn (finished speaking)."""


@dataclass(frozen=True)
class LiveSessionEnded:
    """The vendor session ended (e.g. the ~10 minute connection limit). `reason` is for logs/UI."""

    reason: str


LiveEvent = LiveAudioChunk | LiveTranscript | LiveToolCall | LiveTurnComplete | LiveSessionEnded


class LiveVoiceSession(Protocol):
    """One open speech-to-speech session with a Stock Voice model (e.g. Gemini Live).

    Vendor SDKs live only in `app/providers/live_*.py` behind this Protocol (ADR 0002).
    """

    async def send_audio(self, pcm: bytes) -> None:
        """Send a chunk of the user's mic audio: 16-bit PCM, little-endian, mono, 16 kHz."""
        ...

    async def send_tool_result(self, call_id: str, result: object) -> None:
        """Answer a LiveToolCall with its result (JSON-serialisable)."""
        ...

    def receive(self) -> AsyncIterator[LiveEvent]:
        """Yields events from the model until the session ends."""
        ...

    async def close(self) -> None:
        """Release the underlying connection."""
        ...
