from openai import OpenAI

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class GroqSpeechToText:
    def __init__(self, api_key: str, model: str):
        self._client = OpenAI(api_key=api_key, base_url=GROQ_BASE_URL)
        self._model = model

    def transcribe(self, audio: bytes, filename: str = "audio.wav") -> str:
        result = self._client.audio.transcriptions.create(model=self._model, file=(filename, audio))
        return result.text
