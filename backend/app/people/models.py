from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Person(Base):
    """Someone in the Owner's life. May be a Participant in Memories and, with an email, a Visitor."""

    __tablename__ = "person"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    # Other names the Owner uses for them in Entries ("Riya", "didi", "sis")
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list)
    # Set when the Owner invites them as a Visitor
    email: Mapped[str | None] = mapped_column(String(320), unique=True, default=None)
