"""Contract tests for LLM providers.

Any class implementing the LLM protocol must pass these tests.
"""

import pytest

from app.providers import ChatMessage, LLM
from tests.fakes import FakeLLM


@pytest.fixture(params=[FakeLLM])
def llm_provider(request):
    """Parametrize tests over all LLM implementations.

    Add more implementations by importing them here and adding to params.
    Example: params=[FakeLLM, GeminiLLM, OpenAICompatibleLLM]
    """
    return request.param()


def test_llm_complete_returns_string(llm_provider: LLM):
    """LLM.complete() must return a string."""
    result = llm_provider.complete([ChatMessage("user", "hello")])
    assert isinstance(result, str)


def test_llm_complete_accepts_system_prompt(llm_provider: LLM):
    """LLM.complete() must accept an optional system prompt."""
    result = llm_provider.complete(
        [ChatMessage("user", "hello")],
        system="You are a helpful assistant.",
    )
    assert isinstance(result, str)


def test_llm_complete_handles_multi_message_conversation(llm_provider: LLM):
    """LLM.complete() must handle multi-turn conversations."""
    messages = [
        ChatMessage("user", "What is 2+2?"),
        ChatMessage("assistant", "4"),
        ChatMessage("user", "And 3+3?"),
    ]
    result = llm_provider.complete(messages)
    assert isinstance(result, str)


def test_llm_complete_handles_empty_message_list(llm_provider: LLM):
    """LLM.complete() must handle an empty message list (edge case)."""
    result = llm_provider.complete([])
    assert isinstance(result, str)
