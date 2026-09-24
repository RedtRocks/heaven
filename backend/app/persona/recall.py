"""Where the Clone gets its Memories from.

The archive module (built in parallel, in another worktree) will provide the
real MemoryRecall. Until it's wired in, the Clone gets no Memories at all
rather than importing anything from the archive directly.
"""

from app.conversation.contracts import MemoryRecall, RecalledMemory


class _NullMemoryRecall:
    def recall(self, query: str, visitor_id: int | None, k: int = 8) -> list[RecalledMemory]:
        return []


def get_memory_recall() -> MemoryRecall:
    return _NullMemoryRecall()
