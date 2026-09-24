# feat/modal-voice

Makes the Clone's cloned voice fast by running Chatterbox on a Modal GPU, with local CPU
Nano kept as the automatic fallback (ADR 0003: the Clone must always speak in the Owner's
cloned voice, so "fast" has to mean a faster cloned-voice path, not a stock voice).

## What was built

1. **`deploy/modal_voice/app.py`** — a Modal app (`modal.App`, `@app.cls(gpu="T4", ...)`,
   `@modal.enter()` to load the model once per container, `@modal.fastapi_endpoint`) that
   loads **Chatterbox-Turbo** (not Nano) and exposes `POST /speak {text,
   reference_wav_b64?}` → `audio/wav`. Protected by a bearer token checked against a Modal
   Secret (`keepsake-voice-secret` / `VOICE_SHARED_SECRET`). Weights persist in a Modal
   Volume so only the first cold start downloads them. `scaledown_window=60` so it scales
   to zero between conversations.
   - **Model:** Turbo over Nano — Nano exists to survive the Owner's limited CPU RAM; on a
     GPU that constraint is gone, so there's no reason to keep Nano's quality cut. Turbo is
     also what the voice-gpu.md research's reference RTF numbers are quoted against.
   - **GPU:** T4, the cheapest Modal tier (~$0.59/hr) — 16GB VRAM comfortably fits Turbo's
     ~2.2GB checkpoint. L4 is documented as the fallback tier if bench.py shows T4 isn't
     fast enough.
   - **Streaming:** not implemented. The maintained streaming fork
     (davidbrowne17/chatterbox-streaming) is a different package from the pinned
     `resemble-ai/chatterbox` the local fallback already depends on, and doubling the
     Chatterbox variants in play isn't worth it before knowing whether plain
     per-sentence GPU synthesis already clears 1x RTF. Documented as follow-up in
     `app.py`'s module docstring and `docs/notes/modal-voice-setup.md`.

2. **`backend/app/providers/tts_modal.py`** — `ModalVoiceSynth` (HTTP client over
   `httpx`, bearer auth, raises `ModalVoiceError` on transport errors or non-200) and
   `FallbackVoiceSynth` (tries a primary `VoiceSynth`, falls back to a secondary on *any*
   exception, logging a warning). `httpx` moved from a dev-only dependency to a normal one
   (`uv add httpx`) since this provider needs it at runtime, not just in tests.

3. **`backend/app/providers/registry.py`** — `get_voice()` now reads `VOICE_PROVIDER`
   (`local`, the default, or `modal`). `modal` wraps `ModalVoiceSynth` in
   `FallbackVoiceSynth` with local `ChatterboxVoiceSynth` as the fallback. The
   `_overrides["voice"]` check still runs first, unchanged.

4. **`backend/app/config.py`** — new settings: `voice_provider`, `modal_voice_url`,
   `modal_voice_token`, `modal_voice_timeout_seconds`. Added to `.env.example`.

5. **`deploy/modal_voice/bench.py`** — standalone script (not pytest) the Owner runs
   after deploying: hits the real endpoint for a cold first sentence and two warm ones,
   parses each WAV's duration from its own header (no extra dependency), and prints a
   wall-time / audio-duration / RTF table plus an average-warm-RTF verdict.

6. **`docs/notes/modal-voice-setup.md`** — step by step for the Owner: `modal token new`,
   creating the `keepsake-voice-secret` Modal Secret, `modal deploy`, setting `.env`,
   running the bench, a cost table (T4 ~50 GPU-hours/month, L4 ~37, against the $30
   credit) with reasoning about why real usage should likely stay under that, and a short
   troubleshooting section (401s, image build failures, weights not caching).

7. **Tests** — `backend/tests/test_tts_modal.py` (new): `ModalVoiceSynth` success, bearer
   header sent correctly, reference WAV included/omitted, non-200 → `ModalVoiceError`,
   transport error → `ModalVoiceError`, empty URL rejected; `FallbackVoiceSynth` uses
   primary on success, falls back on primary exception, falls back on `httpx.TimeoutException`
   specifically; `get_voice()` picks local by default, picks modal-wrapped-in-fallback when
   configured, and still honours `_overrides` over `VOICE_PROVIDER=modal`. All via
   `httpx.MockTransport` — no real network calls. Also added a `ModalVoiceSynth` param
   (via a fake transport) to the shared `voice_synth_provider` fixture in
   `backend/tests/contracts/test_voice_synth.py`, so it runs the same
   speak-returns-bytes/WAV/empty-text/long-text contract as every other `VoiceSynth`.

