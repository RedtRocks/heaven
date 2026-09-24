"""Contract tests for FaceRenderer providers.

Any class implementing the FaceRenderer protocol must pass these tests.
"""

import pytest

from app.providers import FaceRenderer
from tests.fakes import FakeFaceRenderer, FakeVoiceSynth


class FakeKaggleClient:
    """Fake KaggleClient (see app/providers/face_musetalk_kaggle.py): completes instantly
    and hands back a valid-looking minimal MP4, so MuseTalkKaggleFaceRenderer can be run
    through the same FaceRenderer contract tests as everything else without touching Kaggle.
    """

    def __init__(self, statuses: list[str] | None = None):
        # Defaults to completing on the first status check. Pass e.g. ["running", "complete"]
        # to exercise the polling loop.
        self._statuses = list(statuses) if statuses else ["complete"]
        self.calls: list[str] = []

    def push_jobs_dataset(self, wav_path):
        self.calls.append("push_jobs_dataset")

    def push_and_run_kernel(self):
        self.calls.append("push_and_run_kernel")

    def get_status(self):
        self.calls.append("get_status")
        if len(self._statuses) > 1:
            return self._statuses.pop(0)
        return self._statuses[0]

    def download_output(self, dest_dir):
        self.calls.append("download_output")
        dest_dir.mkdir(parents=True, exist_ok=True)
        (dest_dir / "out.mp4").write_bytes(FakeFaceRenderer()._make_minimal_mp4())


def _make_musetalk_kaggle_renderer():
    from app.providers.face_musetalk_kaggle import MuseTalkKaggleFaceRenderer

    return MuseTalkKaggleFaceRenderer(
        settings=None,
        kaggle_client=FakeKaggleClient(),
        sleep=lambda _seconds: None,
    )


@pytest.fixture(params=[FakeFaceRenderer, _make_musetalk_kaggle_renderer])
def face_renderer_provider(request):
    """Parametrize tests over all FaceRenderer implementations.

    Add more implementations by importing them here and adding to params.
    Example: params=[FakeFaceRenderer, LivePortraitRenderer]
    """
    return request.param()


def test_face_renderer_render_returns_bytes(face_renderer_provider: FaceRenderer):
    """FaceRenderer.render() must return bytes."""
    # Create a valid WAV file first
    voice_synth = FakeVoiceSynth()
    wav_data = voice_synth.speak("Hello world")

    result = face_renderer_provider.render(wav_data)
    assert isinstance(result, bytes)


def test_face_renderer_render_returns_mp4(face_renderer_provider: FaceRenderer):
    """FaceRenderer.render() must return MP4 bytes (ftyp header)."""
    voice_synth = FakeVoiceSynth()
    wav_data = voice_synth.speak("Hello world")

    result = face_renderer_provider.render(wav_data)
    # All MP4 files contain an ftyp box
    assert b"ftyp" in result


def test_face_renderer_render_handles_empty_audio(face_renderer_provider: FaceRenderer):
    """FaceRenderer.render() must handle empty audio (edge case)."""
    result = face_renderer_provider.render(b"")
    assert isinstance(result, bytes)
    assert b"ftyp" in result


def test_face_renderer_render_handles_various_audio_sizes(face_renderer_provider: FaceRenderer):
    """FaceRenderer.render() must handle audio of various sizes."""
    # Small audio
    result = face_renderer_provider.render(b"\x00" * 100)
    assert isinstance(result, bytes)

    # Large audio
    result = face_renderer_provider.render(b"\x00" * (1024 * 1024))
    assert isinstance(result, bytes)


# ---------------------------------------------------------------------------
# MuseTalkKaggleFaceRenderer-specific behavior (fake Kaggle client)
# ---------------------------------------------------------------------------


