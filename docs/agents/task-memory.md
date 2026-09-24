# Task: memory and visibility (branch feat/memory), Phase 5 core

This is the heart of the product. Get the rules exactly right. Design decisions: CONTEXT.md, ADR 0001, and the plan's Modules section.

## 1. `app/archive/` (models + logic)
- **Entry**: raw text (a voice Entry is stored as its transcript, plus the audio path), `created_at`.
- **Memory**: `text` (one event only), `happened_on`, `entry_id`, `embedding` (pgvector), `sealed: bool`, `sensitive_category: str | None` (health, money, romance, others_secret), `proposed_visibility` (`private` | `participants` | `all_visitors` | explicit list of person ids), `release_at` (end of Holding Period), `owner_reviewed: bool`, `created_at`.
- **MemoryParticipant**: memory ↔ Person (`app/people/models.py`).
- **Opinion about a person**: when a Memory holds the Owner's opinion about a Participant, record `about_person_id` and `said_to_their_face: bool`. It's true ONLY when the Entry explicitly says the Owner told them. Ambiguous means false.
- **Splitter**: `split_entry(entry, llm, people) -> list[MemoryDraft]`. It uses `get_llm()` with a strict JSON-output prompt. Rules: one event per Memory, so a Memory never hints at a neighbouring event. Example from the design: "Argued with Riya at dinner, then texted X who I'm secretly seeing" becomes two Memories, and the first must not mention texting anyone. Match Participants to known People by name/alias, and create new People for new names. Set sensitive_category; any sensitive category → `sealed=True`. Propose a visibility. Validate and repair the LLM's JSON robustly.
- **Holding Period**: configurable (setting `HOLDING_PERIOD_DAYS`, default 7). `release_at = created_at + period`.
- **Release Digest**: `build_release_digest(session, now) -> list[DigestItem]` covers Memories whose release_at falls in the next N days, with their proposed visibility. (Emailing it is a later task. Just build the data plus a plain-text rendering.)

## 2. `app/visibility/`: ONE pure function
`can_see(memory, visitor_id, now) -> bool` (plus a `why` variant returning the rule that decided it, for debugging). Precedence, in order:
1. Owner (visitor_id None) sees everything.
2. `sealed` → never.
3. `now < release_at` → not yet.
4. An opinion about a person that the Visitor is the subject of, and `said_to_their_face` is False → never, for that Visitor.
5. `proposed_visibility`: `private` → only if the Visitor is a Participant. `participants` → Participants only. `all_visitors` → yes. Explicit list → the listed ids.

Participant access unlocks Private, never Sealed. Write thorough table-driven tests covering every rule and every precedence conflict, including these design cases:
- A secret texting Memory is Sealed and Riya is a Participant → Riya can't see it.
- "Rahul is unreliable, ugh" (said behind his back) → Rahul can't see it; others can if the visibility allows.
- "I told Rahul he's unreliable" → Rahul can see it.
- A Private Memory with no Participants → no Visitor sees it.

Also: the Clone must never hint that a hidden Memory exists. Enforce this by filtering BEFORE retrieval results reach any prompt.

## 3. Recall: implement `MemoryRecall` (`app/conversation/contracts.py`)
Embed with an `Embedder` provider. Add a Gemini embedding implementation in `app/providers/embed_gemini.py` (check the google-genai docs for the current embedding model name and dimensions) and register `get_embedder()`. Do vector search in pgvector, then apply `can_see` for the Visitor. Over-fetch so filtering still leaves k results.

## 4. API (`app/archive/api.py`)
- `POST /entries {text}` stores the Entry and splits it (synchronously for now).
- `POST /entries/audio` (multipart `file`) transcribes via `get_stt()`, then does the same.
- `GET /memories`: the Owner's view, including sealed state, visibility, release_at and Participants.
- `PATCH /memories/{id}` with `{sealed?, proposed_visibility?, text?, owner_reviewed?}`.
- `GET /digest`: the Release Digest.
- `POST /assistant/chat {message, history}` → `{reply, citations}`: the Memory Assistant. It uses recall with visitor_id=None, addresses the Owner in the second person, cites Memory ids, and says so plainly when nothing matches instead of inventing.

Tests: fake LLM/Embedder. Tests that need the DB may use the real local Postgres at 5433, but must create and drop their own schema or tables so they don't collide with other agents' test runs. Report as described in common-rules.
