"""Runs FaceJobs: writes the audio, renders it via the configured FaceRenderer, tracks status.

Each function here opens its own DB session (via `SessionLocal`, not the request-scoped
`get_session`) because a job's rendering step runs in a FastAPI BackgroundTask *after* the
request that created it has finished — by then the request's session dependency has already
been torn down. This mirrors a small job-queue table: writes are committed immediately and
independently of the request's own transaction, on purpose.
"""

import uuid
from pathlib import Path

from app.config import Settings, get_settings
from app.db import SessionLocal
from app.face.models import FaceJob
from app.providers.registry import get_face, get_voice


def _jobs_dir(settings: Settings) -> Path:
    settings.face_jobs_dir.mkdir(parents=True, exist_ok=True)
    return settings.face_jobs_dir


def create_job(
    *,
    text: str | None = None,
    audio_wav: bytes | None = None,
    settings: Settings | None = None,
) -> FaceJob:
    """Resolves the audio to render (from `text` via VoiceSynth, or `audio_wav` directly),
    writes it under `face_jobs_dir`, and inserts a `queued` FaceJob row.

    Does NOT render — call `run_job(job.id)` (typically via FastAPI's BackgroundTasks) to
    actually do that, since it's slow.
    """
    if not text and not audio_wav:
        raise ValueError("Provide either text or audio_wav")

    settings = settings or get_settings()
    if audio_wav is None:
        audio_wav = get_voice(settings).speak(text)  # type: ignore[arg-type]

    job_id = uuid.uuid4().hex
    (_jobs_dir(settings) / f"{job_id}.wav").write_bytes(audio_wav)

    session = SessionLocal()
    try:
        job = FaceJob(id=job_id, status="queued")
        session.add(job)
        session.commit()
        return job
    finally:
        session.close()


def run_job(job_id: str, settings: Settings | None = None) -> None:
    """Renders a queued job's WAV to MP4 and updates its status to done/error.

    Safe to call from a background task: opens its own session and swallows rendering
    errors into the job's `error` field rather than raising, since there's no request left
    to receive an exception by the time this runs.
    """
    settings = settings or get_settings()
    session = SessionLocal()
    try:
        job = session.get(FaceJob, job_id)
        if job is None:
            return
        job.status = "running"
        session.commit()

        wav_path = _jobs_dir(settings) / f"{job_id}.wav"
        try:
            mp4_bytes = get_face(settings).render(wav_path.read_bytes())
            mp4_path = _jobs_dir(settings) / f"{job_id}.mp4"
            mp4_path.write_bytes(mp4_bytes)
            job.status = "done"
            job.mp4_path = str(mp4_path)
        except Exception as exc:  # noqa: BLE001 - surfaced via job.error, not re-raised
            job.status = "error"
            job.error = str(exc)
        session.commit()
    finally:
        session.close()


def get_job(job_id: str) -> FaceJob | None:
    session = SessionLocal()
    try:
        return session.get(FaceJob, job_id)
    finally:
        session.close()
