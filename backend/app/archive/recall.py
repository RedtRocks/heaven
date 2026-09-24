"""Implements MemoryRecall (app/conversation/contracts.py) over the archive.

Embeds the query, does a pgvector nearest-neighbour search, then filters through
app.visibility.can_see for the given Visitor BEFORE anything reaches the caller. That
ordering is deliberate (docs/agents/task-memory.md section 2): the Clone must never see,
and so never hint at, a Memory it isn't allowed to have.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.archive.models import Memory
from app.conversation.contracts import RecalledMemory
from app.providers import Embedder
from app.visibility import MemoryVisibility, can_see

# How much wider than k to fetch by vector distance, since visibility filtering may drop
# some candidates and we still want up to k visible results.
OVERFETCH_FACTOR = 5


def _to_visibility(memory: Memory) -> MemoryVisibility:
    return MemoryVisibility(
        sealed=memory.sealed,
        release_at=memory.release_at,
        proposed_visibility=memory.proposed_visibility,
        participant_ids=[p.person_id for p in memory.participants],
        visibility_person_ids=memory.visibility_person_ids,
        about_person_id=memory.about_person_id,
        said_to_their_face=memory.said_to_their_face,
    )


class ArchiveMemoryRecall:
    def __init__(self, session: Session, embedder: Embedder):
        self._session = session
        self._embedder = embedder

    def recall(self, query: str, visitor_id: int | None, k: int = 8) -> list[RecalledMemory]:
        [query_vector] = self._embedder.embed([query]) or [None]
        if query_vector is None:
            return []

        now = datetime.now(timezone.utc)
        candidates = (
            self._session.execute(
                select(Memory)
                .where(Memory.embedding.is_not(None))
                .order_by(Memory.embedding.cosine_distance(query_vector))
                .limit(k * OVERFETCH_FACTOR)
            )
            .scalars()
            .all()
        )

        visible: list[RecalledMemory] = []
        for memory in candidates:
            if can_see(_to_visibility(memory), visitor_id, now):
                visible.append(RecalledMemory(id=memory.id, text=memory.text, happened_on=memory.happened_on))
            if len(visible) >= k:
                break
        return visible
