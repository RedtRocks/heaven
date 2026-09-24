"""Turns raw text into stored Entries and Memories: the DB-touching half of the archive.

`splitter.split_entry` stays pure (LLM in, drafts out); this module is what actually
creates People, Entries, Memories and MemoryParticipants, and computes each Memory's
Holding Period end (`release_at`, see ADR 0001 and CONTEXT.md's Holding Period entry).
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.archive.models import Entry, Memory, MemoryParticipant
from app.archive.splitter import MemoryDraft, ParticipantMention, split_entry
from app.config import Settings, get_settings
from app.people.models import Person
from app.providers import LLM, Embedder


def _find_or_create_person(session: Session, mention: ParticipantMention) -> Person:
    if mention.person_id is not None:
        person = session.get(Person, mention.person_id)
        if person is not None:
            return person
    # Re-check by name/alias in case another Entry created this Person since `people`
    # was loaded for the splitter (e.g. two Memories in the same Entry mention them).
    needle = mention.name.strip().lower()
    for person in session.execute(select(Person)).scalars():
        if person.name.strip().lower() == needle or any(a.strip().lower() == needle for a in person.aliases):
            return person
    person = Person(name=mention.name.strip())
    session.add(person)
    session.flush()
    return person


def _resolve_participant_ids(session: Session, mentions: list[ParticipantMention]) -> list[int]:
    ids: list[int] = []
    for mention in mentions:
        person = _find_or_create_person(session, mention)
        if person.id not in ids:
            ids.append(person.id)
    return ids


def store_memory_draft(
    session: Session,
    entry: Entry,
    draft: MemoryDraft,
    embedder: Embedder,
    settings: Settings | None = None,
) -> Memory:
    """Persists one MemoryDraft: resolves/creates its Participants, embeds its text."""

    s = settings or get_settings()
    participant_ids = _resolve_participant_ids(session, draft.participants)

    about_person_id = None
    if draft.about_person is not None:
        about_person_id = _find_or_create_person(session, draft.about_person).id
        if about_person_id not in participant_ids:
            participant_ids.append(about_person_id)

    [embedding] = embedder.embed([draft.text]) or [None]

    created_at = datetime.now(timezone.utc)
    memory = Memory(
        text=draft.text,
        happened_on=draft.happened_on,
        entry_id=entry.id,
        embedding=embedding,
        sealed=draft.sealed,
        sensitive_category=draft.sensitive_category,
        proposed_visibility=draft.proposed_visibility,
        visibility_person_ids=[],
        about_person_id=about_person_id,
        said_to_their_face=draft.said_to_their_face,
        release_at=created_at + timedelta(days=s.holding_period_days),
        created_at=created_at,
    )
    session.add(memory)
    session.flush()

    for person_id in participant_ids:
        session.add(MemoryParticipant(memory_id=memory.id, person_id=person_id))
    session.flush()
    return memory


def create_entry_and_memories(
    session: Session, text: str, llm: LLM, embedder: Embedder, audio_path: str | None = None
) -> tuple[Entry, list[Memory]]:
    """Stores `text` as an Entry, splits it, and persists the resulting Memories."""

    entry = Entry(text=text, audio_path=audio_path)
    session.add(entry)
    session.flush()

    people = list(session.execute(select(Person)).scalars())
    drafts = split_entry(entry, llm, people)

    memories = [store_memory_draft(session, entry, draft, embedder) for draft in drafts]
    session.commit()
    return entry, memories
