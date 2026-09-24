"""Cheap FaceRenderer fallback: dub the reply audio over a still photo of the Owner.

No GPU and no Kaggle round trip — just ffmpeg. Used when FACE_PROVIDER=still (the default),
or whenever MuseTalk/Kaggle isn't set up. See docs/notes/face-musetalk.md and
docs/agents/reports/musetalk.md for what the Owner needs to provide.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

from app.config import Settings, get_settings


class FfmpegNotFoundError(RuntimeError):
    """ffmpeg isn't on PATH. See docs/notes/face-musetalk.md for install links."""


class OwnerPhotoMissingError(RuntimeError):
    """The Owner hasn't added a face photo yet."""


class StillPhotoFaceRenderer:
    """FaceRenderer: freezes a photo and dubs `audio_wav` over it into an MP4 via ffmpeg."""

    def __init__(self, settings: Settings | None = None, ffmpeg_path: str | None = None):
        s = settings or get_settings()
        self._photo_path = s.face_photo_path
        self._ffmpeg = ffmpeg_path or s.ffmpeg_path

    def _require_ffmpeg(self) -> None:
        if shutil.which(self._ffmpeg) is None:
            raise FfmpegNotFoundError(
                f"ffmpeg not found ({self._ffmpeg!r} not on PATH). Install ffmpeg and make "
                "sure it's on PATH, or set FFMPEG_PATH. See docs/notes/face-musetalk.md."
            )

    def render(self, audio_wav: bytes) -> bytes:
        self._require_ffmpeg()
        if not self._photo_path.exists():
            raise OwnerPhotoMissingError(
                f"No Owner photo at {self._photo_path}. Add a photo of the Owner's face "
                "there (see docs/agents/reports/musetalk.md)."
            )
        with tempfile.TemporaryDirectory() as tmp:
            wav_path = Path(tmp) / "audio.wav"
            wav_path.write_bytes(audio_wav)
            out_path = Path(tmp) / "out.mp4"
            subprocess.run(
                [
                    self._ffmpeg,
                    "-y",
                    "-loop",
                    "1",
                    "-i",
                    str(self._photo_path),
                    "-i",
                    str(wav_path),
                    "-c:v",
                    "libx264",
                    "-tune",
                    "stillimage",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    "-pix_fmt",
                    "yuv420p",
                    "-shortest",
                    str(out_path),
                ],
                check=True,
                capture_output=True,
            )
            return out_path.read_bytes()
