from openai import OpenAI

from app.providers import ChatMessage


class OpenAICompatibleLLM:
    """OpenAI, or any OpenAI-compatible endpoint such as OpenRouter (via base_url)."""

    def __init__(self, api_key: str, model: str, base_url: str | None = None):
        self._client = OpenAI(api_key=api_key, base_url=base_url or None)
        self._model = model

    def complete(self, messages: list[ChatMessage], system: str | None = None) -> str:
        payload = [{"role": "system", "content": system}] if system else []
        payload += [{"role": m.role, "content": m.content} for m in messages]
        response = self._client.chat.completions.create(model=self._model, messages=payload)
        return response.choices[0].message.content or ""
