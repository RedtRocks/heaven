from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Trait(Base):
    """A standing fact about the Owner (preference, habit, opinion).

    The Clone uses a Trait only if it is stated or confirmed. An inferred,
    unconfirmed Trait is used only by the Memory Assistant. A Trait about a
    person reaches THAT person only if said_to_their_face.
    """

    __tablename__ = "persona_trait"

    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20))  # "stated" | "inferred"
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    about_person_id: Mapped[int | None] = mapped_column(ForeignKey("person.id"), nullable=True, default=None)
    said_to_their_face: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StyleSample(Base):
    """Something the Owner actually said/wrote, kept only to learn how they talk.

    Never a Memory, never quoted as fact. Other people's words are never stored.
    """

    __tablename__ = "persona_style_sample"

    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    # Who the Owner was talking to. Null means general / unknown audience.
    person_id: Mapped[int | None] = mapped_column(ForeignKey("person.id"), nullable=True, default=None)
    source: Mapped[str] = mapped_column(String(50), default="whatsapp_import")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Relationship(Base):
    """The Owner's setup for one Visitor: how the Clone should behave toward them."""

    __tablename__ = "persona_relationship"

    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), primary_key=True)
    tone_notes: Mapped[str] = mapped_column(Text, default="")
    questionnaire: Mapped[dict] = mapped_column(JSON, default=dict)
    can_see_all_visitors_memories: Mapped[bool] = mapped_column(Boolean, default=True)


class SeedAnswer(Base):
    """One answer the Owner gave during the Seed Interview.

    question_id may be a plain question bank id ("q001") or, for a
    per-Relationship question, "q001:<person_id>".
    """

    __tablename__ = "persona_seed_answer"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[str] = mapped_column(String(100), unique=True)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
