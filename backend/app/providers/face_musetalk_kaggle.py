"""FaceRenderer that renders the Owner's face via MuseTalk on a free Kaggle GPU (T4/P100).

This is slow (minutes: dataset upload, queueing for a free GPU, MuseTalk's own setup+
inference). `render()` does the whole synchronous round trip; `app/face/jobs.py` wraps it in
a FastAPI BackgroundTask so `POST /face/jobs` can return immediately.

See docs/notes/face-musetalk.md for the researched Kaggle API and MuseTalk details, and for
what's unverified (exact kernel status strings, output filenames) — this module is written
defensively around those unknowns: it globs for output instead of assuming a filename, and
only treats an exact configured "done" status as success so an unexpected status string means
"keep waiting / eventually time out" rather than a false "success".

The real `kaggle` package is imported only inside `RealKaggleClient`, and only inside a
method body — this file lives under app/providers/, which is the one place allowed to import
vendor SDKs (see docs/agents/common-rules.md rule 3 and backend/tests/test_architecture.py).
"""

from __future__ import annotations

import glob
import json
import os
import shutil
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from app.config import Settings, get_settings

REPO_ROOT = Path(__file__).resolve().parents[3]
KERNEL_DIR = REPO_ROOT / "notebooks" / "musetalk_kaggle"

DEFAULT_DONE_STATUS = "complete"
DEFAULT_ERROR_STATUSES = frozenset({"error", "cancelacknowledged", "cancelled"})


class KaggleJobError(RuntimeError):
    """The Kaggle kernel run failed or produced no usable output."""


class KaggleTimeoutError(RuntimeError):
    """The Kaggle kernel didn't finish within the configured timeout."""


class KaggleClient(Protocol):
    """The slice of the Kaggle API this provider needs.

    Lets tests use a fake instead of the real `kaggle` PyPI package. See
    docs/notes/face-musetalk.md for what the real methods correspond to.
    """

    def push_jobs_dataset(self, wav_path: Path) -> None:
        """Push a new version of the private jobs dataset containing this one WAV."""
        ...

    def push_and_run_kernel(self) -> None:
        """Push the MuseTalk kernel (this also starts a run — Kaggle has no separate call)."""
        ...

    def get_status(self) -> str:
        """Return the latest kernel run's status, lowercased."""
        ...

    def download_output(self, dest_dir: Path) -> None:
        """Download the kernel's /kaggle/working output into dest_dir."""
        ...


class RealKaggleClient:
    """Wraps the real `kaggle` PyPI package's `KaggleApi` class.

    Unverified against a live account (no credentials in this environment) — see
    docs/notes/face-musetalk.md. Kept intentionally small so the untested parts are just
    thin pass-throughs to the vendor SDK, with the actual job logic (polling, timeouts,
    output matching) in MuseTalkKaggleFaceRenderer, which IS tested via FakeKaggleClient.
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._api = None

    def _client(self):
        if self._api is None:
            if self._settings.kaggle_username:
                os.environ.setdefault("KAGGLE_USERNAME", self._settings.kaggle_username)
            if self._settings.kaggle_key:
                os.environ.setdefault("KAGGLE_KEY", self._settings.kaggle_key)
            from kaggle.api.kaggle_api_extended import KaggleApi  # vendor SDK: providers/ only

            api = KaggleApi()
            api.authenticate()
            self._api = api
        return self._api

    def push_jobs_dataset(self, wav_path: Path) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            jobs_subdir = Path(tmp) / "jobs"
            jobs_subdir.mkdir()
            shutil.copyfile(wav_path, jobs_subdir / wav_path.name)
            (Path(tmp) / "dataset-metadata.json").write_text(
                json.dumps(
                    {"title": "keepsake-face-jobs", "id": self._settings.kaggle_jobs_dataset_id}
                )
            )
            self._client().dataset_create_version(tmp, version_notes=f"job {wav_path.stem}", quiet=True)

    def push_and_run_kernel(self) -> None:
        self._client().kernels_push(str(KERNEL_DIR))

    def get_status(self) -> str:
        result = self._client().kernels_status(self._settings.kaggle_kernel_id)
        # The classic `kaggle` package's return shape for kernels_status has varied across
        # versions (a plain string vs. an object/dict with a `status` field) and I couldn't
        # verify the current one without a live account — see docs/notes/face-musetalk.md.
        # Handle both defensively rather than assuming.
        status = getattr(result, "status", None)
        if status is None and isinstance(result, dict):
            status = result.get("status")
        if status is None:
            status = result
        return str(status).lower()

    def download_output(self, dest_dir: Path) -> None:
        dest_dir.mkdir(parents=True, exist_ok=True)
        self._client().kernels_output(
            self._settings.kaggle_kernel_id, path=str(dest_dir), force=True, quiet=True
        )


class MuseTalkKaggleFaceRenderer:
    """FaceRenderer: MuseTalk on a free Kaggle GPU, driven through a `KaggleClient`."""

    def __init__(
        self,
        settings: Settings | None = None,
        kaggle_client: KaggleClient | None = None,
        sleep: Callable[[float], None] = time.sleep,
        done_status: str = DEFAULT_DONE_STATUS,
        error_statuses: frozenset[str] = DEFAULT_ERROR_STATUSES,
    ):
        self._settings = settings or get_settings()
        self._client = kaggle_client or RealKaggleClient(self._settings)
        self._sleep = sleep
        self._done_status = done_status
        self._error_statuses = error_statuses

    def render(self, audio_wav: bytes) -> bytes:
        with tempfile.TemporaryDirectory() as tmp:
            wav_path = Path(tmp) / "job.wav"
            wav_path.write_bytes(audio_wav)

            self._client.push_jobs_dataset(wav_path)
            self._client.push_and_run_kernel()
            self._wait_for_completion()

            out_dir = Path(tmp) / "out"
            self._client.download_output(out_dir)
            mp4_files = sorted(glob.glob(str(out_dir / "**" / "*.mp4"), recursive=True))
            if not mp4_files:
                raise KaggleJobError(f"Kaggle kernel finished but produced no .mp4 under {out_dir}")
            return Path(mp4_files[0]).read_bytes()

    def _wait_for_completion(self) -> None:
        deadline = time.monotonic() + self._settings.kaggle_timeout_seconds
        while True:
            status = self._client.get_status()
            if status == self._done_status:
                return
            if status in self._error_statuses:
                raise KaggleJobError(f"Kaggle kernel run failed with status {status!r}")
            if time.monotonic() > deadline:
                raise KaggleTimeoutError(
                    f"Kaggle kernel did not reach {self._done_status!r} within "
                    f"{self._settings.kaggle_timeout_seconds}s (last status: {status!r})"
                )
            self._sleep(self._settings.kaggle_poll_interval_seconds)
