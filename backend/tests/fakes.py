"""Fake providers shared across DB-backed archive tests. No vendor SDKs, no network."""

import json
from dataclasses import dataclass, field

from app.providers import ChatMessage

DIMENSIONS = 768


@dataclass
class FakeEmbedder:
    """Deterministic Embedder: exact vectors for texts registered in `vectors`, else a
    stable pseudo-random vector derived from the text so unregistered texts still embed
    and still work with pgvector's cosine distance.
    """

    vectors: dict[str, list[float]] = field(default_factory=dict)
    dimensions: int = DIMENSIONS

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self.vectors.get(t, self._default(t)) for t in texts]

    def _default(self, text: str) -> list[float]:
        vec = [0.0] * self.dimensions
        vec[0] = 1.0
        vec[1] = (sum(ord(c) for c in text) % 1000) / 1000.0
        return vec


def near_vector(closeness: float) -> list[float]:
    """A vector whose cosine distance from `near_vector(0)` grows with `closeness`."""

    vec = [0.0] * DIMENSIONS
    vec[0] = 1.0
    vec[1] = closeness
    return vec


@dataclass
class FakeLLM:
    """Returns canned responses in order, or `response` for every call if `responses` unset."""

    response: str = ""
    responses: list[str] = field(default_factory=list)
    calls: list[tuple] = field(default_factory=list)

    def complete(self, messages: list[ChatMessage], system: str | None = None) -> str:
        self.calls.append((messages, system))
        if self.responses:
            return self.responses[len(self.calls) - 1] if len(self.calls) <= len(self.responses) else self.responses[-1]
        return self.response


def memories_payload(*memories: dict) -> str:
    return json.dumps({"memories": list(memories)})
