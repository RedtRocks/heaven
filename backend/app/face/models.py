from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class FaceJob(Base):
    """A request to render the Owner's face saying some reply audio.

    Rendering (MuseTalk on a free Kaggle GPU, or the ffmpeg still-photo fallback) can take
    minutes, so a FaceJob tracks progress for `GET /face/jobs/{id}` while it runs in a
    background task. Deliberately written and updated through its own DB session
    (see app/face/jobs.py) rather than the request's session, since it must survive past the
    request that created it.
    """

    __tablename__ = "face_job"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued|running|done|error
    error: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    mp4_path: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