## What's verified

- `cd backend && TEST_DATABASE_URL=postgresql+psycopg://keepsake:keepsake@127.0.0.1:5433/test_modal_voice uv run pytest -q`
  → **179 passed, 2 skipped, 4 deselected** (the 2 skips are the pre-existing
  Chatterbox-extra-not-installed and RUN_LIVE gates; the 4 deselected are `slow`-marked).
- `ModalVoiceSynth`'s HTTP behaviour (headers, JSON body shape, status handling,
  timeout→exception) is exercised against `httpx.MockTransport`, matching how the real
  Modal endpoint's contract is expected to behave — but this is still a mock, not the
  deployed endpoint.
- The Modal API surface used in `app.py` (`modal.App`, `@app.cls(gpu=...)`,
  `@modal.enter()`, `@modal.fastapi_endpoint(method="POST")`, `modal.Volume.from_name(...,
  create_if_missing=True)`, `modal.Secret.from_name(...)`, `scaledown_window`) was checked
  against current modal.com/docs pages (fetched during this work) — decorator/parameter
  names are current as of 2026-09-24, including two recent renames
  (`web_endpoint`→`fastapi_endpoint`, `container_idle_timeout`→`scaledown_window`).

## What's NOT verified (needs the Owner)

- **`deploy/modal_voice/app.py` has never actually been deployed or run.** This
  environment has no Modal account, so `modal token new`, `modal deploy`, and an actual
  cold-start/warm RTF measurement are all undone. `deploy/modal_voice/bench.py`'s numbers
  are not faked anywhere in this codebase — they only exist once the Owner runs it against
  a real deployment.
  - This means the Turbo-on-T4 RTF claim ("should manage < 1x real time") is a
    reasoned prediction from the T4/L4 numbers in `docs/notes/voice-gpu.md`
    (chatterbox-streaming's RTX 4090 numbers, scaled down) and Modal's own hardware specs,
    not a measurement. If the bench shows Turbo-on-T4 doesn't clear 1x RTF, the two
    documented next steps are: try Nano on the same T4 (same code path, just flip
    `nano=False` to `nano=True` in `app.py`), or move to L4.
- The FastAPI `Header(...)` auth pattern in `app.py`'s `speak` endpoint is written to
  Modal's documented shape for `@modal.fastapi_endpoint` methods but has not been run
  through Modal's actual build/deploy pipeline, so a syntax or API mismatch there
  wouldn't surface until the Owner runs `modal deploy`.
- Cost estimates in `docs/notes/modal-voice-setup.md` use Modal's published per-hour GPU
  rates as of 2026-09-24; Modal can change pricing, and the doc says to re-check
  modal.com/pricing before relying on the numbers.

## What the Owner must do by hand

See `docs/notes/modal-voice-setup.md` for the full walkthrough. Summary:

1. Create a Modal account, `pip install modal`, `modal token new`.
2. `modal secret create keepsake-voice-secret VOICE_SHARED_SECRET=<random token>`.
3. `pip install modal fastapi` (local machine, for the deploy step) then
   `modal deploy deploy/modal_voice/app.py` — note the printed `.modal.run` URL.
4. Set `VOICE_PROVIDER=modal`, `MODAL_VOICE_URL`, `MODAL_VOICE_TOKEN` in `backend/.env`.
5. Run `deploy/modal_voice/bench.py` against the deployed endpoint (ideally with
   `likeness/voice/reference.wav`) and check the printed RTF — if it's not under 1.0 on
   warm requests, see the Nano/L4 follow-ups above.
6. Watch actual Modal spend for the first month against the $30 credit; the cost estimate
   in the setup doc explains the trade-off between `scaledown_window` and cold-start
   frequency if it needs tuning.
