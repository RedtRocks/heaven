"""Contract tests for Embedder providers.

Any class implementing the Embedder protocol must pass these tests.
"""

import pytest

from app.providers import Embedder
from tests.fakes import FakeEmbedder


@pytest.fixture(params=[FakeEmbedder])
def embedder_provider(request):
    """Parametrize tests over all Embedder implementations.

    Add more implementations by importing them here and adding to params.
    Example: params=[FakeEmbedder, GeminiEmbedder, OpenAIEmbedder]
    """
    return request.param()


def test_embedder_has_dimensions(embedder_provider: Embedder):
    """Embedder must expose a dimensions attribute."""
    assert hasattr(embedder_provider, "dimensions")
    assert isinstance(embedder_provider.dimensions, int)
    assert embedder_provider.dimensions > 0


def test_embedder_embed_returns_vectors(embedder_provider: Embedder):
    """Embedder.embed() must return a list of vectors."""
    texts = ["hello", "world"]
    result = embedder_provider.embed(texts)
    assert isinstance(result, list)
    assert len(result) == len(texts)


def test_embedder_vector_dimensionality(embedder_provider: Embedder):
    """Each vector must have length equal to embedder.dimensions."""
    texts = ["hello", "world", "test"]
    vectors = embedder_provider.embed(texts)
    for vec in vectors:
        assert isinstance(vec, list)
        assert len(vec) == embedder_provider.dimensions


def test_embedder_vector_elements_are_floats(embedder_provider: Embedder):
    """Each element in a vector must be a float."""
    texts = ["hello"]
    vectors = embedder_provider.embed(texts)
    for vec in vectors:
        for val in vec:
            assert isinstance(val, (int, float))


def test_embedder_empty_text_list(embedder_provider: Embedder):
    """Embedder must handle an empty text list."""
    result = embedder_provider.embed([])
    assert result == []


def test_embedder_single_text(embedder_provider: Embedder):
    """Embedder must handle a single text."""
    result = embedder_provider.embed(["hello"])
    assert len(result) == 1
    assert len(result[0]) == embedder_provider.dimensions
