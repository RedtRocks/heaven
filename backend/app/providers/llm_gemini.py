from google import genai
from google.genai import types

from app.providers import ChatMessage


class GeminiLLM:
    def __init__(self, api_key: str, model: str):
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def complete(self, messages: list[ChatMessage], system: str | None = None) -> str:
        contents = [
            types.Content(role="model" if m.role == "assistant" else "user", parts=[types.Part(text=m.content)])
            for m in messages
        ]
        response = self._client.models.generate_content(
            model=self._model,
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=system) if system else None,
        )
        return response.text or ""
