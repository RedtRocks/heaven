"""Splits one Entry into one-event-only Memory drafts (CONTEXT.md: Memory, Sealed).

`split_entry` is the only place that talks to the LLM for this. It never touches the DB:
it returns `MemoryDraft`s naming Participants by their matched Person id (if the Owner
already knows them) or by raw name (if they're new). The archive API layer is what
actually creates new People and Memory rows, using `resolve_participants` below to turn
names into ids.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import date

from app.archive.models import SENSITIVE_CATEGORIES
from app.people.models import Person
from app.providers import ChatMessage, LLM

VISIBILITY_CHOICES = ("private", "participants", "all_visitors")

_SYSTEM_PROMPT = """You split a personal diary Entry into Memories. A Memory covers exactly \
one event, fact, opinion or story. Never let a Memory hint at what happened before or after \
it in the same Entry: if the Entry describes two events, they become two separate Memories \
and neither may reference the other.

Known people the Owner has mentioned before: {known_people}

For each Memory, decide:
- text: the Memory in the Owner's own words, one event only.
- happened_on: an ISO date "YYYY-MM-DD" if the Entry says or implies one, else null.
- participants: names of people involved in or the subject of this Memory. Match an \
existing known person's name or alias when it's clearly the same person; otherwise use \
the new name as written.
- sensitive_category: one of "health", "money", "romance", "others_secret", or null. Use \
one of these whenever the Memory is about the Owner's health, finances, a romantic or \
sexual matter, or a secret belonging to someone else.
- proposed_visibility: one of "private", "participants", "all_visitors" - your best guess \
at who, besides the Owner, this Memory could eventually reach.
- about_person: if this Memory is the Owner's opinion ABOUT one of the participants \
(good or bad), that person's name, else null.
- said_to_their_face: true only if the Entry explicitly says the Owner told that person \
this to their face or said it directly to them. false if the Owner clearly said it behind \
their back or online. null if the Entry doesn't say either way. When in doubt, use false \
or null, never true.

Respond with ONLY a JSON object of the shape:
{{"memories": [{{"text": "...", "happened_on": "YYYY-MM-DD" | null, "participants": ["..."], \
"sensitive_category": "..." | null, "proposed_visibility": "...", "about_person": "..." | null, \
"said_to_their_face": true | false | null}}]}}
No prose, no markdown fences."""


@dataclass(frozen=True)
class ParticipantMention:
    """A person named in a Memory draft: matched to an existing Person, or new."""

    name: str
    person_id: int | None = None

    @property
    def is_new(self) -> bool:
        return self.person_id is None


@dataclass(frozen=True)
class MemoryDraft:
    text: str
    happened_on: date | None
    participants: list[ParticipantMention] = field(default_factory=list)
    sensitive_category: str | None = None
    sealed: bool = False
    proposed_visibility: str = "private"
    about_person: ParticipantMention | None = None
    said_to_their_face: bool | None = None


def _match_person(name: str, people: list[Person]) -> Person | None:
    needle = name.strip().lower()
    if not needle:
        return None
    for person in people:
        if person.name.strip().lower() == needle:
            return person
        if any(alias.strip().lower() == needle for alias in person.aliases):
            return person
    return None


def _mention(name: str, people: list[Person]) -> ParticipantMention:
    match = _match_person(name, people)
    return ParticipantMention(name=match.name if match else name.strip(), person_id=match.id if match else None)


def _parse_json_object(raw: str) -> dict:
    """Robustly parse the LLM's JSON, repairing common formatting mistakes."""

    text = raw.strip()
    # Strip ```json ... ``` or ``` ... ``` fences.
    fence_match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    for candidate in (text, _extract_braces(text)):
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            return {"memories": parsed}
    return {"memories": []}


def _extract_braces(text: str) -> str | None:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1]


def _build_draft(item: dict, people: list[Person]) -> MemoryDraft | None:
    if not isinstance(item, dict):
        return None
    text = str(item.get("text") or "").strip()
    if not text:
        return None

    happened_on = None
    raw_date = item.get("happened_on")
    if isinstance(raw_date, str):
        try:
            happened_on = date.fromisoformat(raw_date)
        except ValueError:
            happened_on = None

    raw_participants = item.get("participants")
    names = [str(n).strip() for n in raw_participants if str(n).strip()] if isinstance(raw_participants, list) else []
    participants = [_mention(name, people) for name in names]

    sensitive_category = item.get("sensitive_category")
    if sensitive_category not in SENSITIVE_CATEGORIES:
        sensitive_category = None

    proposed_visibility = item.get("proposed_visibility")
    if proposed_visibility not in VISIBILITY_CHOICES:
        proposed_visibility = "private"

    about_person = None
    raw_about = item.get("about_person")
    if isinstance(raw_about, str) and raw_about.strip():
        existing = next((p for p in participants if p.name.lower() == raw_about.strip().lower()), None)
        about_person = existing or _mention(raw_about, people)
        if about_person not in participants:
            participants.append(about_person)

    said_to_their_face = item.get("said_to_their_face")
    if not isinstance(said_to_their_face, bool):
        said_to_their_face = None

    return MemoryDraft(
        text=text,
        happened_on=happened_on,
        participants=participants,
        sensitive_category=sensitive_category,
        sealed=sensitive_category is not None,
        proposed_visibility=proposed_visibility,
        about_person=about_person,
        said_to_their_face=said_to_their_face,
    )


def split_entry(entry, llm: LLM, people: list[Person]) -> list["MemoryDraft"]:
    """Splits `entry.text` into one-event Memory drafts using `llm`.

    `people` is the Owner's known People, used to match Participants by name/alias.
    """

    known_people = ", ".join(sorted({p.name for p in people})) or "(none yet)"
    system = _SYSTEM_PROMPT.format(known_people=known_people)
    raw = llm.complete([ChatMessage("user", entry.text)], system=system)
    data = _parse_json_object(raw)

    items = data.get("memories") if isinstance(data, dict) else None
    if not isinstance(items, list):
        items = []

    drafts = []
    for item in items:
        draft = _build_draft(item, people)
        if draft is not None:
            drafts.append(draft)
    return drafts
