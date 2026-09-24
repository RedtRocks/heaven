"""Contract between conversation (Clone, Memory Assistant) and the archive.

The archive implements MemoryRecall. Conversation code depends only on this file.
"""

from dataclasses import dataclass
from datetime import date
from typing import Protocol


@dataclass(frozen=True)
class RecalledMemory:
    id: int
    text: str
    happened_on: date | None


class MemoryRecall(Protocol):
    def recall(self, query: str, visitor_id: int | None, k: int = 8) -> list[RecalledMemory]:
        """Memories relevant to query.

        visitor_id=None means the Owner (Memory Assistant, full archive).
        Otherwise only Memories that Visitor may see right now, per the visibility module.
        """
        ...
