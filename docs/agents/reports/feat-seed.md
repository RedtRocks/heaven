# Report: feat/seed — persona, Seed Interview and the text Clone

## What was built

New package `backend/app/persona/`:

- **`models.py`**: `Trait` (text, source stated|inferred, confirmed, about_person_id, said_to_their_face, created_at), `StyleSample` (text, person_id, source), `Relationship` (person_id PK, tone_notes, questionnaire JSON, can_see_all_visitors_memories), `SeedAnswer` (question_id, text) to track which Seed Interview questions have been answered.
- **`seed_questions.json`** + **`seed_questions.py`**: 54 Check-in Questions (48 general across favourites/beliefs/habits/humour/advice/phrases/legacy, 6 per-Relationship with a `{name}` placeholder), loaded via `load_seed_questions()`.
- **`relationship_questions.py`**: an 8-question Relationship questionnaire (`RELATIONSHIP_QUESTIONS`), served at `GET /relationships/questionnaire`.
- **`whatsapp.py`**: `parse_whatsapp_export(text, owner_name)` — handles Android (`12/03/24, 9:15 pm - Name: msg`) and iOS (`[12/03/24, 9:15:02 PM] Name: msg`) formats, multi-line messages, `<Media omitted>`/system lines, keeps only the Owner's messages (matched case-insensitively), drops everyone else's words entirely.
- **`traits.py`**: `extract_traits(question, answer, llm)` — prompts the LLM for a JSON array of Traits, tolerant of markdown fences and surrounding prose, validates each item with a pydantic model, drops malformed items. Also `usable_by_clone(traits, visitor_id)` — the filtering rule (stated always usable; inferred only if confirmed; a Trait about the current Visitor is hidden unless `said_to_their_face`).
- **`prompt.py`**: `build_clone_system_prompt(session, visitor_id, recalled)` — assembles usable Traits, up to 5 Style Samples (Visitor-specific if any exist, else general), the Relationship's tone notes, and the given Memories, plus the fixed behaviour rules (life facts only from Traits/Memories, may reason warmly on generic questions, never invents events, warm "I don't recall telling you that" for gaps, never hints at other Memories).
- **`recall.py`**: `get_memory_recall()` factory returning a stub `MemoryRecall` that always returns `[]`, to be swapped for the archive module's real implementation later.
- **`api.py`**: `router` (no prefix, exact paths as specified) with `GET /seed/next`, `POST /seed/answer`, `POST /seed/answer/audio`, `GET/POST/PATCH /traits`, `POST /style-samples/whatsapp`, `GET /relationships/questionnaire`, `GET/PUT /relationships/{person_id}`, `POST /clone/chat`.

`backend/app/main.py` now imports `app.persona.models` (table registration) and includes `persona_router` with one line, per common-rules.

## How to run

```
cd backend
uv run uvicorn app.main:app --reload
```

Seed Interview loop: `GET /seed/next` → `POST /seed/answer {question_id, text}` (or `/seed/answer/audio` multipart with `question_id` + `audio`) until `/seed/next` returns `null`. Per-Relationship questions are expanded once per row in `person`, as `"<question_id>:<person_id>"`, with `{name}` filled in.

Clone chat: `POST /clone/chat {"message": "...", "history": [], "visitor_id": null}` → `{"reply": "...", "citations": []}` (citations always empty until the real `MemoryRecall` is wired in).

## Tests — verified

```
cd backend && uv run pytest -q
```

```
47 passed in 7.00s
```

Covers: WhatsApp parsing (both formats, multi-line, media-omitted, system lines, other-person messages never returned, case-insensitive owner match, empty export), Trait extraction (clean/fenced/prose-wrapped JSON, malformed-item tolerance, empty-answer short-circuit) and the `usable_by_clone` filtering rules (stated-always-usable, inferred-needs-confirmation, said-to-face gating), the prompt builder (trait/style-sample/tone-notes/memory inclusion and exclusion, against the real Postgres test schema), and the full API surface end-to-end (seed loop termination, duplicate-answer 409, unknown-question 404, per-Relationship expansion, Traits CRUD, WhatsApp import endpoint, Relationship GET/PUT, Clone chat prompt construction and citation shape) using fake LLM/STT providers — no real API keys or network calls.

Ran against the branch's own database, `postgresql+psycopg://keepsake:keepsake@127.0.0.1:5433/test_seed` (never `keepsake`), via `backend/tests/conftest.py`.

## Deviations from the brief

- Added `GET /relationships/questionnaire` (not explicitly listed in task-seed.md) to serve the 8-question Relationship questionnaire the brief asked for. Registered before `/relationships/{person_id}` so the literal path wins.
- `extract_traits`-derived Traits are stored with `source="stated", confirmed=True` (the Owner said it directly during the Seed Interview), matching the glossary's "stated" Trait definition. Traits created via `POST /traits` default to `source="inferred", confirmed=False` instead, since that endpoint is for the Owner reviewing Traits proposed by other modules (e.g. an inference pipeline), not for restating something directly.
- `get_llm`/`get_stt` from `app.providers.registry` take an optional `settings` parameter, which FastAPI misinterprets as a request-body field when passed straight into `Depends()` (it produced a spurious `settings` field in the request schema and 422s on every call). Added tiny no-arg wrappers `_get_llm`/`_get_stt` in `app/persona/api.py` that routes actually depend on; this only affects how persona's routes consume the registry, the registry itself is unchanged.
- Duplicate `POST /seed/answer` for an already-answered question returns `409 Conflict` rather than silently re-answering or erroring; not specified in the brief but seemed the safer default.

## Unverified / left undone

- No live LLM/Gemini call was exercised (tests use a fake LLM per common-rules — there are no real API keys in this environment). The prompt→LLM wiring is exercised end-to-end structurally, but actual answer quality/tone from a real model is unverified.
- `MemoryRecall` is a stub returning `[]`; Clone chat will have no real Memories or citations until the archive module's implementation is swapped in via `app/persona/recall.py`.
- The web app (Next.js) side of the Seed Interview / Relationship setup UI was not touched — this task was backend-only per task-seed.md.
- No load/perf testing of WhatsApp import on very large export files.
