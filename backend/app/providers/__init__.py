"""Provider interfaces. Nothing outside this package imports a vendor SDK (see ADR 0002)."""

from dataclasses import dataclass
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
