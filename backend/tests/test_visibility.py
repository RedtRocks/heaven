"""Table-driven tests for the one function that decides Memory visibility.

Every row is (description, MemoryVisibility, visitor_id, now, expected_can_see, expected_rule).
Covers the precedence order from docs/agents/task-memory.md section 2, plus the design
cases called out there explicitly (the secret-texting Memory, the "said behind his back"
Memory, the "I told him" Memory, and the participant-less Private Memory).
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.visibility import MemoryVisibility, can_see, can_see_why

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
PAST = NOW - timedelta(days=1)
FUTURE = NOW + timedelta(days=1)

RIYA = 1
RAHUL = 2
STRANGER = 3


def mv(
    sealed=False,
    release_at=PAST,
    proposed_visibility="private",
    participant_ids=(),
    visibility_person_ids=(),
    about_person_id=None,
    said_to_their_face=None,
):
    return MemoryVisibility(
        sealed=sealed,
        release_at=release_at,
        proposed_visibility=proposed_visibility,
        participant_ids=list(participant_ids),
        visibility_person_ids=list(visibility_person_ids),
        about_person_id=about_person_id,
        said_to_their_face=said_to_their_face,
    )


CASES = [
    # -- Owner sees everything, no matter what.
    ("owner sees sealed", mv(sealed=True), None, NOW, True, "owner"),
    ("owner sees not-yet-released", mv(release_at=FUTURE), None, NOW, True, "owner"),
    ("owner sees said-behind-back about them", mv(about_person_id=RAHUL, said_to_their_face=False), None, NOW, True, "owner"),
    # -- Sealed beats everything else, including being a Participant.
    ("sealed blocks participant", mv(sealed=True, proposed_visibility="participants", participant_ids=[RIYA]), RIYA, NOW, False, "sealed"),
    ("sealed blocks all_visitors", mv(sealed=True, proposed_visibility="all_visitors"), STRANGER, NOW, False, "sealed"),
    ("sealed blocks explicit list", mv(sealed=True, proposed_visibility="explicit", visibility_person_ids=[RIYA]), RIYA, NOW, False, "sealed"),
    # -- Holding Period: not released yet, even for a Participant / all_visitors.
    ("holding period blocks participant", mv(release_at=FUTURE, proposed_visibility="participants", participant_ids=[RIYA]), RIYA, NOW, False, "holding_period"),
    ("holding period blocks all_visitors", mv(release_at=FUTURE, proposed_visibility="all_visitors"), STRANGER, NOW, False, "holding_period"),
    ("holding period passes right at release_at", mv(release_at=NOW, proposed_visibility="all_visitors"), STRANGER, NOW, True, "all_visitors"),
    # -- Said-behind-their-back only blocks the subject, not others.
    ("said behind back blocks the subject", mv(proposed_visibility="all_visitors", about_person_id=RAHUL, said_to_their_face=False), RAHUL, NOW, False, "said_behind_back"),
    ("said behind back allows others", mv(proposed_visibility="all_visitors", about_person_id=RAHUL, said_to_their_face=False), STRANGER, NOW, True, "all_visitors"),
    ("said to their face allows the subject", mv(proposed_visibility="all_visitors", about_person_id=RAHUL, said_to_their_face=True), RAHUL, NOW, True, "all_visitors"),
    ("ambiguous (None) said-to-their-face counts as False", mv(proposed_visibility="all_visitors", about_person_id=RAHUL, said_to_their_face=None), RAHUL, NOW, False, "said_behind_back"),
    (
        "said behind back still requires participant/visibility check for the subject",
        mv(proposed_visibility="private", participant_ids=[RAHUL], about_person_id=RAHUL, said_to_their_face=True),
        RAHUL,
        NOW,
        True,
        "private_participant",
    ),
    # -- private: Participants only.
    ("private allows participant", mv(proposed_visibility="private", participant_ids=[RIYA]), RIYA, NOW, True, "private_participant"),
    ("private blocks non-participant", mv(proposed_visibility="private", participant_ids=[RIYA]), STRANGER, NOW, False, "private_not_participant"),
    ("private with no participants blocks everyone", mv(proposed_visibility="private", participant_ids=[]), RIYA, NOW, False, "private_not_participant"),
    # -- participants: same as private in effect, but a distinct rule/intent.
    ("participants allows participant", mv(proposed_visibility="participants", participant_ids=[RIYA]), RIYA, NOW, True, "participants_only"),
    ("participants blocks non-participant", mv(proposed_visibility="participants", participant_ids=[RIYA]), STRANGER, NOW, False, "participants_only_excluded"),
    # -- all_visitors: anyone once released.
    ("all_visitors allows anyone", mv(proposed_visibility="all_visitors"), STRANGER, NOW, True, "all_visitors"),
    # -- explicit list.
    ("explicit list allows listed id", mv(proposed_visibility="explicit", visibility_person_ids=[RIYA]), RIYA, NOW, True, "explicit_list"),
    ("explicit list blocks unlisted id", mv(proposed_visibility="explicit", visibility_person_ids=[RIYA]), RAHUL, NOW, False, "explicit_list_excluded"),
    # -- unknown value fails closed rather than leaking.
    ("unknown proposed_visibility fails closed", mv(proposed_visibility="bogus"), RIYA, NOW, False, "unknown_visibility"),
]


@pytest.mark.parametrize("desc,memory,visitor_id,now,expected,rule", CASES, ids=[c[0] for c in CASES])
def test_can_see_table(desc, memory, visitor_id, now, expected, rule):
    assert can_see(memory, visitor_id, now) is expected
    assert can_see_why(memory, visitor_id, now) == (expected, rule)


def test_design_case_secret_texting_memory_is_sealed_riya_cant_see_it():
    # "Argued with Riya at dinner, then texted X who I'm secretly seeing" -> the second
    # Memory (secretly seeing X) is Sealed (romance). Riya being a Participant in some
    # OTHER Memory doesn't matter here; this Memory just needs to be unseeable by anyone.
    secret_memory = mv(sealed=True, proposed_visibility="all_visitors")
    assert can_see(secret_memory, RIYA, NOW) is False


def test_design_case_said_behind_his_back_rahul_cant_see_but_others_can():
    memory = mv(proposed_visibility="all_visitors", participant_ids=[RAHUL], about_person_id=RAHUL, said_to_their_face=False)
    assert can_see(memory, RAHUL, NOW) is False
    assert can_see(memory, STRANGER, NOW) is True


def test_design_case_i_told_rahul_he_can_see_it():
    memory = mv(proposed_visibility="participants", participant_ids=[RAHUL], about_person_id=RAHUL, said_to_their_face=True)
    assert can_see(memory, RAHUL, NOW) is True


def test_design_case_private_with_no_participants_nobody_sees_it():
    memory = mv(proposed_visibility="private", participant_ids=[])
    for visitor in (RIYA, RAHUL, STRANGER):
        assert can_see(memory, visitor, NOW) is False
