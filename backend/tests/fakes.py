"""Fake providers for tests. No real API keys or network calls."""

from app.providers import ChatMessage


class FakeLLM:
    """Returns a fixed reply, or one keyed by the last user message."""

    def __init__(self, reply: str = "[]", by_message: dict[str, str] | None = None):
        self.reply = reply
        self.by_message = by_message or {}
        self.calls: list[tuple[list[ChatMessage], str | None]] = []

    def complete(self, messages: list[ChatMessage], system: str | None = None) -> str:
        self.calls.append((messages, system))
        last_user = messages[-1].content if messages else ""
        return self.by_message.get(last_user, self.reply)


class FakeSTT:
    def __init__(self, text: str = "transcribed text"):
        self.text = text

    def transcribe(self, audio: bytes, filename: str = "audio.wav") -> str:
        return self.text
