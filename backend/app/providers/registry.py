"""Picks provider implementations from config. The only place that knows which vendor is in use.

Every get_* function checks `_overrides` first, so tests can swap in fakes with `override(...)`
no matter how the calling code obtained the provider.
"""

from app.config import Settings, get_settings
from app.providers import LLM, Embedder, SpeechToText

_overrides: dict[str, object] = {}


def override(**providers: object) -> None:
    """Force providers by kind, e.g. override(llm=FakeLLM()). Keys match the get_<kind> names."""
    _overrides.update(providers)


def clear_overrides() -> None:
    _overrides.clear()


def get_llm(settings: Settings | None = None) -> LLM:
    if "llm" in _overrides:
        return _overrides["llm"]  # type: ignore[return-value]
    s = settings or get_settings()
    if s.llm_provider == "gemini":
        from app.providers.llm_gemini import GeminiLLM

        return GeminiLLM(s.gemini_api_key, s.gemini_model)
    if s.llm_provider == "openai":
        from app.providers.llm_openai import OpenAICompatibleLLM

        return OpenAICompatibleLLM(s.openai_api_key, s.openai_model, s.openai_base_url)
    raise ValueError(f"Unknown LLM_PROVIDER: {s.llm_provider!r}")


def get_stt(settings: Settings | None = None) -> SpeechToText:
    if "stt" in _overrides:
        return _overrides["stt"]  # type: ignore[return-value]
    s = settings or get_settings()
    from app.providers.stt_groq import GroqSpeechToText

    return GroqSpeechToText(s.groq_api_key, s.groq_stt_model)


def get_embedder(settings: Settings | None = None) -> Embedder:
    if "embedder" in _overrides:
        return _overrides["embedder"]  # type: ignore[return-value]
    s = settings or get_settings()
    if s.embedder_provider == "gemini":
        from app.providers.embed_gemini import GeminiEmbedder

        return GeminiEmbedder(s.gemini_api_key, s.gemini_embedding_model, s.embedding_dimensions)
    raise ValueError(f"Unknown EMBEDDER_PROVIDER: {s.embedder_provider!r}")
