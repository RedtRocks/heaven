"""The Owner's cloned voice, spoken over HTTP."""

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from app.providers import VoiceSynth
from app.providers.registry import get_voice

router = APIRouter()


# get_voice takes an optional `settings` argument for tests outside FastAPI. Passed
# straight to Depends(), FastAPI would try to resolve `settings` itself (as a request
# body field, since Settings is a pydantic model). This no-arg wrapper is what the
# route actually depends on (see app/persona/api.py for the same pattern).
def _get_voice() -> VoiceSynth:
    return get_voice()


class SpeakIn(BaseModel):
    text: str


@router.post("/voice/speak")
def speak(body: SpeakIn, voice: VoiceSynth = Depends(_get_voice)) -> Response:
    wav_bytes = voice.speak(body.text)
    return Response(content=wav_bytes, media_type="audio/wav")
