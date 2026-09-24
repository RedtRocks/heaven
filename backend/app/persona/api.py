from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.people.models import Person
from app.persona.models import Relationship, SeedAnswer, StyleSample, Trait
from app.persona.prompt import build_clone_system_prompt
from app.persona.recall import get_memory_recall
from app.persona.relationship_questions import RELATIONSHIP_QUESTIONS
from app.persona.seed_questions import SeedQuestion, load_seed_questions
from app.persona.traits import extract_traits
from app.persona.whatsapp import parse_whatsapp_export
from app.providers import LLM, ChatMessage, SpeechToText
from app.providers.registry import get_llm, get_stt

router = APIRouter()


# ---------------------------------------------------------------------------
# Seed Interview
# ---------------------------------------------------------------------------


class SeedQuestionOut(BaseModel):
    question_id: str
    text: str
    category: str


class TraitOut(BaseModel):
    id: int
    text: str
    source: str
    confirmed: bool
    about_person_id: int | None
    said_to_their_face: bool

    model_config = {"from_attributes": True}


class SeedAnswerIn(BaseModel):
    question_id: str
    text: str


class SeedAnswerOut(BaseModel):
    question_id: str
    traits: list[TraitOut]


def _instantiate_questions(session: Session) -> list[tuple[str, SeedQuestion]]:
    """(question_id, question) pairs, expanding per-Relationship questions once
    per known Person, with {name} filled in."""
    questions = load_seed_questions()
    persons = list(session.execute(select(Person)).scalars())
    out: list[tuple[str, SeedQuestion]] = []
    for q in questions:
        if q.per_relationship:
            for p in persons:
                out.append((f"{q.id}:{p.id}", SeedQuestion(q.id, q.text.replace("{name}", p.name), q.category, True)))
        else:
            out.append((q.id, q))
    return out


def _question_for_id(session: Session, question_id: str) -> SeedQuestion:
    for qid, question in _instantiate_questions(session):
        if qid == question_id:
            return question
    raise HTTPException(status_code=404, detail="Unknown seed question")


def _already_answered(session: Session, question_id: str) -> bool:
    return session.execute(select(SeedAnswer).where(SeedAnswer.question_id == question_id)).first() is not None


def _store_extracted_traits(session: Session, question_text: str, answer_text: str, llm: LLM) -> list[Trait]:
    extracted = extract_traits(question_text, answer_text, llm)
    traits: list[Trait] = []
    for item in extracted:
        trait = Trait(
            text=item.text,
            source="stated",
            confirmed=True,
            about_person_id=item.about_person_id,
            said_to_their_face=item.said_to_their_face,
        )
        session.add(trait)
        traits.append(trait)
    session.flush()
    return traits


@router.get("/seed/next", response_model=SeedQuestionOut | None)
def next_seed_question(session: Session = Depends(get_session)) -> SeedQuestionOut | None:
    answered = {a.question_id for a in session.execute(select(SeedAnswer)).scalars()}
    for question_id, question in _instantiate_questions(session):
        if question_id not in answered:
            return SeedQuestionOut(question_id=question_id, text=question.text, category=question.category)
    return None


@router.post("/seed/answer", response_model=SeedAnswerOut)
def answer_seed_question(
    body: SeedAnswerIn,
    session: Session = Depends(get_session),
    llm: LLM = Depends(get_llm),
) -> SeedAnswerOut:
    question = _question_for_id(session, body.question_id)
    if _already_answered(session, body.question_id):
        raise HTTPException(status_code=409, detail="Question already answered")
    session.add(SeedAnswer(question_id=body.question_id, text=body.text))
    traits = _store_extracted_traits(session, question.text, body.text, llm)
    session.commit()
    return SeedAnswerOut(question_id=body.question_id, traits=[TraitOut.model_validate(t) for t in traits])


@router.post("/seed/answer/audio", response_model=SeedAnswerOut)
async def answer_seed_question_audio(
    question_id: str = Form(...),
    audio: UploadFile = File(...),
    session: Session = Depends(get_session),
    llm: LLM = Depends(get_llm),
    stt: SpeechToText = Depends(get_stt),
) -> SeedAnswerOut:
    question = _question_for_id(session, question_id)
    if _already_answered(session, question_id):
        raise HTTPException(status_code=409, detail="Question already answered")
    audio_bytes = await audio.read()
    text = stt.transcribe(audio_bytes, filename=audio.filename or "audio.wav")
    session.add(SeedAnswer(question_id=question_id, text=text))
    traits = _store_extracted_traits(session, question.text, text, llm)
    session.commit()
    return SeedAnswerOut(question_id=question_id, traits=[TraitOut.model_validate(t) for t in traits])


# ---------------------------------------------------------------------------
# Traits
# ---------------------------------------------------------------------------


