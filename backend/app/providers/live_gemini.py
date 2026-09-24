"""Gemini Live API adapter (ADR 0003: Memory Assistant / Stock Voice only, never the Clone).

Vendor import lives only here, behind the LiveVoiceSession Protocol (app/providers/__init__.py).
Uses `google-genai`'s `client.aio.live.connect`, per docs/notes/live-mode.md.
"""

from collections.abc import AsyncIterator

from google import genai
from google.genai import types

from app.providers import (
    LiveAudioChunk,
    LiveEvent,
    LiveSessionEnded,
    LiveToolCall,
    LiveTranscript,
    LiveTurnComplete,
)

# Gemini Live sends/expects raw 16-bit PCM at these rates (docs/notes/live-mode.md).
INPUT_SAMPLE_RATE_HZ = 16000
OUTPUT_SAMPLE_RATE_HZ = 24000


class GeminiLiveSession:
    """One open Gemini Live connection. Construct via `GeminiLiveSession.connect(...)`."""

    def __init__(self, connection, session_cm):
        self._connection = connection
        self._session_cm = session_cm  # kept alive so __aexit__ can close it
        self._ended = False

    @classmethod
    async def connect(
        cls,
        api_key: str,
        model: str,
        voice: str,
        system_instruction: str,
        tools: list[dict],
    ) -> "GeminiLiveSession":
        client = genai.Client(api_key=api_key)
        function_declarations = [types.FunctionDeclaration(**t) for t in tools]
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice))
            ),
            system_instruction=types.Content(parts=[types.Part(text=system_instruction)]),
            tools=[types.Tool(function_declarations=function_declarations)] if function_declarations else None,
            output_audio_transcription=types.AudioTranscriptionConfig(),
            input_audio_transcription=types.AudioTranscriptionConfig(),
        )
        session_cm = client.aio.live.connect(model=model, config=config)
        connection = await session_cm.__aenter__()
        return cls(connection, session_cm)

    async def send_audio(self, pcm: bytes) -> None:
        await self._connection.send_realtime_input(
            audio=types.Blob(data=pcm, mime_type=f"audio/pcm;rate={INPUT_SAMPLE_RATE_HZ}")
        )

    async def send_tool_result(self, call_id: str, result: object) -> None:
        await self._connection.send_tool_response(
            function_responses=[types.FunctionResponse(id=call_id, name="recall_memories", response={"result": result})]
        )

    async def receive(self) -> AsyncIterator[LiveEvent]:
        try:
            async for message in self._connection.receive():
                for event in self._translate(message):
                    yield event
        except Exception as exc:  # vendor connection dropped (e.g. ~10 min limit)
            self._ended = True
            yield LiveSessionEnded(reason=str(exc) or "connection closed")

    def _translate(self, message) -> list[LiveEvent]:
        events: list[LiveEvent] = []
        server_content = getattr(message, "server_content", None)

        if server_content is not None:
            model_turn = getattr(server_content, "model_turn", None)
            if model_turn is not None:
                for part in model_turn.parts or []:
                    inline = getattr(part, "inline_data", None)
                    if inline is not None and inline.data:
                        events.append(LiveAudioChunk(pcm=inline.data, sample_rate_hz=OUTPUT_SAMPLE_RATE_HZ))

            out_transcript = getattr(server_content, "output_transcription", None)
            if out_transcript is not None and out_transcript.text:
                events.append(LiveTranscript(text=out_transcript.text, speaker="model", final=bool(server_content.turn_complete)))

            in_transcript = getattr(server_content, "input_transcription", None)
            if in_transcript is not None and in_transcript.text:
                events.append(LiveTranscript(text=in_transcript.text, speaker="user", final=True))

            if getattr(server_content, "turn_complete", False):
                events.append(LiveTurnComplete())

        tool_call = getattr(message, "tool_call", None)
        if tool_call is not None:
            for call in tool_call.function_calls or []:
                events.append(LiveToolCall(call_id=call.id, name=call.name, args=dict(call.args or {})))

        return events

    async def close(self) -> None:
        if self._ended:
            return
        await self._session_cm.__aexit__(None, None, None)
