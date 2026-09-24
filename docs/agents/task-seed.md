# Task: persona, Seed Interview and the text Clone (branch feat/seed), Phase 1

Goal: before any daily Entries exist, the Clone already answers like the Owner, and each Visitor gets the right tone. Read CONTEXT.md carefully (Trait, Check-in Question, Seed Interview, Style Sample, Relationship, Clone).

## 1. `app/persona/`
- **Trait**: `text`, `source` (`stated` | `inferred`), `confirmed: bool`, `about_person_id` (nullable, → Person), `said_to_their_face: bool`, `created_at`. The Clone uses a Trait only if it is stated or confirmed. An inferred, unconfirmed Trait is used only by the Memory Assistant. A Trait about a person reaches THAT person only if said_to_their_face.
- **Check-in Question bank**: write ~50 good Seed Interview questions in `app/persona/seed_questions.yaml` (or JSON). Cover favourites, beliefs, habits, humour, advice, how the Owner talks to close people, what they'd want family to remember, and phrases they often use. Some are per-Relationship ("How do you usually tease/comfort <name>?"). Warm and natural, not a form.
- **Answers → Traits**: `extract_traits(question, answer, llm)` turns one answer into one or more stated Traits (JSON output, validated).
- **Style Sample**: `text`, `person_id` (who the Owner was talking to, nullable), `source`. **WhatsApp import**: `parse_whatsapp_export(text, owner_name)` handles both Android (`12/03/24, 9:15 pm - Name: msg`) and iOS (`[12/03/24, 9:15:02 PM] Name: msg`) formats, multi-line messages, and `<Media omitted>`/system lines. It keeps ONLY the Owner's messages (other people's words are dropped, never stored) and links them to the other person. Test it heavily with fixture strings.
- **Relationship**: `person_id`, `tone_notes`, `questionnaire` (JSON answers), `can_see_all_visitors_memories: bool = True`. Include a short Relationship questionnaire (~8 questions: what they call each other, tone, inside jokes, topics to avoid).
- **Prompt builder**: `build_clone_system_prompt(session, visitor_id, recalled: list[RecalledMemory]) -> str`. It speaks in the first person as the Owner and uses confirmed Traits, a few Style Samples (for that Visitor if any, else general) for tone, and the Relationship's tone notes. Rules in the prompt: answer life facts only from the given Memories or Traits. For generic questions (advice, opinions in the Owner's style) it may reason warmly. For a life fact it has no Memory for, it says warmly that it never told them / doesn't remember, and is never cold. It never invents events. It never hints that other Memories exist.

## 2. API (`app/persona/api.py`)
- `GET /seed/next` → next unanswered question. `POST /seed/answer {question_id, text}` → stores the answer and the extracted Traits. `POST /seed/answer/audio` → multipart, transcribed via `get_stt()`.
- `GET/POST/PATCH /traits` (the Owner confirms/rejects inferred Traits).
- `POST /style-samples/whatsapp` multipart `file` + `owner_name` + optional `person_id`.
- `GET/PUT /relationships/{person_id}`.
- `POST /clone/chat {message, history, visitor_id?}` → `{reply, citations}`. Get Memories via a `MemoryRecall` implementation. The memory agent is building the real one in parallel, so depend only on the Protocol, and inject a stub that returns [] (from a small factory function in `app/persona/recall.py` that later gets swapped to the archive's implementation). `visitor_id` None here means the Owner testing their own Clone.

Tests: fake LLM, WhatsApp parser fixtures, Trait filtering rules (unconfirmed never reaches the Clone, behind-back Traits never reach their subject), prompt builder content. For DB tests, use the local Postgres at 5433 with your own schema or tables so you don't collide with other agents. Report as described in common-rules.
