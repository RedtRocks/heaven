"""Live mode: the Memory Assistant over a WebSocket, speech-to-speech (ADR 0003).

The browser streams mic PCM (16 kHz, 16-bit LE, mono) as binary WebSocket frames. We relay
it to a Gemini Live session (via LiveVoiceSession, app/providers) and relay the model's
audio and transcripts back as binary frames / JSON text frames. `recall_memories` tool
calls are executed here, against the archive, for the Owner (visitor_id=None) - with Sealed
Memories filtered out before anything is sent to the vendor (app/live/recall.py).

Never used by /clone: Gemini Live is a Stock Voice, and the Clone speaks only in the
Owner's cloned voice (ADR 0003).
"""

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.db import get_session
from app.live.recall import MEMORY_ASSISTANT_SYSTEM_PROMPT, RECALL_MEMORIES_TOOL, recall_for_live, recalled_memories_to_tool_result
from app.providers import LiveAudioChunk, LiveSessionEnded, LiveToolCall, LiveTranscript, LiveTurnComplete
from app.providers.registry import get_embedder, get_live

logger = logging.getLogger("uvicorn.error")

router = APIRouter()


@router.websocket("/live/assistant")
async def live_assistant(websocket: WebSocket, db_session: Session = Depends(get_session)) -> None:
    await websocket.accept()

    try:
        live = await get_live(system_instruction=MEMORY_ASSISTANT_SYSTEM_PROMPT, tools=[RECALL_MEMORIES_TOOL])
    except Exception:
        logger.exception("Failed to open Gemini Live session")
        await websocket.send_json({"type": "error", "message": "Couldn't start live mode. Try again shortly."})
        await websocket.close()
        return

    try:
        await asyncio.gather(
            _relay_browser_to_live(websocket, live),
            _relay_live_to_browser(websocket, live, db_session),
        )
    except WebSocketDisconnect:
        pass
    finally:
        await live.close()


async def _relay_browser_to_live(websocket: WebSocket, live) -> None:
    """Browser mic audio -> Gemini. Binary frames are PCM; text frames are control messages."""
    while True:
        message = await websocket.receive()
        if message["type"] == "websocket.disconnect":
            return
        if (data := message.get("bytes")) is not None:
            await live.send_audio(data)
        elif (text := message.get("text")) is not None:
            try:
                control = json.loads(text)
            except ValueError:
                continue
            if control.get("type") == "end":
                return


async def _relay_live_to_browser(websocket: WebSocket, live, db_session: Session) -> None:
    """Gemini events -> browser, executing recall_memories tool calls along the way."""
    embedder = get_embedder()
    async for event in live.receive():
        if isinstance(event, LiveAudioChunk):
            await websocket.send_bytes(event.pcm)
        elif isinstance(event, LiveTranscript):
            await websocket.send_json(
                {"type": "transcript", "speaker": event.speaker, "text": event.text, "final": event.final}
            )
        elif isinstance(event, LiveTurnComplete):
            await websocket.send_json({"type": "turn_complete"})
        elif isinstance(event, LiveToolCall):
            await _handle_tool_call(live, db_session, embedder, event)
        elif isinstance(event, LiveSessionEnded):
            await websocket.send_json({"type": "session_ended", "reason": event.reason})
            return


async def _handle_tool_call(live, db_session: Session, embedder, call: LiveToolCall) -> None:
    if call.name != "recall_memories":
        await live.send_tool_result(call.call_id, {"error": f"Unknown tool {call.name!r}"})
        return
    query = str(call.args.get("query", ""))
    recalled = recall_for_live(db_session, embedder, query)
    await live.send_tool_result(call.call_id, recalled_memories_to_tool_result(recalled))
