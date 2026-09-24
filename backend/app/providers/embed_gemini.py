from google import genai
from google.genai import types


class GeminiEmbedder:
    """Embedder backed by Gemini's text embedding model (see ADR 0002).

    Uses `output_dimensionality` to truncate Gemini's embeddings (trained with Matryoshka
    Representation Learning, so truncation stays meaningful) to a size that's cheap to
    store and index in pgvector.
    """

    def __init__(self, api_key: str, model: str, dimensions: int):
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self._client.models.embed_content(
            model=self._model,
            contents=texts,
            config=types.EmbedContentConfig(output_dimensionality=self.dimensions),
        )
        return [list(e.values or []) for e in response.embeddings or []]
