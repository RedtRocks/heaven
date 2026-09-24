"""Release Digest: Memories about to release, with their proposed Visibility (CONTEXT.md)."""

from datetime import datetime, timedelta, timezone

from app.archive.digest import build_release_digest, render_digest_text
from app.archive.models import Entry, Memory

NOW = datetime.now(timezone.utc)


def _memory(session, entry, text, release_at, sealed=False, proposed_visibility="private"):
    memory = Memory(text=text, entry_id=entry.id, release_at=release_at, sealed=sealed, proposed_visibility=proposed_visibility)
    session.add(memory)
    session.flush()
    return memory


def test_digest_includes_only_memories_releasing_within_the_window(db_session):
    entry = Entry(text="a day")
    db_session.add(entry)
    db_session.flush()

    soon = _memory(db_session, entry, "releases soon", NOW + timedelta(days=1))
    later = _memory(db_session, entry, "releases later", NOW + timedelta(days=30))
    already_released = _memory(db_session, entry, "already released", NOW - timedelta(days=1))
    db_session.commit()

    items = build_release_digest(db_session, NOW, within_days=3)

    ids = {i.memory_id for i in items}
    assert soon.id in ids
    assert later.id not in ids
    assert already_released.id not in ids


def test_digest_never_includes_sealed_memories_even_if_due(db_session):
    entry = Entry(text="a day")
    db_session.add(entry)
    db_session.flush()
    sealed = _memory(db_session, entry, "sealed", NOW + timedelta(days=1), sealed=True)
    db_session.commit()

    items = build_release_digest(db_session, NOW, within_days=3)

    assert sealed.id not in {i.memory_id for i in items}


def test_digest_carries_the_proposed_visibility():
    from app.archive.digest import DigestItem

    item = DigestItem(memory_id=1, text="t", proposed_visibility="all_visitors", release_at=NOW, sealed=False)
    assert item.proposed_visibility == "all_visitors"


def test_render_digest_text_lists_each_item():
    from app.archive.digest import DigestItem

    items = [DigestItem(memory_id=5, text="Went hiking", proposed_visibility="all_visitors", release_at=NOW, sealed=False)]
    rendered = render_digest_text(items)
    assert "[5]" in rendered
    assert "Went hiking" in rendered
    assert "all_visitors" in rendered


def test_render_digest_text_empty_case():
    assert "No Memories" in render_digest_text([])
