from datetime import date

from app.conversation.contracts import RecalledMemory
from app.people.models import Person
from app.persona.models import Relationship, StyleSample, Trait
from app.persona.prompt import build_clone_system_prompt


def test_prompt_includes_stated_and_confirmed_traits_but_not_unconfirmed_inferred(db_session):
    db_session.add_all(
        [
            Trait(text="favourite food is biryani", source="stated", confirmed=False),
            Trait(text="secretly wants to move abroad", source="inferred", confirmed=True),
            Trait(text="unverified guess about them", source="inferred", confirmed=False),
        ]
    )
    db_session.commit()

    prompt = build_clone_system_prompt(db_session, visitor_id=None, recalled=[])

    assert "favourite food is biryani" in prompt
    assert "secretly wants to move abroad" in prompt
    assert "unverified guess about them" not in prompt


def test_prompt_hides_trait_about_visitor_unless_said_to_their_face(db_session):
    person = Person(name="Riya")
    db_session.add(person)
    db_session.flush()

    db_session.add_all(
        [
            Trait(
                text="finds Riya exhausting sometimes",
                source="stated",
                about_person_id=person.id,
                said_to_their_face=False,
            ),
            Trait(
                text="thinks Riya is hilarious",
                source="stated",
                about_person_id=person.id,
                said_to_their_face=True,
            ),
        ]
    )
    db_session.commit()

    prompt = build_clone_system_prompt(db_session, visitor_id=person.id, recalled=[])

    assert "finds Riya exhausting sometimes" not in prompt
    assert "thinks Riya is hilarious" in prompt


def test_prompt_uses_visitor_specific_style_samples_when_available(db_session):
    person = Person(name="Riya")
    db_session.add(person)
    db_session.flush()

    db_session.add_all(
        [
            StyleSample(text="yaar seriously though", person_id=person.id, source="whatsapp_import"),
            StyleSample(text="general chat energy", person_id=None, source="whatsapp_import"),
        ]
    )
    db_session.commit()

    prompt = build_clone_system_prompt(db_session, visitor_id=person.id, recalled=[])

    assert "yaar seriously though" in prompt
    assert "general chat energy" not in prompt


def test_prompt_falls_back_to_general_style_samples_when_none_for_visitor(db_session):
    person = Person(name="Riya")
    db_session.add(person)
    db_session.flush()
    db_session.add(StyleSample(text="general chat energy", person_id=None, source="whatsapp_import"))
    db_session.commit()

    prompt = build_clone_system_prompt(db_session, visitor_id=person.id, recalled=[])

    assert "general chat energy" in prompt


def test_prompt_includes_relationship_tone_notes(db_session):
    person = Person(name="Riya")
    db_session.add(person)
    db_session.flush()
    db_session.add(Relationship(person_id=person.id, tone_notes="playful, lots of teasing"))
    db_session.commit()

    prompt = build_clone_system_prompt(db_session, visitor_id=person.id, recalled=[])

    assert "playful, lots of teasing" in prompt


def test_prompt_includes_recalled_memories_as_facts(db_session):
    recalled = [RecalledMemory(id=1, text="ran a half marathon last spring", happened_on=date(2024, 4, 1))]
    prompt = build_clone_system_prompt(db_session, visitor_id=None, recalled=recalled)
    assert "ran a half marathon last spring" in prompt


def test_prompt_never_invents_events_rule_and_never_hints_more_memories_rule_are_present(db_session):
    prompt = build_clone_system_prompt(db_session, visitor_id=None, recalled=[])
    assert "never" in prompt.lower()
    assert "invent" in prompt.lower()
    assert "hint" in prompt.lower()
