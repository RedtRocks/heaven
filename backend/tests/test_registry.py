import pytest

from app.config import Settings
from app.providers.llm_gemini import GeminiLLM
from app.providers.llm_openai import OpenAICompatibleLLM
from app.providers.registry import get_llm


def test_registry_picks_gemini():
    assert isinstance(get_llm(Settings(llm_provider="gemini", gemini_api_key="x")), GeminiLLM)


def test_registry_picks_openai_compatible():
    assert isinstance(get_llm(Settings(llm_provider="openai", openai_api_key="x")), OpenAICompatibleLLM)


def test_registry_rejects_unknown_provider():
    with pytest.raises(ValueError):
        get_llm(Settings(llm_provider="nope"))
