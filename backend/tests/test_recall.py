"""ArchiveMemoryRecall: vector search that never lets a hidden Memory reach a Visitor.

Uses the real local Postgres+pgvector (test_memory database, see conftest.py). The shared
FakeEmbedder (tests/fakes.py) hashes text to a vector, which is great for "does this embed
at all" but useless for controlling *ranking* by cosine distance. These tests need exact
control over which Memory is closest to the query, so they use a small local embedder
instead - it's a test-only geometry trick, not a second general-purpose fake.
"""

from datetime import datetime, timedelta, timezone

from app.archive.models import Entry, Memory, MemoryParticipant
from app.archive.recall import ArchiveMemoryRecall
from app.people.models import Person

PAST = datetime.now(timezone.utc) - timedelta(days=1)
FUTURE = datetime.now(timezone.utc) + timedelta(days=1)
DIMENSIONS = 768


class _ExactVectorEmbedder:
    """Embedder whose vectors are pre-registered exactly, for controlling cosine ranking."""

    dimensions = DIMENSIONS

    def __init__(self, vectors: dict[str, list[float]]):
        self._vectors = vectors

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vectors[t] for t in texts]


def near_vector(closeness: float) -> list[float]:
    """A vector whose cosine distance from `near_vector(0)` grows with `closeness`."""

    vec = [0.0] * DIMENSIONS
    vec[0] = 1.0
    vec[1] = closeness
    return vec


def _make_memory(session, entry, text, embedding, **kwargs):
    memory = Memory(
        text=text,
        entry_id=entry.id,
        embedding=embedding,
        sealed=kwargs.get("sealed", False),
        proposed_visibility=kwargs.get("proposed_visibility", "private"),
        visibility_person_ids=kwargs.get("visibility_person_ids", []),
        about_person_id=kwargs.get("about_person_id"),
        said_to_their_face=kwargs.get("said_to_their_face"),
        release_at=kwargs.get("release_at", PAST),
    )
    session.add(memory)
    session.flush()
    for person_id in kwargs.get("participant_ids", []):
        session.add(MemoryParticipant(memory_id=memory.id, person_id=person_id))
    session.flush()
    return memory


def test_recall_filters_by_visibility_for_a_visitor_but_not_the_owner(db_session):
    riya = Person(name="Riya")
    rahul = Person(name="Rahul")
    db_session.add_all([riya, rahul])
    db_session.flush()
    entry = Entry(text="a day")
    db_session.add(entry)
    db_session.flush()

    query_text = "what happened"
    embedder = _ExactVectorEmbedder({query_text: near_vector(0.0)})

    sealed = _make_memory(db_session, entry, "sealed secret", near_vector(0.1), sealed=True, proposed_visibility="all_visitors")
    private_to_riya = _make_memory(
        db_session, entry, "private to riya", near_vector(0.2), proposed_visibility="private", participant_ids=[riya.id]
    )
    public = _make_memory(db_session, entry, "public memory", near_vector(0.3), proposed_visibility="all_visitors")
    not_yet_released = _make_memory(
        db_session, entry, "not yet released", near_vector(0.4), proposed_visibility="all_visitors", release_at=FUTURE
    )
    db_session.commit()

    recall = ArchiveMemoryRecall(db_session, embedder)

    owner_ids = {m.id for m in recall.recall(query_text, visitor_id=None, k=10)}
    assert owner_ids == {sealed.id, private_to_riya.id, public.id, not_yet_released.id}

    riya_ids = {m.id for m in recall.recall(query_text, visitor_id=riya.id, k=10)}
    assert riya_ids == {private_to_riya.id, public.id}

    rahul_ids = {m.id for m in recall.recall(query_text, visitor_id=rahul.id, k=10)}
    assert rahul_ids == {public.id}


def test_recall_overfetches_so_hidden_matches_dont_starve_k(db_session):
    riya = Person(name="Riya")
    db_session.add(riya)
    db_session.flush()
    entry = Entry(text="a day")
    db_session.add(entry)
    db_session.flush()

    query_text = "query"
    embedder = _ExactVectorEmbedder({query_text: near_vector(0.0)})

    # The 3 closest matches by embedding are all Sealed; only the 4th is visible to Riya.
    # With k=1 and no over-fetch (limit=k), the visible Memory would never be reached.
    for i in range(3):
        _make_memory(db_session, entry, f"sealed {i}", near_vector(0.01 * (i + 1)), sealed=True, proposed_visibility="all_visitors")
    visible = _make_memory(
        db_session, entry, "visible to riya", near_vector(0.04), proposed_visibility="participants", participant_ids=[riya.id]
    )
    db_session.commit()

    recall = ArchiveMemoryRecall(db_session, embedder)
    results = recall.recall(query_text, visitor_id=riya.id, k=1)

    assert [m.id for m in results] == [visible.id]


def test_said_behind_back_memory_is_never_recalled_for_its_subject(db_session):
    rahul = Person(name="Rahul")
    db_session.add(rahul)
    db_session.flush()
    entry = Entry(text="a day")
    db_session.add(entry)
    db_session.flush()

    query_text = "opinion"
    embedder = _ExactVectorEmbedder({query_text: near_vector(0.0)})
    _make_memory(
        db_session,
        entry,
        "Rahul is unreliable",
        near_vector(0.1),
        proposed_visibility="all_visitors",
        participant_ids=[rahul.id],
        about_person_id=rahul.id,
        said_to_their_face=False,
    )
    db_session.commit()

    recall = ArchiveMemoryRecall(db_session, embedder)
    assert recall.recall(query_text, visitor_id=rahul.id, k=10) == []
    assert len(recall.recall(query_text, visitor_id=None, k=10)) == 1
