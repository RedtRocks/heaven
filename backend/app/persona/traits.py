"""Turning one Seed Interview answer into stated Traits, via the LLM."""

import json

from pydantic import BaseModel, ValidationError

from app.persona.models import Trait
from app.providers import LLM, ChatMessage

EXTRACT_SYSTEM_PROMPT = """\
You turn one interview answer into standing facts (Traits) about the person \
who answered, called the Owner. Read the question and answer, then return a \
JSON array of Traits implied by the answer. Each Trait is an object:

{"text": "<one standing fact, written about the Owner, e.g. \
'favourite food is biryani'>", "about_person_id": null, "said_to_their_face": false}

Rules:
- Only include facts actually supported by the answer. If the answer gives no \
  clear standing fact, return an empty array.
- Keep each Trait short and self-contained (it will be shown out of context).
- "about_person_id" is almost always null. Leave it null unless you were \
  explicitly told the numeric id of a person the Trait is about.
- "said_to_their_face" is almost always false. Leave it false unless the \
  answer explicitly says the Owner tells this to that person's face.
- Return ONLY the JSON array. No prose, no markdown fences.
"""


class ExtractedTrait(BaseModel):
    text: str
    about_person_id: int | None = None
    said_to_their_face: bool = False


def _parse_json_array(raw: str) -> list:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        first_line, _, rest = raw.partition("\n")
        raw = rest if first_line.strip().lower() in ("json", "") else raw
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("["), raw.rfind("]")
        if start == -1 or end == -1 or end < start:
            return []
        try:
            data = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return []
    if isinstance(data, dict):
        data = data.get("traits", [])
    return data if isinstance(data, list) else []


def extract_traits(question: str, answer: str, llm: LLM) -> list[ExtractedTrait]:
    """Turn one Seed Interview answer into zero or more stated Traits."""
    if not answer.strip():
        return []
    prompt = f"Question: {question}\nAnswer: {answer}\n\nReturn the JSON array of Traits."
    raw = llm.complete([ChatMessage("user", prompt)], system=EXTRACT_SYSTEM_PROMPT)
    traits: list[ExtractedTrait] = []
    for item in _parse_json_array(raw):
        if not isinstance(item, dict):
            continue
        try:
            traits.append(ExtractedTrait.model_validate(item))
        except ValidationError:
            continue
    return traits


def usable_by_clone(traits: list[Trait], visitor_id: int | None) -> list[Trait]:
    """Traits the Clone may use for this Visitor (None means the Owner).

    A Trait is usable only if it is stated or confirmed (an inferred,
    unconfirmed Trait is for the Memory Assistant only). A Trait about a
    person reaches THAT person only if it was said to their face.
    """
    usable = []
    for trait in traits:
        if trait.source != "stated" and not trait.confirmed:
            continue
        if visitor_id is not None and trait.about_person_id == visitor_id and not trait.said_to_their_face:
            continue
        usable.append(trait)
    return usable
