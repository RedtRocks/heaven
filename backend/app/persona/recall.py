"""Where the Clone gets its Memories from.

Backed by the archive module's ArchiveMemoryRecall: embeds the query, does a pgvector
search, then filters through app.visibility.can_see for the given Visitor before
anything reaches the Clone's prompt (see docs/agents/task-memory.md section 3).
"""

from sqlalchemy.orm import Session

from app.archive.recall import ArchiveMemoryRecall
from app.conversation.contracts import MemoryRecall
from app.providers.registry import get_embedder


def get_memory_recall(session: Session) -> MemoryRecall:
    return ArchiveMemoryRecall(session, get_embedder())
