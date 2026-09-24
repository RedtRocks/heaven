"""Release Digest: what's about to reach the Clone, sent to the Owner for review.

CONTEXT.md: "The message sent to the Owner before a Holding Period ends. It lists the
Memories about to reach the Clone and the Visibility proposed for each one. If the Owner
doesn't reply, the proposals take effect" (see ADR 0001). Emailing it is a later task;
this module only builds the data and a plain-text rendering.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.archive.models import Memory
from app.config import Settings, get_settings


@dataclass(frozen=True)
class DigestItem:
    memory_id: int
    text: str
    proposed_visibility: str
    release_at: datetime
    sealed: bool


def build_release_digest(session: Session, now: datetime, within_days: int | None = None) -> list[DigestItem]:
    """Memories whose release_at falls within the next `within_days` days (default from
    settings.digest_window_days). Sealed Memories are never released, so they're excluded
    even if their Holding Period has technically elapsed.
    """

    settings: Settings = get_settings()
    window = within_days if within_days is not None else settings.digest_window_days
    horizon = now + timedelta(days=window)

    memories = (
        session.execute(
            select(Memory)
            .where(Memory.sealed.is_(False))
            .where(Memory.release_at >= now)
            .where(Memory.release_at <= horizon)
            .order_by(Memory.release_at)
        )
        .scalars()
        .all()
    )
    return [
        DigestItem(
            memory_id=m.id,
            text=m.text,
            proposed_visibility=m.proposed_visibility,
            release_at=m.release_at,
            sealed=m.sealed,
        )
        for m in memories
    ]


def render_digest_text(items: list[DigestItem]) -> str:
    """A plain-text rendering suitable for the Release Digest email (later task)."""

    if not items:
        return "No Memories are due to release soon."

    lines = ["Memories about to reach your Clone unless you change them:", ""]
    for item in items:
        lines.append(f"- [{item.memory_id}] releases {item.release_at:%Y-%m-%d} as '{item.proposed_visibility}': {item.text}")
    return "\n".join(lines)
