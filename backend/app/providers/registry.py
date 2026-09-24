"""Picks provider implementations from config. The only place that knows which vendor is in use."""

from app.config import Settings, get_settings
from app.providers import LLM, SpeechToText


def get_llm(settings: Settings | None = None) -> LLM:
    s = settings or get_settings()
    if s.llm_provider == "gemini":
        from app.providers.llm_gemini import GeminiLLM

        return GeminiLLM(s.gemini_api_key, s.gemini_model)
    if s.llm_provider == "openai":
        from app.providers.llm_openai import OpenAICompatibleLLM

        return OpenAICompatibleLLM(s.openai_api_key, s.openai_model, s.openai_base_url)
    raise ValueError(f"Unknown LLM_PROVIDER: {s.llm_provider!r}")


def get_stt(settings: Settings | None = None) -> SpeechToText:
    s = settings or get_settings()
    from app.providers.stt_groq import GroqSpeechToText

    return GroqSpeechToText(s.groq_api_key, s.groq_stt_model)
