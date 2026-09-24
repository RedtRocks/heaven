"""Picks provider implementations from config. The only place that knows which vendor is in use.

Every get_* function checks `_overrides` first, so tests can swap in fakes with `override(...)`
no matter how the calling code obtained the provider.
"""

from app.config import Settings, get_settings
from app.providers import LLM, FaceRenderer, SpeechToText, VoiceSynth

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


def get_voice(settings: Settings | None = None) -> VoiceSynth:
    if "voice" in _overrides:
        return _overrides["voice"]  # type: ignore[return-value]
    # No real VoiceSynth provider is wired up on this branch yet (voice cloning is a
    # separate piece of work). `app/face/jobs.py` only needs this for the `text` input of
    # POST /face/jobs; callers can pass `audio` directly to avoid depending on it.
    raise NotImplementedError(
        "No VoiceSynth provider is configured. Pass `audio` directly to /face/jobs instead "
        "of `text` until voice cloning is wired up."
    )


def get_face(settings: Settings | None = None) -> FaceRenderer:
    if "face" in _overrides:
        return _overrides["face"]  # type: ignore[return-value]
    s = settings or get_settings()
    if s.face_provider == "musetalk_kaggle":
        from app.providers.face_musetalk_kaggle import MuseTalkKaggleFaceRenderer

        return MuseTalkKaggleFaceRenderer(s)
    if s.face_provider == "still":
        from app.providers.face_still import StillPhotoFaceRenderer

        return StillPhotoFaceRenderer(s)
    raise ValueError(f"Unknown FACE_PROVIDER: {s.face_provider!r}")
