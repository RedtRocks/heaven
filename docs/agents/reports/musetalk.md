# Report: feat/musetalk — photoreal face replies

## What was built

**Research**: `docs/notes/face-musetalk.md` — MuseTalk 1.5 (MIT), install/inference steps,
and the Kaggle API (classic `kaggle` PyPI package: auth, kernel-metadata.json,
dataset-metadata.json, push/status/output). Marks what's unverified (exact kernel status
strings, MuseTalk's output filename convention, weight-caching persistence between runs)
since there's no live Kaggle account in this environment.

**Kaggle kernel**: `notebooks/musetalk_kaggle/` — `musetalk_kernel.py` (clones MuseTalk,
installs deps, downloads weights, builds an inference config from
`/kaggle/input/keepsake-face-jobs/jobs/*.wav` + the reference face dataset, runs inference,
globs for `*.mp4` output and copies each to `/kaggle/working/out/<job_id>.mp4`),
`kernel-metadata.json` (GPU + internet on, two dataset sources), `dataset-metadata.json`
(template for the jobs dataset), `README.md`.

**Providers** (`backend/app/providers/`):
- `face_musetalk_kaggle.py` — `MuseTalkKaggleFaceRenderer` implements `FaceRenderer.render()`
  as the full synchronous round trip (push a new WAV as a dataset version → push+run the
  kernel → poll `kernels_status` → download output → return the MP4 bytes). Talks to Kaggle
  only through a small `KaggleClient` Protocol; `RealKaggleClient` wraps the actual `kaggle`
  package (imported lazily, inside a method, so importing this module never requires the
  `kaggle` package to be installed — it's an optional dependency group, `uv add --optional
  musetalk kaggle`). Only an exact configured "done" status (`"complete"`) is treated as
  success and a configured set of statuses as failure; anything else means "keep polling"
  so an unexpected real status degrades to a timeout rather than a false success.
- `face_still.py` — `StillPhotoFaceRenderer`, the cheap fallback: ffmpeg muxes
  `likeness/face/photo.jpg` (looped, still) with the reply WAV into an MP4. Raises a clear
  `FfmpegNotFoundError` if `ffmpeg` isn't on PATH, and `OwnerPhotoMissingError` if the photo
  isn't there yet.
- `registry.py` — added `get_face()` (checks `_overrides["face"]` first, then
  `FACE_PROVIDER` = `musetalk_kaggle` | `still`) and `get_voice()` (checks
  `_overrides["voice"]`; with no override it raises `NotImplementedError`, since no real
  `VoiceSynth` is wired up on this branch — voice cloning is separate work. `POST
  /face/jobs` can still be used today by passing `audio` directly instead of `text`).

**Job API** (`backend/app/face/`, new module):
- `models.py` — `FaceJob` (id, status `queued|running|done|error`, error, mp4_path,
  timestamps).
- `jobs.py` — `create_job(text=, audio_wav=)` resolves the audio (via `get_voice()` for
  text, or the given WAV), writes it under `data/face_jobs/`, inserts the job row; `run_job
  (job_id)` renders via `get_face()` and updates status; `get_job(job_id)`. Each opens its
  own DB session via `SessionLocal` rather than the request-scoped session, because
  rendering happens in a FastAPI `BackgroundTask` *after* the request (and its session
  dependency) has already finished — this is deliberately structured like a small
  job-queue table, committed independently of the request's own transaction.
- `api.py` — `router` at `/face`: `POST /face/jobs` (multipart form, `text` or `audio` file)
  → `{job_id, status, mp4_url, error}`, `GET /face/jobs/{id}` → same shape, `GET
  /face/jobs/{id}/video` → the MP4 (404/409/410 for not-found/not-ready/gone).
- `backend/app/main.py` registers `app.face.models` (table registration) and
  `face_router` with the two required one-liners.

**Config**: `backend/app/config.py` gained `face_provider` (default `"still"`),
`face_jobs_dir`, `face_photo_path`, `ffmpeg_path`, `kaggle_username`, `kaggle_key`,
`kaggle_kernel_id`, `kaggle_jobs_dataset_id`, `kaggle_poll_interval_seconds`,
`kaggle_timeout_seconds`. `.env.example` documents all of them.

## How to run

```
cd backend
uv run uvicorn app.main:app --reload
```

Default `FACE_PROVIDER=still`. To use MuseTalk on Kaggle: set `FACE_PROVIDER=musetalk_kaggle`
plus the `KAGGLE_*` variables (see below for what the Owner needs to do first), and `uv sync
--extra musetalk` to install the `kaggle` package.

```
curl -F "audio=@reply.wav" http://localhost:8000/face/jobs
# {"job_id": "...", "status": "queued", "mp4_url": null, "error": null}
curl http://localhost:8000/face/jobs/<job_id>
# {"job_id": "...", "status": "done", "mp4_url": "/face/jobs/<job_id>/video", "error": null}
curl http://localhost:8000/face/jobs/<job_id>/video -o out.mp4
```

## Tests — verified

```
TEST_DATABASE_URL=postgresql+psycopg://keepsake:keepsake@127.0.0.1:5433/test_musetalk uv run pytest -q
```

```
96 passed, 2 skipped in 9.06s
```

The 2 skips are the `StillPhotoFaceRenderer` tests that need a real `ffmpeg` binary, which
isn't installed in this environment (`shutil.which("ffmpeg") is None` → `pytest.mark.skipif`).
Their logic (missing-ffmpeg and missing-photo error paths, and a real ffmpeg round-trip
using a synthetic color image) is otherwise identical to what would run with ffmpeg present.

New/changed tests:
- `backend/tests/contracts/test_face_renderer.py` — added `MuseTalkKaggleFaceRenderer` to
  the shared FaceRenderer contract fixture, driven by a `FakeKaggleClient` (completes
  instantly, hands back a valid minimal MP4), so it runs through the same
  bytes/ftyp-header/empty-audio/size-variation checks as `FakeFaceRenderer`. Added dedicated
  tests for polling (`queued`→`running`→`complete`), the error-status path, the timeout
  path, and "kernel finished but produced no mp4". Added the two ffmpeg-gated
  `StillPhotoFaceRenderer` tests plus one non-gated missing-ffmpeg test.
- `backend/tests/test_face.py` (new) — `registry.get_face()`/`get_voice()` provider
  selection and override behavior; the full job API happy path with audio input
  (queued → done, mp4 fetchable, `fake_face_renderer.calls` recorded); the text-input path
  (uses `fake_voice_synth`, recorded correctly); 422 for neither text nor audio, 404 for an
  unknown job, 409 for fetching video before it's ready.

Ran against this branch's own database, `test_musetalk` (confirmed it already existed;
never touched `keepsake`). Also confirmed `backend/tests/test_architecture.py` still passes:
neither `face_still.py` nor `face_musetalk_kaggle.py` imports `kaggle`/`torch`/etc. at module
level (the real `kaggle` import in `RealKaggleClient` is lazy, inside a method), and both
live under `app/providers/` anyway so it would be allowed either way.

Note on Docker: the shared `keepsake-db` Postgres container (used by all agents'
worktrees) had stopped along with Docker Desktop before I started; I started Docker Desktop
and `docker start keepsake-db` to bring it back up. I didn't touch any other worktree or
its data.

## What the Owner must do by hand

1. **Record a reference face video** — a few seconds of the Owner facing the camera, ideally
   speaking naturally (MuseTalk drives an existing face; it doesn't need to say anything in
   particular). Save it as, e.g., `likeness/face/reference.mp4` (never committed — `likeness/`
   is gitignored).
2. **Add a still photo** for the cheap fallback: a clear, front-facing photo at
   `likeness/face/photo.jpg`.
3. **Create a Kaggle account and API token**: https://www.kaggle.com/settings → API →
   "Create New Token" → set `KAGGLE_USERNAME` and `KAGGLE_KEY` in `.env` (never commit them).
4. **Create the two Kaggle datasets** (one-time, via the `kaggle` CLI or the website):
   - `keepsake-face-ref`: upload the reference video from step 1.
   - `keepsake-face-jobs`: create it with a placeholder `jobs/placeholder.wav` file — the
     provider pushes new versions of this dataset per job.
   Then fill in the real `<username>/keepsake-face-jobs` id in
   `notebooks/musetalk_kaggle/dataset-metadata.json`, and both dataset ids (plus your own
   username in place of `keepsake-musetalk`'s id) in
   `notebooks/musetalk_kaggle/kernel-metadata.json`.
5. **Set `KAGGLE_KERNEL_ID` and `KAGGLE_JOBS_DATASET_ID`** in `.env` to match what you used
   above (e.g. `yourname/keepsake-musetalk`, `yourname/keepsake-face-jobs`).
6. **First push**: run `kaggle kernels push -p notebooks/musetalk_kaggle` once by hand and
   watch it run in the Kaggle UI (Settings → Notebooks) to confirm your free GPU quota is
   available and the run actually reaches "complete" — this is also the moment to sanity
   check the "unverified" bits called out in `docs/notes/face-musetalk.md` (real status
   strings, output filenames) against what actually happens, and adjust
   `MuseTalkKaggleFaceRenderer`'s `done_status`/`error_statuses` if Kaggle's real values
   turn out to differ.
7. **Install ffmpeg** locally (or wherever the backend runs) for the `still` fallback to
   work at all — not installed in this dev environment; get it from
   https://ffmpeg.org/download.html and put it on PATH, or set `FFMPEG_PATH`.
8. To actually use MuseTalk instead of the still fallback: `uv sync --extra musetalk` (or
   `uv add --optional musetalk kaggle` was already run on this branch, so a plain `uv sync`
   with the extra should suffice) and set `FACE_PROVIDER=musetalk_kaggle`.

## Unverified (see docs/notes/face-musetalk.md for detail)

- Exact Kaggle kernel status strings (`kernels_status`'s real return shape/values) — no live
  account was available to observe one. Handled defensively: only an exact match on
  `"complete"` counts as success, only a configured set counts as failure, everything else
  polls until timeout.
- MuseTalk's exact output filename convention inside `result_dir` — the kernel script globs
  for `*.mp4` rather than assuming a name.
- Whether MuseTalk's weights/MuseTalk repo checkout actually persist between separate Kaggle
  kernel runs (Kaggle's `/kaggle/working` caching behavior for script kernels specifically)
  — if not, every run re-clones and re-downloads weights, which is slow but not incorrect.
- The `kaggle` package's `dataset_create_version`/`kernels_push`/`kernels_output` Python
  method signatures were cross-referenced against a third-party doc page (the official docs
  only cover the CLI) and general knowledge of the package; not exercised against a live
  account.

## Deviations / design notes

- Added `get_voice()` to the registry (not explicitly asked for) because `POST /face/jobs`
  accepting `text` needs a `VoiceSynth` to turn it into audio, and the test fixtures/`client`
  fixture already anticipated a `voice` override key. It raises `NotImplementedError` until
  a real voice provider is merged from whatever branch owns that; `audio` input works today.
- `FaceJob` rows are written via their own `SessionLocal()` session rather than the
  request's `db_session`, on purpose (see `app/face/jobs.py`'s docstring) — a background
  task's session must outlive the request. One side effect: in tests, `FaceJob` rows commit
  for real against the test database rather than being rolled back per test like everything
  else using the `db_session`/`client` fixtures. Job ids are random UUIDs, so this doesn't
  cause cross-test interference, but it does mean `face_job` rows accumulate in
  `test_musetalk` across test runs (harmless, but noting it since it diverges from the
  savepoint-per-test pattern everything else uses).
- `MuseTalkKaggleFaceRenderer.render()` is fully synchronous per the `FaceRenderer` Protocol
  (as required); the "expose an async job API" half of the brief lives one layer up, in
  `app/face/jobs.py`'s `run_job` + FastAPI's `BackgroundTasks`, not in the provider itself.
