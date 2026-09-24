"""HTTP surface for the archive: Entries in, Memories managed, Digest and Assistant out.

See docs/agents/task-memory.md section 4 for the endpoint contracts.
"""

import re
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.archive.digest import build_release_digest, render_digest_text
from app.archive.models import VISIBILITY_KINDS, Memory
from app.archive.recall import ArchiveMemoryRecall
from app.archive.service import create_entry_and_memories
from app.config import REPO_ROOT
from app.db import get_session
from app.providers import LLM, ChatMessage, Embedder, SpeechToText
from app.providers.registry import get_embedder, get_llm, get_stt

router = APIRouter(prefix="", tags=["archive"])

AUDIO_ENTRIES_DIR = REPO_ROOT / "data" / "audio"


# get_llm/get_embedder/get_stt take an optional `settings` argument for tests outside
# FastAPI. Passed straight to Depends(), FastAPI would try to resolve `settings` itself
# (as a request body field, since Settings is a pydantic model). These no-arg wrappers
# are what routes actually depend on (see app/persona/api.py for the same pattern).
def _get_llm() -> LLM:
    return get_llm()


def _get_embedder() -> Embedder:
    return get_embedder()


def _get_stt() -> SpeechToText:
    return get_stt()


class EntryCreate(BaseModel):
    text: str


class MemoryOut(BaseModel):
    id: int
    text: str
    happened_on: date | None
    sealed: bool
    sensitive_category: str | None
    proposed_visibility: str
    visibility_person_ids: list[int]
    about_person_id: int | None
    said_to_their_face: bool | None
    release_at: datetime
    owner_reviewed: bool
    created_at: datetime
    participant_ids: list[int]

    model_config = {"from_attributes": True}


class EntryOut(BaseModel):
    entry_id: int
    memories: list[MemoryOut]


def _memory_out(memory: Memory) -> MemoryOut:
    return MemoryOut(
        id=memory.id,
        text=memory.text,
        happened_on=memory.happened_on,
        sealed=memory.sealed,
        sensitive_category=memory.sensitive_category,
        proposed_visibility=memory.proposed_visibility,
        visibility_person_ids=memory.visibility_person_ids,
        about_person_id=memory.about_person_id,
        said_to_their_face=memory.said_to_their_face,
        release_at=memory.release_at,
        owner_reviewed=memory.owner_reviewed,
        created_at=memory.created_at,
        participant_ids=[p.person_id for p in memory.participants],
    )


@router.post("/entries", response_model=EntryOut)
def create_entry(
    body: EntryCreate,
    session: Session = Depends(get_session),
    llm: LLM = Depends(_get_llm),
    embedder: Embedder = Depends(_get_embedder),
) -> EntryOut:
    entry, memories = create_entry_and_memories(session, body.text, llm, embedder)
    return EntryOut(entry_id=entry.id, memories=[_memory_out(m) for m in memories])


@router.post("/entries/audio", response_model=EntryOut)
def create_entry_from_audio(
    file: UploadFile,
    session: Session = Depends(get_session),
    llm: LLM = Depends(_get_llm),
    embedder: Embedder = Depends(_get_embedder),
    stt: SpeechToText = Depends(_get_stt),
) -> EntryOut:
    audio_bytes = file.file.read()
    text = stt.transcribe(audio_bytes, filename=file.filename or "audio.wav")

    AUDIO_ENTRIES_DIR.mkdir(parents=True, exist_ok=True)
    suffix = f".{file.filename.rsplit('.', 1)[-1]}" if file.filename and "." in file.filename else ".wav"
    audio_path = AUDIO_ENTRIES_DIR / f"{uuid.uuid4()}{suffix}"
    audio_path.write_bytes(audio_bytes)

    entry, memories = create_entry_and_memories(session, text, llm, embedder, audio_path=str(audio_path))
    return EntryOut(entry_id=entry.id, memories=[_memory_out(m) for m in memories])


