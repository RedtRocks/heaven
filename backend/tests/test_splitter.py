"""Tests for split_entry: one event per Memory, robust JSON parsing, participant matching.

No DB, no real LLM: a FakeLLM stands in for app.providers.LLM.
"""

import json
from dataclasses import dataclass

from app.archive.models import Entry
from app.archive.splitter import split_entry
from app.people.models import Person
from app.providers import ChatMessage


@dataclass
class FakeLLM:
    response: str

    def complete(self, messages: list[ChatMessage], system: str | None = None) -> str:
        return self.response


def _entry(text: str) -> Entry:
    return Entry(id=1, text=text)


def test_splits_two_events_from_one_entry_neither_hints_at_the_other():
    # The design's canonical example (docs/agents/task-memory.md section 1).
    payload = {
        "memories": [
            {
                "text": "Argued with Riya at dinner.",
                "happened_on": None,
                "participants": ["Riya"],
                "sensitive_category": None,
                "proposed_visibility": "private",
                "about_person": None,
                "said_to_their_face": None,
            },
            {
                "text": "Texted someone I'm secretly seeing.",
                "happened_on": None,
                "participants": [],
                "sensitive_category": "romance",
                "proposed_visibility": "private",
                "about_person": None,
                "said_to_their_face": None,
            },
        ]
    }
    llm = FakeLLM(json.dumps(payload))
    drafts = split_entry(_entry("Argued with Riya at dinner, then texted X who I'm secretly seeing"), llm, [])

    assert len(drafts) == 2
    assert "text" not in drafts[0].text.lower()  # first Memory never mentions the texting
    assert "riya" not in drafts[1].text.lower()  # second Memory never mentions Riya/dinner
    assert drafts[1].sealed is True
    assert drafts[1].sensitive_category == "romance"
    assert drafts[0].sealed is False


def test_matches_participant_to_known_person_by_alias():
    riya = Person(id=7, name="Riya Sharma", aliases=["didi", "sis"])
    payload = {"memories": [{"text": "Talked to didi about work.", "participants": ["didi"]}]}
    llm = FakeLLM(json.dumps(payload))

    drafts = split_entry(_entry("..."), llm, [riya])

    assert len(drafts) == 1
    [mention] = drafts[0].participants
    assert mention.person_id == 7
    assert mention.is_new is False


def test_new_participant_name_has_no_person_id():
    payload = {"memories": [{"text": "Met a new coworker, Zoya.", "participants": ["Zoya"]}]}
    llm = FakeLLM(json.dumps(payload))

    drafts = split_entry(_entry("..."), llm, [])

    [mention] = drafts[0].participants
    assert mention.person_id is None
    assert mention.name == "Zoya"
    assert mention.is_new is True


def test_unknown_sensitive_category_is_dropped_not_sealed():
    payload = {"memories": [{"text": "Went for a run.", "sensitive_category": "fitness"}]}
    llm = FakeLLM(json.dumps(payload))

    [draft] = split_entry(_entry("..."), llm, [])

    assert draft.sensitive_category is None
    assert draft.sealed is False


def test_invalid_proposed_visibility_falls_back_to_private():
    payload = {"memories": [{"text": "Something happened.", "proposed_visibility": "public"}]}
    llm = FakeLLM(json.dumps(payload))

    [draft] = split_entry(_entry("..."), llm, [])

    assert draft.proposed_visibility == "private"


def test_said_to_their_face_ambiguous_stays_none_not_true():
    payload = {"memories": [{"text": "Rahul is unreliable, ugh.", "about_person": "Rahul", "said_to_their_face": None}]}
    llm = FakeLLM(json.dumps(payload))

    [draft] = split_entry(_entry("..."), llm, [])

    assert draft.said_to_their_face is None
    assert draft.about_person is not None
    assert draft.about_person.name == "Rahul"
    # about_person is folded into participants so it can become a Participant later.
    assert any(p.name == "Rahul" for p in draft.participants)


def test_said_to_their_face_true_when_entry_says_so():
    payload = {"memories": [{"text": "Told Rahul he's unreliable.", "about_person": "Rahul", "said_to_their_face": True}]}
    llm = FakeLLM(json.dumps(payload))

    [draft] = split_entry(_entry("..."), llm, [])

    assert draft.said_to_their_face is True


def test_repairs_json_wrapped_in_markdown_fence():
    payload = {"memories": [{"text": "Fenced response."}]}
    llm = FakeLLM("```json\n" + json.dumps(payload) + "\n```")

    drafts = split_entry(_entry("..."), llm, [])

    assert len(drafts) == 1
    assert drafts[0].text == "Fenced response."


def test_repairs_json_with_leading_and_trailing_prose():
    payload = {"memories": [{"text": "Chatty response."}]}
    llm = FakeLLM("Sure, here you go:\n" + json.dumps(payload) + "\nHope that helps!")

    drafts = split_entry(_entry("..."), llm, [])

    assert len(drafts) == 1
    assert drafts[0].text == "Chatty response."


def test_completely_unparseable_response_yields_no_drafts_not_a_crash():
    llm = FakeLLM("I cannot help with that.")

    drafts = split_entry(_entry("..."), llm, [])

    assert drafts == []


def test_item_missing_text_is_skipped():
    payload = {"memories": [{"participants": ["Riya"]}, {"text": "Valid one."}]}
    llm = FakeLLM(json.dumps(payload))

    drafts = split_entry(_entry("..."), llm, [])

    assert len(drafts) == 1
    assert drafts[0].text == "Valid one."
