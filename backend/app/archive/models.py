"""Entries and Memories: the raw record the Owner gives, and the events split out of it.

See CONTEXT.md for Entry, Memory, Sealed, Participant, Visibility, Holding Period.
"""

from datetime import date, datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import get_settings
from app.db import Base

# Categories that auto-Seal a Memory (ADR 0001, CONTEXT.md's Sealed entry).
SENSITIVE_CATEGORIES = ("health", "money", "romance", "others_secret")

# The non-explicit shapes `proposed_visibility` can take. An "explicit" list of Person ids
# is stored separately in `visibility_person_ids` (see app/visibility/rules.py).
VISIBILITY_KINDS = ("private", "participants", "all_visitors", "explicit")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Entry(Base):
    """Raw input the Owner gives. A voice Entry is stored as its transcript plus audio_path."""

    __tablename__ = "entry"

    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    # Set only for Entries captured via POST /entries/audio.
    audio_path: Mapped[str | None] = mapped_column(String(1000), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    memories: Mapped[list["Memory"]] = relationship(back_populates="entry")


class Memory(Base):
    """A single event, fact, opinion or story taken from one Entry. The unit that's
    searched, filtered by app/visibility, and cited by the Clone and Memory Assistant.
    """

    __tablename__ = "memory"

    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    happened_on: Mapped[date | None] = mapped_column(Date, default=None)
    entry_id: Mapped[int] = mapped_column(ForeignKey("entry.id"))

    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(get_settings().embedding_dimensions), default=None
    )

    sealed: Mapped[bool] = mapped_column(Boolean, default=False)
    # One of SENSITIVE_CATEGORIES, or None. Any value here forces sealed=True.
    sensitive_category: Mapped[str | None] = mapped_column(String(50), default=None)

    # One of VISIBILITY_KINDS. When "explicit", visibility_person_ids names who.
    proposed_visibility: Mapped[str] = mapped_column(String(20), default="private")
    visibility_person_ids: Mapped[list[int]] = mapped_column(JSON, default=list)

    # Set when this Memory holds the Owner's opinion about a Participant.
    about_person_id: Mapped[int | None] = mapped_column(ForeignKey("person.id"), default=None)
    # True ONLY when the Entry explicitly says the Owner told them. Ambiguous means False.
    said_to_their_face: Mapped[bool | None] = mapped_column(Boolean, default=None)

    release_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    owner_reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    entry: Mapped["Entry"] = relationship(back_populates="memories")
    participants: Mapped[list["MemoryParticipant"]] = relationship(
        back_populates="memory", cascade="all, delete-orphan"
    )


class MemoryParticipant(Base):
    """A Person who took part in, or is the subject of, a Memory (CONTEXT.md: Participant)."""

    __tablename__ = "memory_participant"

    id: Mapped[int] = mapped_column(primary_key=True)
    memory_id: Mapped[int] = mapped_column(ForeignKey("memory.id"))
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"))

    memory: Mapped["Memory"] = relationship(back_populates="participants")
