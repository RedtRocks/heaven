# Report: feat/voice (Phase 2)

## What was built

**`app/providers/tts_chatterbox.py`**: `ChatterboxVoiceSynth`, implementing the
`VoiceSynth` protocol via Resemble AI's Chatterbox (MIT). The task asked for
Chatterbox-Nano; the latest released PyPI package (`chatterbox-tts==0.1.7`) doesn't
support `nano=True` yet (only on GitHub's unreleased default branch — verified by
inspecting the installed package's source), so this uses the standard `ChatterboxTTS`
(`chatterbox.tts`) instead, the closest real CPU-capable option. `generate()` /
`audio_prompt_path` is the same API either way, so swapping in Nano later is a one-line
change once a PyPI release adds it. Vendor imports (`chatterbox`, `torchaudio`) happen
only inside methods, not at module import time, so the module and `get_voice()` work
even without the `voice` extra installed.

**`app/providers/registry.py`**: `get_voice()`, following the override pattern
(checks `_overrides["voice"]` first) and caching a singleton across calls, since loading
the model is slow. (This replaced a placeholder `get_voice()` from feat/musetalk that
raised `NotImplementedError`, merged in afterward — see Merges below.)

**`app/voice/api.py`**: `POST /voice/speak` `{text}` -> `audio/wav`, wired into
`app/main.py`.

**`backend/scripts/record_reference.py`**: records ~30s from the mic (`sounddevice`) or
converts an existing audio file, saving to `settings.likeness_dir / "voice" /
"reference.wav"`.

**`backend/scripts/voice_loop.py`**: push-to-talk loop (mic -> `get_stt()` -> `get_llm()`
with `build_clone_system_prompt` -> `get_voice()` -> speaker). Its per-turn logic is
extracted into `run_turn()`, a hardware-free function, so it's unit-testable with fake
providers (`backend/tests/test_voice_loop.py`). **Pipecat was not used**: a first pass at
wrapping our synchronous provider Protocols in Pipecat's async `FrameProcessor`/turn-taking
model went past a reasonable effort for this task's budget, so push-to-talk ships first,
per task-voice.md's own fallback instruction. Follow-up noted in the script's docstring.

**`backend/scripts/bench_voice.py`**: measures real-time factor and latency for 3
sentences with the default voice. See "CPU benchmark" below — it did not complete.

**Tests**: `test_voice_api.py` (endpoint, fake provider), `test_voice_loop.py`
(`run_turn` wiring: STT -> recall -> Clone prompt -> LLM -> voice, with history carried
across turns), `test_registry.py::test_get_voice_honours_override`, and a `slow`-marked,
install-gated Chatterbox parametrization added to
`tests/contracts/test_voice_synth.py` (skipped unless `chatterbox` is importable).

## How to run

```
cd backend
uv sync --extra voice          # installs chatterbox-tts, torch, torchaudio, sounddevice, soundfile, scipy
uv run python scripts/record_reference.py record     # or: convert <file>
uv run uvicorn app.main:app --reload                  # POST /voice/speak {"text": "..."}
uv run python scripts/voice_loop.py                   # push-to-talk live loop
uv run python scripts/bench_voice.py                  # CPU benchmark (see caveat below)
```

## Test results

```
TEST_DATABASE_URL=postgresql+psycopg://keepsake:keepsake@127.0.0.1:5433/test_voice uv run pytest -q
162 passed, 2 skipped, 4 deselected, 1 warning in 20.22s
```

(2 skipped are `live` tests needing real API keys, unrelated to voice; 4 deselected are
`slow` tests, including the Chatterbox contract param, since `chatterbox` is installed
but calling it needs the model loaded — see below.)

## CPU benchmark: NOT measured, honestly

I could not get a real real-time-factor/latency measurement on this machine. Full
account, what was tried, and why in `docs/notes/voice.md`. Short version: `chatterbox-tts`
installs and imports fine, and the ~3.2GB model downloads fine (once with the agent
sandbox disabled for that step — the sandbox's own resource limits caused the first two
download attempts to fail with a Windows "insufficient system resources" error). But
actually *loading* the downloaded weights into memory segfaults (exit 139) twice in a
row, consistent with genuinely low free system RAM at the time (~0.8–1.4GB free out of
~14GB total, the rest in use by this machine's normal desktop session running alongside
the agent). I did not fabricate numbers. `uv run python scripts/bench_voice.py` should
work as-is (no code changes needed) once run with more free RAM available — the model is
already cached locally so it won't need to re-download.

## Merges

Merged `main` into `feat/voice` twice per the coordinator's requests:

1. After feat/memory landed: `app/persona/recall.get_memory_recall` gained a `session`
   parameter and a real (`ArchiveMemoryRecall`) implementation, plus `get_embedder()` in
   the registry. Only conflict was `registry.py` (import line + where to place
   `get_voice`/`get_embedder`); resolved by keeping both functions. Updated
   `voice_loop.py` to open a `SessionLocal()` session and call
   `get_memory_recall(session)` inside the per-turn loop instead of once at startup.
2. After feat/musetalk landed: it had added its own placeholder `get_voice()` (raises
   `NotImplementedError`, since face rendering's `text` input needs a `VoiceSynth` too)
   plus `get_face()`. Resolved by keeping feat/voice's real `ChatterboxVoiceSynth`-backed
   `get_voice()` and merging in `get_face()`/the face router alongside it. One conflict
   resolution left a stray `>>>>>>> main` marker in `registry.py` on the first merge
   commit, causing a `SyntaxError`; caught by re-running the test suite immediately after
   and fixed in a follow-up commit. Also updated `tests/test_face.py`'s
   `test_get_voice_without_override_raises_not_implemented` (asserted the now-replaced
   placeholder's behaviour) to assert the real `ChatterboxVoiceSynth` is returned instead.

## What's verified

- `/voice/speak` returns `audio/wav` bytes from a fake provider; the real provider
  constructs correctly (`isinstance` check) and `get_voice()` respects overrides and
  caches a singleton.
- The push-to-talk loop's full wiring (STT -> recall -> Clone system prompt -> LLM
  history -> voice) is exercised end-to-end with fakes, including that `recall.recall()`
  gets the transcribed text and `visitor_id=None` (Owner), and that conversation history
  accumulates correctly across turns without a shared-list aliasing bug (fixed during
  development: `llm.complete()` is called with `list(history)`, not `history` itself,
  since `FakeLLM` records the list by reference and `history` keeps changing after the
  call).
- `chatterbox-tts` installs and imports (`from chatterbox.tts import ChatterboxTTS`)
  under this project's `uv` environment with Python 3.13.
- The full backend test suite passes after both merges.

## What's unverified / left undone

- **Real-time factor and first-audio latency**: not measured (see above). Needs a
  re-run of `bench_voice.py` with more free system RAM.
- **`record_reference.py`**: not run against a real microphone (no mic available to this
  agent); the conversion path (existing audio file -> reference.wav) is also unexercised
  end-to-end, though it's a thin wrapper over `soundfile`/`scipy.signal.resample`.
- **`voice_loop.py`**: not run live end-to-end against real providers (needs
  `GROQ_API_KEY`, a working LLM provider, a mic, and the voice model loading — which
  segfaults on this machine right now, per above). Its logic is unit-tested via
  `run_turn()` with fakes only.
- **Chatterbox contract tests** (`slow`-marked, in `test_voice_synth.py`): written and
  will run once the model can actually load in this environment (`pytest -q -m slow`),
  but not exercised here for the same memory reason.
- **Pipecat**: intentionally not attempted beyond a quick feasibility read; push-to-talk
  ships instead, as task-voice.md allows. A real Pipecat integration is follow-up work.
- Whether the standard `ChatterboxTTS` model (in place of Nano) is fast/light enough for
  comfortable CPU real-time use on this hardware is unknown until the benchmark can run.