def test_musetalk_kaggle_polls_until_complete():
    from app.providers.face_musetalk_kaggle import MuseTalkKaggleFaceRenderer

    client = FakeKaggleClient(statuses=["queued", "running", "complete"])
    renderer = MuseTalkKaggleFaceRenderer(kaggle_client=client, sleep=lambda _s: None)

    result = renderer.render(b"\x00" * 100)

    assert b"ftyp" in result
    assert client.calls.count("get_status") == 3
    assert client.calls[:2] == ["push_jobs_dataset", "push_and_run_kernel"]


def test_musetalk_kaggle_raises_on_error_status():
    from app.providers.face_musetalk_kaggle import KaggleJobError, MuseTalkKaggleFaceRenderer

    client = FakeKaggleClient(statuses=["error"])
    renderer = MuseTalkKaggleFaceRenderer(kaggle_client=client, sleep=lambda _s: None)

    with pytest.raises(KaggleJobError):
        renderer.render(b"\x00" * 100)


def test_musetalk_kaggle_times_out_if_never_complete():
    from app.providers.face_musetalk_kaggle import KaggleTimeoutError, MuseTalkKaggleFaceRenderer
    from app.config import Settings

    client = FakeKaggleClient(statuses=["running"])
    settings = Settings(kaggle_timeout_seconds=0.01, kaggle_poll_interval_seconds=0)
    renderer = MuseTalkKaggleFaceRenderer(settings=settings, kaggle_client=client, sleep=lambda _s: None)

    with pytest.raises(KaggleTimeoutError):
        renderer.render(b"\x00" * 100)


def test_musetalk_kaggle_raises_if_no_mp4_produced():
    from app.providers.face_musetalk_kaggle import KaggleJobError, MuseTalkKaggleFaceRenderer

    class NoOutputClient(FakeKaggleClient):
        def download_output(self, dest_dir):
            self.calls.append("download_output")
            dest_dir.mkdir(parents=True, exist_ok=True)  # empty: no .mp4 written

    renderer = MuseTalkKaggleFaceRenderer(kaggle_client=NoOutputClient(), sleep=lambda _s: None)

    with pytest.raises(KaggleJobError):
        renderer.render(b"\x00" * 100)


# ---------------------------------------------------------------------------
# StillPhotoFaceRenderer-specific behavior (real ffmpeg; skipped if not installed)
# ---------------------------------------------------------------------------

import shutil  # noqa: E402
import subprocess  # noqa: E402

from app.config import Settings  # noqa: E402

requires_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


@requires_ffmpeg
def test_still_photo_renderer_produces_mp4(tmp_path):
    from app.providers.face_still import StillPhotoFaceRenderer

    photo_path = tmp_path / "photo.jpg"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=64x64",
            "-frames:v",
            "1",
            str(photo_path),
        ],
        check=True,
        capture_output=True,
    )

    settings = Settings(face_photo_path=photo_path)
    renderer = StillPhotoFaceRenderer(settings=settings)

    wav_data = FakeVoiceSynth().speak("Hello world")
    result = renderer.render(wav_data)

    assert isinstance(result, bytes)
    assert b"ftyp" in result


@requires_ffmpeg
def test_still_photo_renderer_missing_photo_raises(tmp_path):
    from app.providers.face_still import OwnerPhotoMissingError, StillPhotoFaceRenderer

    settings = Settings(face_photo_path=tmp_path / "does-not-exist.jpg")
    renderer = StillPhotoFaceRenderer(settings=settings)

    with pytest.raises(OwnerPhotoMissingError):
        renderer.render(FakeVoiceSynth().speak("Hello world"))


def test_still_photo_renderer_missing_ffmpeg_raises(tmp_path):
    from app.providers.face_still import FfmpegNotFoundError, StillPhotoFaceRenderer

    settings = Settings(face_photo_path=tmp_path / "photo.jpg")
    renderer = StillPhotoFaceRenderer(settings=settings, ffmpeg_path="definitely-not-a-real-binary")

    with pytest.raises(FfmpegNotFoundError):
        renderer.render(FakeVoiceSynth().speak("Hello world"))
