# Live mode for the Memory Assistant

Speech-to-speech "Talk live" for `/assistant`, via Gemini Live. Stock Voice only, per ADR
0003: never used by `/clone`.

## What was built

**Backend**

- `app/providers/__init__.py`: `LiveVoiceSession` Protocol plus event types
  (`LiveAudioChunk`, `LiveTranscript`, `LiveToolCall`, `LiveTurnComplete`,
  `LiveSessionEnded`).
- `app/providers/live_gemini.py`: the only place `google.genai`'s live client is
  imported. `GeminiLiveSession.connect(...)` opens `client.aio.live.connect(...)`,
  configures audio-only responses, the Stock Voice, the `recall_memories` function
  declaration, and input/output transcription; translates Gemini's message shapes into
  the Protocol's event types.
- `app/providers/registry.py`: `get_live(system_instruction, tools, settings=None)`
  (async - opening a session is a connect, not a cheap constructor). Checks
  `_overrides["live"]` first, same pattern as every other `get_*`.
- `app/live/recall.py`: `recall_for_live` calls the existing `ArchiveMemoryRecall` for the
  Owner (`visitor_id=None`) and then re-checks `Memory.sealed` directly against the DB,
  dropping any Sealed result before it can reach Gemini. This is a second gate on top of
  `ArchiveMemoryRecall`, because for the Owner `can_see` already returns `True` for Sealed
  Memories (correct for the text Memory Assistant, which the Owner already uses to see
  everything of their own) - but live mode hands results to a third-party vendor, and
  ADR 0003 / `docs/notes/live-mode.md` say Sealed must never leave the backend for that.
  Also holds the `recall_memories` tool declaration and the Memory Assistant system prompt.
