# Face rendering research: MuseTalk on Kaggle

Researched 2026-09-24 for `feat/musetalk` (task-musetalk.md). Links checked live via web
fetch/search; anything I could not confirm against a primary source is marked **unverified**.

## MuseTalk

Repo: https://github.com/TMElyralab/MuseTalk (MIT license, confirmed in the repo's own
license statement: "The code of MuseTalk is released under the MIT License. There is no
limitation for both academic and commercial usage.")

- **Current version**: MuseTalk 1.5, released 2025-03-28. 1.0 is still available/supported.
  We target 1.5 since it's what the README's own inference examples default to.
- **Python/CUDA**: Python 3.10, PyTorch 2.0.1, CUDA 11.7 (or the cu118 wheel). This matches
  what Kaggle's GPU notebooks ship (Kaggle images bundle a working CUDA + PyTorch stack, so
  the kernel script installs MuseTalk's own pinned deps on top rather than fighting the base
  image).
- **Install steps** (from the README):
  1. `pip install -r requirements.txt`
  2. MMLab ecosystem via openmim: `mim install mmengine`, then `mmcv==2.0.1`,
     `mmdet==3.1.0`, `mmpose==1.1.0` (these do face detection/pose for the reference video).
  3. ffmpeg binary on PATH, or point `FFMPEG_PATH` at it.
  4. Weights: either run `download_weights.sh` (Linux) / `download_weights.bat` (Windows),
     or download manually from HuggingFace and lay them out under `./models/`:
     musetalk (v1.5 unet + musetalk.json), sd-vae-ft-mse, whisper, dwpose, syncnet,
     face-parse-bisent, resnet18.
- **Inference**:
  - Reference input: a video, a single image, or a directory of images containing the
    face (an ~256x256 face region is what gets driven).
  - Audio input: any audio file MuseTalk can decode (WAV works).
  - Config: `configs/inference/test.yaml` lists `{video_path, audio_path}` pairs — this is
    how you batch multiple audio files against the same reference video in one run.
  - Command (Linux convenience script): `sh inference.sh v1.5 normal`. Underlying Python
    call (also what Windows uses directly):
    ```
    python -m scripts.inference \
      --inference_config configs/inference/test.yaml \
      --result_dir results/test \
      --unet_model_path models/musetalkV15/unet.pth \
      --unet_config models/musetalkV15/musetalk.json \
      --version v15 \
      --ffmpeg_path <path-to-ffmpeg>
    ```
  - Output: one MP4 per config entry, written under `--result_dir`.
- **Unverified**: the exact output filename pattern MuseTalk uses inside `result_dir` (it's
  derived from the input filenames per the repo's own scripts, but I have not run it to
  confirm the precise naming). The Kaggle kernel script below globs for `*.mp4` under the
  result dir rather than relying on an exact name, to be robust to this.

Sources:
- https://github.com/TMElyralab/MuseTalk (README: version, license, install, inference)

## Kaggle API

Two things both called "the Kaggle API" exist right now:

1. **The classic Python package `kaggle`** (`pip install kaggle`, `import kaggle` /
   `from kaggle.api.kaggle_api_extended import KaggleApi`). This is what
   `docs/agents/common-rules.md`'s architecture test means by "no `kaggle` import outside
   `app/providers/`" — it's the one our provider actually uses.
2. **A newer Go-based CLI rewrite**, `Kaggle/kaggle-cli` (adds an OAuth login flow,
   `kaggle auth login`, `KAGGLE_API_TOKEN`, `~/.kaggle/access_token`). Its docs describe the
   same kernel/dataset concepts (kernel-metadata.json, dataset-metadata.json,
   `kernels push/status/output`, `datasets create/version`) but the field names come from
   this rewrite's docs, not the classic package. I've cross-checked the field names below
   against both where possible.

We use the **classic Python package** since it's what has a stable, documented Python API
(`KaggleApi` class) suitable for calling from our backend, and it's the one the repo's own
architecture-test rule already names.

- **Auth**: place `kaggle.json` (downloaded from https://www.kaggle.com/settings → API →
  "Create New Token") at `~/.kaggle/kaggle.json`, or set env vars `KAGGLE_USERNAME` and
  `KAGGLE_KEY`. `KaggleApi().authenticate()` picks either up. `KAGGLE_CONFIG_DIR` can move
  the json file's directory (default `%HOMEPATH%/kaggle.json` on Windows,
  `~/.kaggle/kaggle.json` on Linux/Mac). Our settings pass `KAGGLE_USERNAME`/`KAGGLE_KEY` as
  env vars — Keepsake never writes a `kaggle.json` file itself.
