"""Recall for live mode, with an extra safety net on top of ArchiveMemoryRecall.

ArchiveMemoryRecall.recall(visitor_id=None) is correct for the Owner (they may see every
Memory of their own, Sealed included - that's how the text Memory Assistant already works).
But live mode hands results to a third-party vendor (Gemini), and per ADR 0003 / the live
mode research notes, Sealed Memories must never leave the backend for that. So this module
re-checks `sealed` against the DB and drops those results before they reach the tool result
sent back to Gemini. It's a second gate, not a replacement for visibility rules.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.archive.models import Memory
from app.archive.recall import ArchiveMemoryRecall
from app.conversation.contracts import RecalledMemory
from app.providers import Embedder


def recall_for_live(session: Session, embedder: Embedder, query: str, k: int = 8) -> list[RecalledMemory]:
    """Owner-scoped recall (visitor_id=None) with Sealed Memories filtered out."""
    recall = ArchiveMemoryRecall(session, embedder)
    recalled = recall.recall(query, visitor_id=None, k=k)
    return filter_sealed(session, recalled)


def filter_sealed(session: Session, recalled: list[RecalledMemory]) -> list[RecalledMemory]:
    """Drop any RecalledMemory whose underlying Memory is currently Sealed."""
    if not recalled:
        return []
    ids = [m.id for m in recalled]
    sealed_ids = set(session.execute(select(Memory.id).where(Memory.id.in_(ids), Memory.sealed.is_(True))).scalars().all())
    return [m for m in recalled if m.id not in sealed_ids]


def recalled_memories_to_tool_result(recalled: list[RecalledMemory]) -> dict:
    """What we hand back to Gemini for a recall_memories tool call."""
    return {
        "memories": [
            {"id": m.id, "happened_on": m.happened_on.isoformat() if m.happened_on else None, "text": m.text}
            for m in recalled
        ]
    }


RECALL_MEMORIES_TOOL = {
    "name": "recall_memories",
    "description": (
        "Search the Owner's memory archive for Memories relevant to a query. Use this before "
        "answering any question about the Owner's life, so you never invent facts."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"query": {"type": "STRING", "description": "What to search for."}},
        "required": ["query"],
    },
}

MEMORY_ASSISTANT_SYSTEM_PROMPT = (
    "You are the Owner's Memory Assistant, talking to the Owner about their own life in a live "
    "voice conversation. Address them in the second person ('you said...', 'you told me...'). "
    "Before answering any question about something that happened, or about their opinions, "
    "preferences or people in their life, call the recall_memories tool to find relevant "
    "Memories - never invent facts about the Owner's life. If recall_memories returns nothing "
    "relevant, say plainly that you don't have that memory instead of guessing. Keep replies "
    "conversational and brief, since this is spoken aloud."
)
