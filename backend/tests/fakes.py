"""Deterministic fake implementations of Keepsake providers for testing.

Each fake returns stable, predictable results (no API calls). All fakes support
recording calls for assertion. Example:

    fake_llm = FakeLLM()
    result = fake_llm.complete([...])
    assert fake_llm.calls == [({'messages': [...], 'system': None})]
"""

import hashlib
from collections.abc import AsyncIterator
from datetime import date
from typing import Callable

from app.conversation.contracts import MemoryRecall, RecalledMemory
from app.providers import ChatMessage, Embedder, FaceRenderer, LiveEvent, LLM, SpeechToText, VoiceSynth


class FakeLLM:
    """LLM that returns scripted replies.

    Usage:
        fake_llm = FakeLLM(replies=['yes', 'no', 'maybe'])
        result = fake_llm.complete([...])  # Returns 'yes'
        result = fake_llm.complete([...])  # Returns 'no'
    """

    def __init__(
        self,
        replies: list[str] | Callable[[list[ChatMessage], str | None], str] | None = None,
        reply: str | None = None,
    ):
        """Initialize with scripted replies or a callable.

        Args:
            replies: Either a list of strings (cycled in order) or a callable that takes
                    (messages, system) and returns a string.
        """
        # `reply` is shorthand for a single reply returned every time
        self._replies = replies or ([reply] if reply is not None else ["OK"])
        self._index = 0
        self.calls: list[dict] = []

    @property
    def reply(self) -> str:
        return self._replies[0] if isinstance(self._replies, list) else ""

    @reply.setter
    def reply(self, value: str) -> None:
        """Switch to always returning `value`."""
        self._replies = [value]
        self._index = 0

    def complete(self, messages: list[ChatMessage], system: str | None = None) -> str:
        """Return the next scripted reply and record the call."""
        self.calls.append({"messages": messages, "system": system})

        if callable(self._replies):
            return self._replies(messages, system)

        reply = self._replies[self._index % len(self._replies)]
        self._index += 1
        return reply


