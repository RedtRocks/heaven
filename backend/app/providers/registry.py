"""Picks provider implementations from config. The only place that knows which vendor is in use.

Every get_* function checks `_overrides` first, so tests can swap in fakes with `override(...)`
no matter how the calling code obtained the provider.
"""

from app.config import Settings, get_settings
from app.providers import LLM, Embedder, FaceRenderer, SpeechToText, VoiceSynth

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


_voice_singleton: VoiceSynth | None = None


def get_voice(settings: Settings | None = None) -> VoiceSynth:
    """Cached across calls: Chatterbox's model is slow to load, so we load it once."""
    if "voice" in _overrides:
        return _overrides["voice"]  # type: ignore[return-value]
    global _voice_singleton
    if _voice_singleton is None:
        s = settings or get_settings()
        from app.providers.tts_chatterbox import ChatterboxVoiceSynth

        reference_path = s.likeness_dir / "voice" / "reference.wav"
        _voice_singleton = ChatterboxVoiceSynth(reference_path)
    return _voice_singleton


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
>>>>>>> main
