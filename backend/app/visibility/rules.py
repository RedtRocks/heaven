"""The one function that decides whether a Visitor can see a Memory right now.

Pure and dependency-free on purpose: no DB session, no provider calls. The archive module
builds a `MemoryVisibility` from its ORM rows and calls in here. Keeping this pure is what
makes it possible to write exhaustive, table-driven tests for the precedence rules (see
CONTEXT.md's Visibility/Sealed/Participant entries and docs/v1-plan.md's visibility module
note: "Sealed wins -> Holding Period -> Participant or proposed Visibility -> Private by
default").
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class MemoryVisibility:
    """Everything `can_see` needs to know about one Memory. Owner-agnostic, DB-agnostic."""

    sealed: bool
    release_at: datetime
    # "private" | "participants" | "all_visitors" | "explicit"
    proposed_visibility: str
    participant_ids: list[int] = field(default_factory=list)
    # Only meaningful when proposed_visibility == "explicit".
    visibility_person_ids: list[int] = field(default_factory=list)
    # Set when this Memory records the Owner's opinion about a Participant.
    about_person_id: int | None = None
    # True only when the Entry explicitly says the Owner told them; ambiguous means False.
    said_to_their_face: bool | None = None


def can_see(memory: MemoryVisibility, visitor_id: int | None, now: datetime) -> bool:
    return can_see_why(memory, visitor_id, now)[0]


def can_see_why(memory: MemoryVisibility, visitor_id: int | None, now: datetime) -> tuple[bool, str]:
    """Returns (can_see, rule) where `rule` names which precedence step decided it."""

    # 1. Owner sees everything.
    if visitor_id is None:
        return True, "owner"

    # 2. Sealed overrides every other rule, including Participant access.
    if memory.sealed:
        return False, "sealed"

    # 3. Holding Period: not released yet.
    if now < memory.release_at:
        return False, "holding_period"

    # 4. Said-behind-their-back: this Visitor is the subject of an opinion the Owner
    #    didn't say to their face. Blocks only that Visitor, not everyone else.
    if memory.about_person_id is not None and visitor_id == memory.about_person_id:
        if not memory.said_to_their_face:
            return False, "said_behind_back"

    # 5. proposed_visibility.
    is_participant = visitor_id in memory.participant_ids

    if memory.proposed_visibility == "private":
        return (True, "private_participant") if is_participant else (False, "private_not_participant")

    if memory.proposed_visibility == "participants":
        return (True, "participants_only") if is_participant else (False, "participants_only_excluded")

    if memory.proposed_visibility == "all_visitors":
        return True, "all_visitors"

    if memory.proposed_visibility == "explicit":
        return (True, "explicit_list") if visitor_id in memory.visibility_person_ids else (False, "explicit_list_excluded")

    # Unknown value: fail closed rather than leak.
    return False, "unknown_visibility"
