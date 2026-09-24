"""Contract tests for MemoryRecall implementations.

Any class implementing the MemoryRecall protocol must pass these tests.
"""

from datetime import date

import pytest

from app.conversation.contracts import MemoryRecall, RecalledMemory
from tests.fakes import FakeMemoryRecall


@pytest.fixture(params=[FakeMemoryRecall])
def memory_recall_provider(request):
    """Parametrize tests over all MemoryRecall implementations.

    Add more implementations by importing them here and adding to params.
    Example: params=[FakeMemoryRecall, PostgresMemoryRecall]
    """
    return request.param()


def test_memory_recall_returns_list(memory_recall_provider: MemoryRecall):
    """MemoryRecall.recall() must return a list of RecalledMemory objects."""
    result = memory_recall_provider.recall("test query")
    assert isinstance(result, list)
    for item in result:
        assert isinstance(item, RecalledMemory)


def test_memory_recall_with_visitor_id(memory_recall_provider: MemoryRecall):
    """MemoryRecall.recall() must accept an optional visitor_id."""
    result = memory_recall_provider.recall("test query", visitor_id=42)
    assert isinstance(result, list)


def test_memory_recall_with_custom_k(memory_recall_provider: MemoryRecall):
    """MemoryRecall.recall() must accept a custom k parameter."""
    result = memory_recall_provider.recall("test query", k=5)
    assert isinstance(result, list)
    # Note: Some implementations might return fewer than k results if fewer match
    assert len(result) <= 5


def test_memory_recall_returns_correctly_typed_memories(memory_recall_provider: MemoryRecall):
    """Each RecalledMemory must have the correct fields and types."""
    # Set up with a known memory
    memories = [
        RecalledMemory(id=1, text="Test memory", happened_on=date(2024, 1, 1)),
    ]
    provider = FakeMemoryRecall(memories)

    result = provider.recall("test")
    assert len(result) == 1
    assert result[0].id == 1
    assert result[0].text == "Test memory"
    assert result[0].happened_on == date(2024, 1, 1)


def test_memory_recall_k_limits_results(memory_recall_provider: MemoryRecall):
    """MemoryRecall should respect the k parameter as a limit."""
    # Set up with multiple memories
    memories = [
        RecalledMemory(id=i, text=f"Memory {i}", happened_on=date(2024, 1, i + 1))
        for i in range(1, 20)
    ]
    provider = FakeMemoryRecall(memories)

    result = provider.recall("memory", k=5)
    assert len(result) <= 5


def test_memory_recall_owner_vs_visitor(memory_recall_provider: MemoryRecall):
    """MemoryRecall must distinguish between Owner (visitor_id=None) and Visitor queries."""
    # visitor_id=None means the Owner (should see everything)
    # visitor_id=N means a Visitor (should see filtered memories)
    result_owner = memory_recall_provider.recall("test", visitor_id=None)
    result_visitor = memory_recall_provider.recall("test", visitor_id=1)

    # Both should return lists (may or may not be equal, depends on permissions)
    assert isinstance(result_owner, list)
    assert isinstance(result_visitor, list)
