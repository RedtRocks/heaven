"""Builds the system prompt that makes the LLM answer as the Owner's Clone."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.conversation.contracts import RecalledMemory
from app.persona.models import Relationship, StyleSample, Trait
from app.persona.traits import usable_by_clone

MAX_STYLE_SAMPLES = 5


def build_clone_system_prompt(session: Session, visitor_id: int | None, recalled: list[RecalledMemory]) -> str:
    """The Clone speaks in the first person as the Owner.

    It uses confirmed Traits, a few Style Samples (for this Visitor if any
    exist, otherwise general ones) for tone, and the Relationship's tone
    notes. It answers life facts only from Traits/Memories given here, may
    reason warmly on generic questions, and never invents events or hints
    that other Memories exist.
    """
    all_traits = list(session.execute(select(Trait)).scalars())
    traits = usable_by_clone(all_traits, visitor_id)

    samples: list[StyleSample] = []
    if visitor_id is not None:
        samples = list(
            session.execute(
                select(StyleSample).where(StyleSample.person_id == visitor_id).limit(MAX_STYLE_SAMPLES)
            ).scalars()
        )
    if not samples:
        samples = list(
            session.execute(
                select(StyleSample).where(StyleSample.person_id.is_(None)).limit(MAX_STYLE_SAMPLES)
            ).scalars()
        )

    tone_notes = ""
    if visitor_id is not None:
        relationship = session.get(Relationship, visitor_id)
        if relationship and relationship.tone_notes.strip():
            tone_notes = relationship.tone_notes.strip()

    lines = [
        "You are the Owner of this memory archive, speaking as yourself in the first "
        "person. You are not an assistant and never describe yourself as an AI, a bot "
        "or a clone.",
    ]

    if traits:
        lines.append("\nThings that are true about you:")
        lines.extend(f"- {t.text}" for t in traits)

    if samples:
        lines.append("\nHow you actually talk (match this voice and tone; don't quote these lines verbatim):")
        lines.extend(f"- {s.text}" for s in samples)

    if tone_notes:
        lines.append(f"\nHow you talk specifically to the person you're talking to right now: {tone_notes}")

    if recalled:
        lines.append("\nMemories you have been given for this conversation (you may use these as facts):")
        lines.extend(f"- ({m.happened_on if m.happened_on else 'undated'}) {m.text}" for m in recalled)
    else:
        lines.append("\nYou have not been given any specific Memories for this conversation.")

    lines.append(
        "\nRules you always follow:\n"
        "- Answer any life fact ONLY using the Traits and Memories listed above. Never "
        "invent an event, date, name or detail that isn't given to you.\n"
        "- For generic questions (advice, opinions, how you'd react to something) you "
        "may reason warmly and in your own voice, without inventing facts about your "
        "own life.\n"
        "- If asked about a life fact you have no Trait or Memory for, say warmly that "
        "you never told them that, or that you don't remember it that way. Never sound "
        "cold, clinical or robotic.\n"
        "- Never hint, imply or admit that other Memories exist beyond what's listed "
        "here."
    )

    return "\n".join(lines)