- `app/live/api.py`: `/live/assistant` WebSocket. Browser sends binary frames (mic PCM,
  16 kHz/16-bit LE/mono) and receives binary frames (model audio, 24 kHz) plus JSON text
  frames (`transcript`, `turn_complete`, `session_ended`, `error`). Runs two relay
  coroutines concurrently (`asyncio.gather`): browser→Gemini and Gemini→browser. Executes
  `recall_memories` tool calls server-side via `recall_for_live` and answers unknown tool
  names with an error result rather than crashing the session. On `LiveSessionEnded`
  (Gemini's ~10 minute connection limit, or any other drop) it sends a `session_ended`
  message with a reason and returns cleanly - no resumption is implemented (see
  "Unverified / left undone").
- `app/config.py`: `LIVE_MODEL` (default `gemini-2.5-flash-native-audio-preview-09-2025`)
  and `LIVE_VOICE` (default `"Puck"`).
- `app/main.py`: one line, `app.include_router(live_router)`.

**Tests** (`backend/tests/test_live.py`, `tests/fakes.py: FakeLiveSession`)

- `FakeLiveSession` implements `LiveVoiceSession`, plays back a scripted list of events,
  and records `send_audio`/`send_tool_result` calls. `fake_live_factory(session)` wraps it
  for `registry.override(live=...)`, since `get_live` is async.
- Sealed filtering: `test_recall_for_live_drops_sealed_memories`,
  `test_filter_sealed_removes_only_sealed_ids` - real Postgres rows, one Sealed, one not;
  asserts the Sealed text never appears in results.
- Relay: `test_relay_streams_audio_and_transcripts_from_fake_live_session` drives a full
  WebSocket round trip through `TestClient.websocket_connect` and checks transcript JSON,
  raw audio bytes, `turn_complete`, and `session_ended` all arrive in order, and that mic
  bytes reached the fake session.
- Tool execution: `test_relay_executes_recall_memories_tool_call_excluding_sealed` and
  `test_relay_reports_unknown_tool_call`.
- `test_real_gemini_live_session_connects` is marked `@pytest.mark.live` and skipped
  unless `RUN_LIVE=1` (existing project convention, `tests/conftest.py`) - **there is no
  API key in this environment, so this test has never actually run.** Added
  `pytest-asyncio` as a dev dependency and `asyncio_mode = "strict"` to `pyproject.toml`
  for it.

**Web**

- `lib/liveAudio.ts` (pure, no DOM): `resampleFloat32` (linear interpolation),
  `floatTo16BitPCM` / `pcm16ToFloat32` (round-trip PCM encode/decode), `encodeMicChunk`
  (resample-then-encode for the mic path), `rmsAmplitude` (the interruption heuristic).
  Unit-tested in `lib/liveAudio.test.ts` (18 tests: resampling ratios, round-trip
  accuracy, clamping, byte order, RMS behaviour).
- `public/live-mic-worklet.js`: an `AudioWorkletProcessor` that forwards raw Float32 mic
  samples to the main thread (it can't import the TS helpers - it runs on the audio
  rendering thread).
- `components/LiveTalk.tsx`: opens the WebSocket, runs the AudioWorklet mic pipeline,
  encodes and sends chunks, and plays back 24 kHz PCM via a queued
  `AudioBufferSourceNode` chain (schedules each chunk after the last, so chunks play
  gapless without needing a full jitter buffer). Local interruption: when
  `rmsAmplitude` on a mic chunk crosses a threshold, or a `user` transcript frame arrives,
  it stops all in-flight playback sources immediately. Cleans up mic stream, both
  AudioContexts, and the socket on stop/unmount.
- `components/AssistantLive.tsx` / `app/assistant/page.tsx`: `page.tsx` stays a server
  component (keeps its `metadata` export); the toggle, live transcript panel, and
  existing `<Chat>` moved into the new client component `AssistantLive.tsx`.
- `lib/api.ts`: added `getWsUrl(path)` (same host as the HTTP API, `ws:`/`wss:`).

## 3D face: skipped, and why

The task allowed reusing `FaceStage` for streamed audio "if that's clean; otherwise skip
the face and explain why." I skipped it. `FaceStageCanvas`'s only audio-driven path
(`speakWithAudio`) hands a full `Blob`/`<audio>` element to `wawa-lipsync`'s
`connectAudio(audioElement)`, which analyses a decodable file, not a live PCM stream.
Making that accept `/live/assistant`'s chunked PCM would mean building a
`MediaStreamAudioDestinationNode` bridge (feed the same `AudioBufferSourceNode` chain
`LiveTalk.tsx` already plays into a stream, then hand that stream to `wawa-lipsync` or
TalkingHead's viseme driver instead of an `<audio>` element) and get it working through
TalkingHead's WebGL/Three.js runtime, which I can't exercise or verify without a browser
and a GLB avatar in this environment - real risk of shipping something that silently does
nothing. The 24 kHz PCM the WebSocket already emits is exactly what `docs/notes/live-mode.md`
says TalkingHead/wawa-lipsync want, so the follow-up work is plumbing, not a design
question; flagging it here rather than guessing at an unverified implementation.

## Test and build output

Backend (`cd backend && TEST_DATABASE_URL=postgresql+psycopg://keepsake:keepsake@127.0.0.1:5433/test_live_mode uv run pytest -q`):

```
167 passed, 3 skipped, 4 deselected, 1 warning in 7.53s
```

(3 skipped are the project's other `@slow`/pre-existing conditional tests; 4 deselected
are `@slow`; the live-Gemini test above is additionally gated by `RUN_LIVE`, which wasn't
set, so it's among the deselected/skipped set - not run.)

Web:

```
pnpm test   -> Test Files 2 passed (2), Tests 24 passed (24)
pnpm lint   -> clean, no errors
pnpm build  -> Compiled successfully, TypeScript passed, all routes static
```

## Live model name

`gemini-2.5-flash-native-audio-preview-09-2025`, set as `LIVE_MODEL`'s default. Per
`docs/notes/live-mode.md` (dated the same day as this work) this is the documented
native-audio preview id; the same notes flag that model names were moving from 2.5 to 3.x
during 2026 ("Gemini 3.8 Live" mentioned as newer/listed) and say to check
https://ai.google.dev/gemini-api/docs/pricing at build time. I did a web search rather than
just trusting the pre-existing note and it corroborated both names circulating (2.5 Flash
Live API pages still live, "Gemini 3.8 Live" announced) without resolving which one is
current free tier as of today - so this default is **unverified** and should be confirmed
against the pricing page before relying on it. It's a plain settings field, so switching
model id needs no code change.

## Unverified / not run

- **No API key in this environment** - nothing here has been exercised against the real
  Gemini Live API. `test_real_gemini_live_session_connects` (`@pytest.mark.live`) exists
  for that and only runs with `RUN_LIVE=1` and `GEMINI_API_KEY` set.
- The exact shape of `google-genai`'s live message objects
  (`server_content.model_turn`, `output_transcription`, `tool_call.function_calls`, etc.)
  in `app/providers/live_gemini.py`'s `_translate` is written from the SDK's documented
  API surface, not verified against a live response - a key rename in a future SDK
  version could go unnoticed since no @live test exercises it here.
- **Session resumption** for the ~10 minute connection limit is not implemented; the
  session instead ends cleanly and reports `session_ended` to the browser, matching the
  task's "or at least end cleanly with a clear message" fallback. The browser doesn't
  auto-reconnect; a user who wants to keep going has to press "Talk live" again.
- The mic AudioWorklet, playback scheduling, and interruption heuristic
  (`SPEECH_RMS_THRESHOLD = 0.02`) have not been run in a real browser against a real
  microphone - only their pure logic (`lib/liveAudio.ts`) is unit-tested. The threshold is
  a guess and will likely need tuning once someone can actually talk to it.
- 3D face integration is not built (see above).
- Sample rates: input is fixed at 16 kHz to match Gemini Live's documented expectation;
  output is fixed at 24 kHz per `docs/notes/live-mode.md`. Neither is read back from the
  server's actual `mime_type` on the audio part, so if Gemini ever changes its output rate
  this would need updating in both `live_gemini.py` and `lib/liveAudio.ts`.
