"""create_entry_and_memories: the DB-touching glue between an Entry and its Memories."""

import json
from datetime import timedelta

from sqlalchemy import select

from app.archive.models import Entry, Memory, MemoryParticipant
from app.archive.service import create_entry_and_memories
from app.config import get_settings
from app.people.models import Person

from .fakes import FakeEmbedder, FakeLLM


def memories_payload(*memories: dict) -> str:
    return json.dumps({"memories": list(memories)})


def test_creates_entry_and_memories_with_new_person_and_embedding(db_session):
    llm = FakeLLM(reply=memories_payload({"text": "Met Zoya for coffee.", "participants": ["Zoya"]}))
    embedder = FakeEmbedder()

    entry, memories = create_entry_and_memories(db_session, "Met Zoya for coffee.", llm, embedder)

    assert entry.text == "Met Zoya for coffee."
    [memory] = memories
    assert memory.text == "Met Zoya for coffee."
    assert memory.embedding is not None
    assert len(memory.embedding) == embedder.dimensions

    zoya = db_session.execute(select(Person).where(Person.name == "Zoya")).scalar_one()
    participant = db_session.execute(select(MemoryParticipant).where(MemoryParticipant.memory_id == memory.id)).scalar_one()
    assert participant.person_id == zoya.id


def test_reuses_existing_person_instead_of_creating_a_duplicate(db_session):
    riya = Person(name="Riya Sharma", aliases=["didi"])
    db_session.add(riya)
    db_session.flush()

    llm = FakeLLM(reply=memories_payload({"text": "Talked to didi.", "participants": ["didi"]}))
    embedder = FakeEmbedder()

    entry, memories = create_entry_and_memories(db_session, "Talked to didi.", llm, embedder)

    people = db_session.execute(select(Person)).scalars().all()
    assert len(people) == 1  # no duplicate created
    [memory] = memories
    [participant] = memory.participants
    assert participant.person_id == riya.id


def test_release_at_is_created_at_plus_holding_period(db_session):
    llm = FakeLLM(reply=memories_payload({"text": "A quiet day."}))
    embedder = FakeEmbedder()

    entry, memories = create_entry_and_memories(db_session, "A quiet day.", llm, embedder)

    [memory] = memories
    expected = memory.created_at + timedelta(days=get_settings().holding_period_days)
    assert memory.release_at == expected


def test_sensitive_category_auto_seals(db_session):
    llm = FakeLLM(reply=memories_payload({"text": "Doctor visit.", "sensitive_category": "health"}))
    embedder = FakeEmbedder()

    _, memories = create_entry_and_memories(db_session, "Doctor visit.", llm, embedder)

    [memory] = memories
    assert memory.sealed is True
    assert memory.sensitive_category == "health"


def test_one_entry_can_produce_multiple_memories_each_stored_separately(db_session):
    llm = FakeLLM(
        reply=memories_payload(
            {"text": "Argued with Riya at dinner.", "participants": ["Riya"]},
            {"text": "Texted someone I'm secretly seeing.", "sensitive_category": "romance"},
        )
    )
    embedder = FakeEmbedder()

    entry, memories = create_entry_and_memories(db_session, "long diary entry", llm, embedder)

    assert len(memories) == 2
    stored = db_session.execute(select(Memory).where(Memory.entry_id == entry.id)).scalars().all()
    assert len(stored) == 2
    sealed_ones = [m for m in stored if m.sealed]
    assert len(sealed_ones) == 1
    assert "secretly seeing" in sealed_ones[0].text


def test_about_person_becomes_a_participant_even_if_not_named_in_participants(db_session):
    llm = FakeLLM(
        reply=memories_payload(
            {
                "text": "Rahul is unreliable, ugh.",
                "participants": [],
                "about_person": "Rahul",
                "said_to_their_face": False,
            }
        )
    )
    embedder = FakeEmbedder()

    _, memories = create_entry_and_memories(db_session, "Rahul is unreliable, ugh.", llm, embedder)

    [memory] = memories
    rahul = db_session.execute(select(Person).where(Person.name == "Rahul")).scalar_one()
    assert memory.about_person_id == rahul.id
    assert memory.said_to_their_face is False
    participant_ids = [p.person_id for p in memory.participants]
    assert rahul.id in participant_ids
