# Keepsake v1 build plan

Terms are defined in [CONTEXT.md](../CONTEXT.md). Decisions are recorded in [docs/adr/](adr/).

## What v1 is

A laptop-only build for one Owner. It has two goals, in order:

1. **A Clone that looks, sounds and talks like the Owner.** It has a cloned voice in real time, a stylized 3D face in real time, and photoreal pre-rendered video replies.
2. **Memory modules built properly from the start**, so the archive can grow later without a rewrite.

The Owner tests the Visitor side personally, using a second email address. No real Visitors in v1.

## Stack

| Piece | Choice | Fallback |
|---|---|---|
| Backend | Python, FastAPI | |
| Database | Postgres + pgvector, local | |
| Web app | Next.js (TypeScript) | |
| Voice pipeline | Pipecat, running locally | |
| Speech-to-text | Groq Whisper-large-v3-turbo (free) | local faster-whisper `small` int8 |
| LLM | Gemini Flash-Lite (free) | gpt-5-nano (paid, pennies) |
| Voice clone | Chatterbox-Nano, local on CPU | XTTS-v2 (Hindi), Cartesia Pro for one month |
| 3D face, real time | Stylized head in three.js, visemes from TTS audio | |
| Photoreal face | MuseTalk on a free Kaggle/Colab GPU, pre-rendered | animated still photo |
| Email | Gmail SMTP with an app password | |

Every AI piece sits behind an adapter ([ADR 0002](adr/0002-free-providers-behind-adapters.md)).

## Modules

The boundaries that keep later growth cheap:

- **providers**: one interface each for `LLM`, `SpeechToText`, `VoiceSynth` and `FaceRenderer`. Nothing else imports a vendor SDK.
- **archive**: Entries, Memories (one event each), Participants.
- **visibility**: one function answers "can Visitor V see Memory M right now?" All the rules live here: Sealed wins → Holding Period → Participant or proposed Visibility → Private by default. The "said to their face" rule for opinions about a person is also here. It's the most heavily tested module.
- **persona**: Traits (stated, inferred, confirmed), Style Samples (Owner's side only), Relationships.
- **likeness**: the Owner's voice reference clips and face assets. These are local files the Owner owns.
- **conversation**: the Memory Assistant (full archive, second person) and the Clone (filtered through `visibility`, first person, cites Memories). Generic questions are answered in the Owner's style. Life facts with no Memory get a warm "I never told you that."

## Build order

Each phase ends with something you can run and judge.

**Phase 0: Skeleton.** Repo, FastAPI, local Postgres, Next.js shell, and the four provider interfaces with one implementation each.
*Done when:* one text round-trip reaches Gemini through the adapter.

**Phase 1: Seed.** Seed Interview (about 50 Check-in Questions, answered by typing or speaking) → Traits. WhatsApp export import → Style Samples, keeping only the Owner's lines.
*Done when:* the text Clone answers "what's your favourite food?" and "any advice for my exam?" in a way you'd call yours.

**Phase 2: Voice.** Record reference clips, clone with Chatterbox-Nano, then build the Pipecat loop: mic → Whisper → LLM with persona → Chatterbox → speaker.
*Done when:* you can talk to it live, the latency is measured, and you judge whether the voice sounds like you.

**Phase 3: 3D face in real time.** Stylized head built from your photos, rendered in the browser, with lip-sync driven by the voice output.
*Done when:* you talk to a face on screen that moves its mouth in sync.
*Open research:* which open-source photo-to-3D-head tool to use. Decide at the start of this phase.

**Phase 4: Photoreal video replies.** Record face video, run MuseTalk on Kaggle to render a reply clip from the Clone's audio. If this doesn't work, fall back to an animated still photo.
*Done when:* a question gets a video reply of your face saying the answer.

**Phase 5: Memory.** Text and voice Entries → split into Memories → Participants detected → Visibility proposed → sensitive categories auto-Sealed → Holding Period → Release Digest email. Memory Assistant chat with citations. Scheduled Check-in Questions. Inferred Traits are confirmed in Check-ins.
*Done when:* the four test questions from design Q7 behave as agreed, and a Sealed Memory can't be reached by any prompt you try.

**Phase 6: Visitor flow.** Relationship setup questionnaire, invite by email link, sign-in with that email, Clone filtered through `visibility`.
*Done when:* signed in with your second email as "Riya", you can't reach anything Sealed, Private-without-Participant, or said behind her back.

## Parked until after v1

- Legacy Mode, and how the Executor proves a death
- Grief safeguards (session limits, crisis support path)
- Phone and wearable input, and the local nightly model for Entry processing
- Recording a consent statement to create a clone
- Cloud hosting (the MVP moves off the laptop)
- Real-time photoreal face (needs a paid GPU)

## Unverified facts to check as we build

- Kaggle's weekly GPU quota, and MuseTalk speed on a T4
- Chatterbox-Nano latency on a 6-core Ryzen 5 7530U
- Exact Gemini free-tier rate limits (shown in AI Studio)
- Simli's free real-time avatar minutes