class TraitIn(BaseModel):
    text: str
    source: Literal["stated", "inferred"] = "inferred"
    confirmed: bool = False
    about_person_id: int | None = None
    said_to_their_face: bool = False


class TraitPatch(BaseModel):
    text: str | None = None
    confirmed: bool | None = None
    said_to_their_face: bool | None = None


@router.get("/traits", response_model=list[TraitOut])
def list_traits(session: Session = Depends(get_session)) -> list[Trait]:
    return list(session.execute(select(Trait).order_by(Trait.id)).scalars())


@router.post("/traits", response_model=TraitOut)
def create_trait(body: TraitIn, session: Session = Depends(get_session)) -> Trait:
    trait = Trait(**body.model_dump())
    session.add(trait)
    session.commit()
    session.refresh(trait)
    return trait


@router.patch("/traits/{trait_id}", response_model=TraitOut)
def patch_trait(trait_id: int, body: TraitPatch, session: Session = Depends(get_session)) -> Trait:
    trait = session.get(Trait, trait_id)
    if trait is None:
        raise HTTPException(status_code=404, detail="Trait not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(trait, field, value)
    session.commit()
    session.refresh(trait)
    return trait


# ---------------------------------------------------------------------------
# Style Samples
# ---------------------------------------------------------------------------


class WhatsAppImportOut(BaseModel):
    imported: int


@router.post("/style-samples/whatsapp", response_model=WhatsAppImportOut)
async def import_whatsapp_style_samples(
    file: UploadFile = File(...),
    owner_name: str = Form(...),
    person_id: int | None = Form(None),
    session: Session = Depends(get_session),
) -> WhatsAppImportOut:
    if person_id is not None and session.get(Person, person_id) is None:
        raise HTTPException(status_code=404, detail="Unknown person")
    raw_bytes = await file.read()
    raw_text = raw_bytes.decode("utf-8", errors="replace")
    messages = parse_whatsapp_export(raw_text, owner_name)
    samples = [StyleSample(text=m, person_id=person_id, source="whatsapp_import") for m in messages]
    session.add_all(samples)
    session.commit()
    return WhatsAppImportOut(imported=len(samples))


# ---------------------------------------------------------------------------
# Relationships
# ---------------------------------------------------------------------------


class RelationshipQuestionnaireOut(BaseModel):
    questions: list[str]


class RelationshipIn(BaseModel):
    tone_notes: str = ""
    questionnaire: dict = {}
    can_see_all_visitors_memories: bool = True


class RelationshipOut(RelationshipIn):
    person_id: int

    model_config = {"from_attributes": True}


@router.get("/relationships/questionnaire", response_model=RelationshipQuestionnaireOut)
def relationship_questionnaire() -> RelationshipQuestionnaireOut:
    return RelationshipQuestionnaireOut(questions=RELATIONSHIP_QUESTIONS)


@router.get("/relationships/{person_id}", response_model=RelationshipOut)
def get_relationship(person_id: int, session: Session = Depends(get_session)) -> Relationship:
    relationship = session.get(Relationship, person_id)
    if relationship is None:
        raise HTTPException(status_code=404, detail="No Relationship set up for this person")
    return relationship


@router.put("/relationships/{person_id}", response_model=RelationshipOut)
def put_relationship(person_id: int, body: RelationshipIn, session: Session = Depends(get_session)) -> Relationship:
    if session.get(Person, person_id) is None:
        raise HTTPException(status_code=404, detail="Unknown person")
    relationship = session.get(Relationship, person_id)
    if relationship is None:
        relationship = Relationship(person_id=person_id)
        session.add(relationship)
    relationship.tone_notes = body.tone_notes
    relationship.questionnaire = body.questionnaire
    relationship.can_see_all_visitors_memories = body.can_see_all_visitors_memories
    session.commit()
    session.refresh(relationship)
    return relationship


# ---------------------------------------------------------------------------
# Clone chat
# ---------------------------------------------------------------------------


class ClonChatMessageIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class CloneChatIn(BaseModel):
    message: str
    history: list[ClonChatMessageIn] = []
    visitor_id: int | None = None


class CitationOut(BaseModel):
    memory_id: int
    text: str


class CloneChatOut(BaseModel):
    reply: str
    citations: list[CitationOut]


@router.post("/clone/chat", response_model=CloneChatOut)
def clone_chat(
    body: CloneChatIn,
    session: Session = Depends(get_session),
    llm: LLM = Depends(get_llm),
) -> CloneChatOut:
    recall = get_memory_recall()
    recalled = recall.recall(body.message, body.visitor_id)
    system = build_clone_system_prompt(session, body.visitor_id, recalled)
    messages = [ChatMessage(m.role, m.content) for m in body.history]
    messages.append(ChatMessage("user", body.message))
    reply = llm.complete(messages, system=system)
    citations = [CitationOut(memory_id=m.id, text=m.text) for m in recalled]
    return CloneChatOut(reply=reply, citations=citations)
