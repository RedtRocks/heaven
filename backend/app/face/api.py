from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.face.jobs import create_job, get_job, run_job
from app.face.models import FaceJob

router = APIRouter(prefix="/face", tags=["face"])


class FaceJobOut(BaseModel):
    job_id: str
    status: Literal["queued", "running", "done", "error"]
    mp4_url: str | None = None
    error: str | None = None

    @classmethod
    def from_job(cls, job: FaceJob) -> "FaceJobOut":
        return cls(
            job_id=job.id,
            status=job.status,  # type: ignore[arg-type]
            mp4_url=f"/face/jobs/{job.id}/video" if job.status == "done" else None,
            error=job.error,
        )


@router.post("/jobs", response_model=FaceJobOut)
async def create_face_job(
    background_tasks: BackgroundTasks,
    text: str | None = Form(None),
    audio: UploadFile | None = File(None),
) -> FaceJobOut:
    """Kick off a face render from either `text` (spoken via the Owner's cloned voice, once
    that's wired up) or a WAV `audio` file. Returns immediately with a job_id; poll
    GET /face/jobs/{job_id} for status, then fetch mp4_url once status is "done"."""
    audio_bytes = await audio.read() if audio is not None else None
    if not text and not audio_bytes:
        raise HTTPException(422, "Provide either `text` or `audio`")

    try:
        job = create_job(text=text, audio_wav=audio_bytes)
    except NotImplementedError as exc:
        raise HTTPException(503, str(exc)) from exc

    background_tasks.add_task(run_job, job.id)
    return FaceJobOut.from_job(job)


@router.get("/jobs/{job_id}", response_model=FaceJobOut)
def get_face_job(job_id: str) -> FaceJobOut:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    return FaceJobOut.from_job(job)


@router.get("/jobs/{job_id}/video")
def get_face_job_video(job_id: str) -> FileResponse:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    if job.status != "done" or not job.mp4_path:
        raise HTTPException(409, f"job is {job.status!r}, not ready yet")
    path = Path(job.mp4_path)
    if not path.exists():
        raise HTTPException(410, "rendered video is no longer available")
    return FileResponse(path, media_type="video/mp4", filename=f"{job_id}.mp4")