class FakeEmbedder:
    """Embedder that returns stable hash-based vectors.

    The same text always produces the same vector, making tests deterministic.
    Vectors are of a fixed dimension (default 768, matching most models).
    """

    def __init__(self, dimensions: int = 768):
        """Initialize with vector dimensionality."""
        self.dimensions = dimensions
        self.calls: list[dict] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return stable vectors derived from text hash."""
        self.calls.append({"texts": texts})

        vectors = []
        for text in texts:
            # Generate a stable vector from text hash. Use the hash to seed
            # pseudo-random floats in [-1, 1], normalized.
            # hashlib, not hash(): str hashes are randomized per process
            h = int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "big")
            vector = []
            for i in range(self.dimensions):
                # Use hash and index to generate a stable pseudo-random float
                val = ((h ^ (i * 73856093)) % 10000) / 10000.0 - 0.5
                vector.append(val)

            # Normalize to unit length (common for embeddings)
            norm = sum(v * v for v in vector) ** 0.5
            if norm > 0:
                vector = [v / norm for v in vector]

            vectors.append(vector)

        return vectors


class FakeSpeechToText:
    """SpeechToText that returns pre-set text.

    Usage:
        fake_stt = FakeSpeechToText(text="Hello world")
        result = fake_stt.transcribe(audio_bytes)  # Always returns "Hello world"
    """

    def __init__(self, text: str = "transcribed text"):
        """Initialize with the text to return."""
        self.text = text
        self.calls: list[dict] = []

    def transcribe(self, audio: bytes, filename: str = "audio.wav") -> str:
        """Return the pre-set text and record the call."""
        self.calls.append({"audio_len": len(audio), "filename": filename})
        return self.text


class FakeVoiceSynth:
    """VoiceSynth that returns a valid tiny WAV file.

    Uses a minimal WAV structure (44-byte header + silence). The same text
    always produces the same WAV (for determinism).
    """

    def __init__(self):
        """Initialize with a minimal WAV template."""
        self.calls: list[dict] = []
        # Minimal valid WAV: 44-byte header + 1000 bytes of silence (16-bit, 16kHz, mono)
        # This is enough for testing without bloating test data.
        self._wav_template = self._make_minimal_wav()

    @staticmethod
    def _make_minimal_wav() -> bytes:
        """Create a minimal valid WAV file (silence, 16kHz, 16-bit mono)."""
        import struct

        # WAV file format: RIFF header, fmt subchunk, data subchunk
        sample_rate = 16000
        num_samples = 1000
        bytes_per_sample = 2  # 16-bit = 2 bytes

        # Audio data (1000 samples of silence = 2000 bytes)
        audio_data = b"\x00" * (num_samples * bytes_per_sample)

        # Subchunk2 size (audio data size)
        subchunk2_size = len(audio_data)

        # fmt subchunk
        fmt_subchunk = struct.pack(
            "<HHIIHH",
            1,  # AudioFormat (1 = PCM)
            1,  # NumChannels (1 = mono)
            sample_rate,  # SampleRate
            sample_rate * bytes_per_sample,  # ByteRate
            bytes_per_sample,  # BlockAlign
            16,  # BitsPerSample
        )

        # RIFF header
        file_size = 36 + len(fmt_subchunk) + subchunk2_size
        wav = (
            b"RIFF"
            + struct.pack("<I", file_size)
            + b"WAVE"
            + b"fmt "
            + struct.pack("<I", len(fmt_subchunk))
            + fmt_subchunk
            + b"data"
            + struct.pack("<I", subchunk2_size)
            + audio_data
        )

        return wav

    def speak(self, text: str) -> bytes:
        """Return a valid WAV file and record the call."""
        self.calls.append({"text": text})
        return self._wav_template


class FakeFaceRenderer:
    """FaceRenderer that returns a minimal MP4 file.

    Uses a minimal MP4 structure (ftyp + mdat boxes). Deterministic but
    not a playable video—just enough structure to test file handling.
    """

    def __init__(self):
        """Initialize with a minimal MP4 template."""
        self.calls: list[dict] = []
        self._mp4_template = self._make_minimal_mp4()

    @staticmethod
    def _make_minimal_mp4() -> bytes:
        """Create a minimal valid MP4 file structure (not playable, for testing only)."""
        import struct

        # Minimal MP4: ftyp box + mdat box with small video data
        # ftyp box (File Type Box)
        ftyp_data = (
            b"isom"  # Major brand
            + struct.pack(">I", 512)  # Minor version
            + b"isomiso2avc1"  # Compatible brands (minimum)
        )
        ftyp_box = b"ftyp" + struct.pack(">I", 20 + len(ftyp_data)) + ftyp_data

        # mdat box (Media Data Box) with minimal video data
        video_data = b"\x00" * 100  # 100 bytes of dummy video data
        mdat_box = b"mdat" + struct.pack(">I", 8 + len(video_data)) + video_data

        return ftyp_box + mdat_box

    def render(self, audio_wav: bytes) -> bytes:
        """Return a minimal MP4 file and record the call."""
        self.calls.append({"audio_len": len(audio_wav)})
        return self._mp4_template


class FakeMemoryRecall:
    """MemoryRecall that returns pre-configured memories.

    Usage:
        memories = [
            RecalledMemory(id=1, text="Went to the beach", happened_on=date(2024, 1, 1)),
            RecalledMemory(id=2, text="Had coffee with Alice", happened_on=date(2024, 1, 2)),
        ]
        fake_recall = FakeMemoryRecall(memories)
        result = fake_recall.recall("beach")  # Returns [RecalledMemory(...)]
    """

    def __init__(self, memories: list[RecalledMemory] | None = None):
        """Initialize with a set of memories to return.

        Args:
            memories: List of RecalledMemory objects. All queries return these (or a subset).
        """
        self._memories = memories or []
        self.calls: list[dict] = []

    def recall(self, query: str, visitor_id: int | None = None, k: int = 8) -> list[RecalledMemory]:
        """Return configured memories and record the call."""
        self.calls.append({"query": query, "visitor_id": visitor_id, "k": k})

        # Simple substring matching for determinism (tests can set specific memories)
        matching = [m for m in self._memories if query.lower() in m.text.lower()]
        return matching[:k]


class FakeLiveSession:
    """LiveVoiceSession that plays back a scripted list of LiveEvents.

    Usage:
        session = FakeLiveSession(events=[LiveToolCall(...), LiveAudioChunk(...)])
        async for event in session.receive():
            ...
        session.audio_sent  # bytes passed to send_audio, concatenated
        session.tool_results  # [(call_id, result), ...]
    """

    def __init__(self, events: list[LiveEvent] | None = None):
        self._events = events or []
        self.audio_sent = b""
        self.tool_results: list[tuple[str, object]] = []
        self.closed = False
        self.calls: list[dict] = []

    async def send_audio(self, pcm: bytes) -> None:
        self.calls.append({"send_audio": pcm})
        self.audio_sent += pcm

    async def send_tool_result(self, call_id: str, result: object) -> None:
        self.calls.append({"send_tool_result": (call_id, result)})
        self.tool_results.append((call_id, result))

    async def receive(self) -> AsyncIterator[LiveEvent]:
        for event in self._events:
            yield event

    async def close(self) -> None:
        self.closed = True


def fake_live_factory(session: "FakeLiveSession"):
    """Wraps a FakeLiveSession so it can be used as a `live` registry override: the
    registry calls `await get_live(system_instruction, tools)`, so the override must be
    an async callable, not the session itself."""

    async def factory(system_instruction: str, tools: list[dict]) -> "FakeLiveSession":
        factory.system_instruction = system_instruction  # type: ignore[attr-defined]
        factory.tools = tools  # type: ignore[attr-defined]
        return session

    return factory
