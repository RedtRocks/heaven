# Report: feat/memory (Phase 5 core)

## What was built

**`app/visibility/` (the most heavily tested module)**
- `MemoryVisibility` (pure dataclass) and `can_see` / `can_see_why(memory, visitor_id, now) -> (bool, rule)`.
- Precedence implemented exactly as specified: Owner sees everything -> Sealed (never, overrides Participant access) -> Holding Period -> said-behind-their-back (blocks only the subject Visitor) -> proposed_visibility (`private`/`participants`/`all_visitors`/`explicit`).
- 27 table-driven cases in `tests/test_visibility.py`, plus the four literal design cases from the brief (secret-texting Memory Sealed even though Riya is a Participant; "Rahul is unreliable, ugh" blocks Rahul but not others; "I told Rahul he's unreliable" lets Rahul see it; a Private Memory with no Participants is unseeable by anyone but the Owner).
- Deliberately pure and DB-free so the precedence logic can be tested exhaustively without Postgres.

**`app/archive/` (models + logic)**
- `models.py`: `Entry` (text, optional `audio_path`, `created_at`), `Memory` (text, `happened_on`, `entry_id`, pgvector `embedding`, `sealed`, `sensitive_category`, `proposed_visibility` + `visibility_person_ids` for the explicit-list case, `about_person_id`/`said_to_their_face`, `release_at`, `owner_reviewed`, `created_at`), `MemoryParticipant`.
- `splitter.py`: `split_entry(entry, llm, people) -> list[MemoryDraft]`. Strict-JSON prompt, one event per Memory, participant name/alias matching against known People (new names come back as unmatched `ParticipantMention`s for the caller to persist), auto-seal on any sensitive category, robust JSON repair (fenced code blocks, surrounding prose, brace-extraction fallback, skips malformed items instead of crashing). Kept free of DB access on purpose — it's the only place that talks to the LLM for this and it's fully unit-testable with a fake LLM (11 tests, `tests/test_splitter.py`).
- `service.py`: `create_entry_and_memories` — the DB-touching half. Finds-or-creates People, resolves `about_person`, embeds each Memory's text, sets `release_at = created_at + settings.holding_period_days` (default 7, ADR 0001).
- `recall.py`: `ArchiveMemoryRecall` implementing `MemoryRecall` (`app/conversation/contracts.py`). Embeds the query, does a pgvector cosine-distance search over-fetched by `k * 5`, then filters through `can_see` for the given Visitor **before** anything is returned — so a Sealed/not-yet-released/private Memory can never reach a prompt. `visitor_id=None` (Owner) bypasses filtering entirely, matching the Memory Assistant's "full archive" contract.
- `digest.py`: `build_release_digest(session, now, within_days=None) -> list[DigestItem]` (Memories releasing within `settings.digest_window_days`, default 3; Sealed Memories are always excluded) plus `render_digest_text`.
- `api.py`: `POST /entries`, `POST /entries/audio` (saves the uploaded audio under `data/audio/` — gitignored — then transcribes and splits), `GET /memories` (Owner's full view), `PATCH /memories/{id}` (`sealed`, `proposed_visibility`, `text` — re-embeds on text change, `owner_reviewed`), `GET /digest`, `POST /assistant/chat` (recall with `visitor_id=None`, second-person system prompt, `[Memory <id>]` citation format parsed and filtered to only IDs actually recalled, and an honest "I don't have a memory of that" when nothing matches instead of calling the LLM at all).

**Providers**
- `app/providers/embed_gemini.py`: `GeminiEmbedder` using `gemini-embedding-001` with `output_dimensionality` truncation (default 768 dims, configurable via `EMBEDDING_DIMENSIONS`). Registered as `get_embedder()` in `app/providers/registry.py`.
- `app/archive/api.py` wraps `get_llm`/`get_embedder`/`get_stt` in thin `Depends()`-friendly functions (`llm_dependency` etc.) instead of calling the registry directly from route bodies — needed so tests can override providers via FastAPI's `dependency_overrides` the standard way; calling the registry functions directly inside a handler body is invisible to FastAPI's DI and can't be overridden.

## How to run

```
cd backend
uv run uvicorn app.main:app --reload
```

Needs a real `GEMINI_API_KEY` in `.env` for `/entries`, `/entries/audio`, and `/assistant/chat` to actually call the LLM/embedder; the test suite never needs one (fakes throughout).

## Test results

```
cd backend && uv run pytest -q
................................................................
64 passed in 5.56s
```

Breakdown: 27 visibility table-driven tests (+4 design-case tests folded into the 27), 11 splitter tests (fake LLM, no DB), 6 service tests, 3 recall tests, 5 digest tests, 9 API tests (all against the real local Postgres/pgvector at `test_memory`, per common-rules.md #7 — each test runs in its own rolled-back transaction so nothing persists between tests or collides with other agents' runs), plus the pre-existing 3 registry tests.

## Deviations from the brief

- **Embedding model name**: the brief said to check current google-genai docs. Docs were ambiguous between `gemini-embedding-001` (documented as GA/stable, still listed) and a newer `gemini-embedding-2` reference that turned up in one fetch. I went with `gemini-embedding-001` since it's the name consistently confirmed as generally available; this is a one-line config change (`GEMINI_EMBEDDING_MODEL`) if it turns out to be stale. **Unverified against a live API call** — no API key available in this environment.
- **Digest window**: the brief didn't specify N days for "the next N days"; I added a `DIGEST_WINDOW_DAYS` setting (default 3), separate from `HOLDING_PERIOD_DAYS` (default 7), so a digest can be requested/scheduled independently of the Holding Period length.
- **Explicit visibility list**: the Memory model and `can_see` fully support `proposed_visibility="explicit"` with a `visibility_person_ids` list (per CONTEXT.md), but `split_entry` never proposes it — the brief's splitter rules only mention private/participants/all_visitors as LLM-proposed values. An explicit list would be set later by the Owner via `PATCH /memories/{id}` in a follow-up (the PATCH endpoint currently doesn't accept `visibility_person_ids`; that's the one gap here if the Owner wants to set an explicit list from the UI without a DB console).
- **Audio storage**: Entries created via `POST /entries/audio` are written under `<repo>/data/audio/<uuid>.<ext>` (gitignored per common-rules #5) since there was no existing convention for where diary audio should live (as opposed to `likeness/`, which is for the Owner's voice/face reference clips, a different thing).

## Unverified

- The Gemini embedding model name/dimensions weren't checked against a real API response (no key in this sandbox) — verify with a live call before relying on it.
- `POST /entries/audio` was tested with a fake `SpeechToText`; the real Groq Whisper integration for this new call path (multipart upload -> bytes -> `transcribe`) hasn't been exercised against the real Groq API.
- No load/performance testing of the pgvector cosine-distance query at realistic Memory counts.