- **kernel-metadata.json** fields (used for `notebooks/musetalk_kaggle/kernel-metadata.json`):
  `id` ("<kaggle-username>/<kernel-slug>"), `title`, `code_file`, `language` (`python`),
  `kernel_type` (`script` or `notebook`), `is_private` (bool), `enable_gpu` (bool — "false"
  if omitted), `enable_internet` (bool — MuseTalk needs internet on first run to pull
  weights from HuggingFace unless we bake them into a dataset), `dataset_sources` (list of
  `"username/dataset-slug"` strings — this is how we attach the reference face video and the
  `jobs/` WAV dataset to the kernel).
- **Push + run**: `kaggle kernels push -p <folder>` (CLI) / `KaggleApi.kernels_push(folder)`
  (Python) uploads the metadata + script and **also triggers a run** — there's no separate
  "run" call. `--accelerator NvidiaTeslaT4` (CLI flag) selects the GPU; in `kernel-metadata.json`
  this corresponds to `enable_gpu: true` (Kaggle picks the GPU type from the notebook's
  accelerator setting/quota; **unverified** whether the classic Python package exposes a
  separate "which GPU" field beyond `enable_gpu`).
- **Poll status**: `kaggle kernels status <owner>/<slug>` (CLI) / `KaggleApi.kernels_status(kernel)`
  (Python). **Unverified**: the exact set of status strings the classic package returns:
  based on the Kaggle web UI and community reports these are along the lines of
  `queued` / `running` / `complete` / `error` / `cancelAcknowledged` — the provider code
  treats anything that isn't `complete` or an error-like string as "still running" and polls
  again, rather than hard-coding an exact enum, specifically because this is unverified.
- **Pull output**: `kaggle kernels output <owner>/<slug> -p <dest>` (CLI) /
  `KaggleApi.kernels_output(kernel, path, force=True)` (Python) downloads the kernel's log
  and any files it wrote to `/kaggle/working/`.
- **Datasets** (for uploading the WAV(s) as kernel input): `dataset-metadata.json` needs at
  least `title` and `id` ("username/dataset-slug"); `kaggle datasets create -p <folder>`
  makes a new dataset, `kaggle datasets version -p <folder> -m "<message>"` pushes a new
  version of an existing one (Python: `dataset_create_new(folder, ...)` /
  `dataset_create_version(folder, version_notes, ...)`). We push a **new version of one
  private "keepsake-face-jobs" dataset** per job rather than a new dataset per job, since
  Kaggle limits how many datasets/kernels a free account can create.

Sources:
- https://github.com/Kaggle/kaggle-cli (repo overview, confirms legacy `~/.kaggle/kaggle.json`
  path plus the newer OAuth flow)
- https://raw.githubusercontent.com/Kaggle/kaggle-cli/main/docs/kernels.md (`kernels push`,
  `--accelerator`, `status`, `output` commands)
- https://raw.githubusercontent.com/Kaggle/kaggle-cli/main/docs/datasets.md (`datasets create`,
  `datasets version`)
- https://technowhisp.com/kaggle-api-python-documentation/ (Python `KaggleApi` class calls:
  `authenticate()`, `kernels_push(folder)`, `kernels_status(kernel)`,
  `kernels_output(kernel, path, force, quiet)` — this third-party page explicitly notes the
  official Kaggle docs only cover CLI usage, not the Python class, which is why it's cited
  alongside the CLI docs above)
- General knowledge of the `kaggle` PyPI package's `kernel-metadata.json` /
  `dataset-metadata.json` field names (`enable_gpu`, `dataset_sources`, `is_private`, etc.),
  cross-checked against the kaggle-cli docs above since the fields are the same concepts.
  **Unverified**: I did not have a live Kaggle account/token to actually push a kernel and
  observe real status strings or output filenames end-to-end.

## What this means for our provider

Because none of the above can be exercised without real Kaggle credentials (which we don't
have), `backend/app/providers/face_musetalk_kaggle.py`:

- Talks to Kaggle only through a small `KaggleClient` Protocol (`push_dataset_version`,
  `push_and_run_kernel`, `get_status`, `download_output`) so the real `kaggle` package is
  wrapped in one adapter and everything else — polling loop, job bookkeeping, error handling
  — is tested against a fake implementing that Protocol.
- Treats kernel status conservatively: only an exact match on a configurable "done" status
  string (default `"complete"`) is treated as success; a configurable set of "failed"
  strings (default `{"error", "cancelAcknowledged"}`) raise; everything else keeps polling.
  This means if Kaggle's real status strings differ from what's documented above, the code
  degrades to "keeps waiting" rather than silently misreporting success/failure — the Owner
  should watch the first real run's logs and adjust `KAGGLE_DONE_STATUS`/`KAGGLE_ERROR_STATUSES`
  in settings if needed.
- Downloads output by globbing for the first `*.mp4` under the downloaded output directory,
  per the "unverified exact output filename" note above.