@router.get("/memories", response_model=list[MemoryOut])
def list_memories(session: Session = Depends(get_session)) -> list[MemoryOut]:
    memories = session.execute(select(Memory).order_by(Memory.created_at.desc())).scalars().all()
    return [_memory_out(m) for m in memories]


class MemoryPatch(BaseModel):
    sealed: bool | None = None
    proposed_visibility: str | None = None
    text: str | None = None
    owner_reviewed: bool | None = None


@router.patch("/memories/{memory_id}", response_model=MemoryOut)
def patch_memory(
    memory_id: int,
    body: MemoryPatch,
    session: Session = Depends(get_session),
    embedder: Embedder = Depends(_get_embedder),
) -> MemoryOut:
    memory = session.get(Memory, memory_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")

    if body.proposed_visibility is not None:
        if body.proposed_visibility not in VISIBILITY_KINDS:
            raise HTTPException(status_code=422, detail=f"proposed_visibility must be one of {VISIBILITY_KINDS}")
        memory.proposed_visibility = body.proposed_visibility
    if body.sealed is not None:
        memory.sealed = body.sealed
    if body.owner_reviewed is not None:
        memory.owner_reviewed = body.owner_reviewed
    if body.text is not None and body.text != memory.text:
        memory.text = body.text
        [embedding] = embedder.embed([body.text]) or [None]
        memory.embedding = embedding

    session.commit()
    session.refresh(memory)
    return _memory_out(memory)


class DigestOut(BaseModel):
    items: list[dict]
    text: str


@router.get("/digest", response_model=DigestOut)
def get_digest(session: Session = Depends(get_session)) -> DigestOut:
    items = build_release_digest(session, datetime.now(timezone.utc))
    return DigestOut(
        items=[
            {
                "memory_id": i.memory_id,
                "text": i.text,
                "proposed_visibility": i.proposed_visibility,
                "release_at": i.release_at,
            }
            for i in items
        ],
        text=render_digest_text(items),
    )


class ChatTurn(BaseModel):
    role: str
    content: str


class AssistantChatRequest(BaseModel):
    message: str
    history: list[ChatTurn] = []


class AssistantChatResponse(BaseModel):
    reply: str
    citations: list[int]


_CITATION_RE = re.compile(r"\[Memory (\d+)\]")


@router.post("/assistant/chat", response_model=AssistantChatResponse)
def assistant_chat(
    body: AssistantChatRequest,
    session: Session = Depends(get_session),
    llm: LLM = Depends(_get_llm),
    embedder: Embedder = Depends(_get_embedder),
) -> AssistantChatResponse:
    """The Memory Assistant: the Owner talking to their own full archive (visitor_id=None)."""

    recall = ArchiveMemoryRecall(session, embedder)
    recalled = recall.recall(body.message, visitor_id=None)

    if not recalled:
        return AssistantChatResponse(
            reply="I don't have a memory of that. You haven't told me anything matching that yet.",
            citations=[],
        )

    memory_lines = "\n".join(f"[Memory {m.id}] ({m.happened_on or 'undated'}) {m.text}" for m in recalled)
    system = (
        "You are the Owner's Memory Assistant: you talk to the Owner about their own life, "
        "addressing them in the second person ('you said...'). Answer only from the Memories "
        "below - never invent facts about the Owner's life. Cite every Memory you rely on "
        "inline as [Memory <id>]. If the Memories below don't answer the question, say so "
        "plainly instead of guessing.\n\nMemories:\n" + memory_lines
    )
    history_messages = [ChatMessage(role="assistant" if t.role == "assistant" else "user", content=t.content) for t in body.history]
    reply = llm.complete([*history_messages, ChatMessage("user", body.message)], system=system)

    recalled_ids = {m.id for m in recalled}
    citations = sorted({int(cid) for cid in _CITATION_RE.findall(reply) if int(cid) in recalled_ids})
    return AssistantChatResponse(reply=reply, citations=citations)
