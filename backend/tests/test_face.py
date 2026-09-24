"""Tests for the face job API (app/face/) and the provider registry's get_face/get_voice."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.providers import registry
from tests.fakes import FakeFaceRenderer, FakeVoiceSynth


@pytest.mark.unit
def test_get_face_picks_still_provider():
    settings = Settings(face_provider="still")
    face = registry.get_face(settings)

    from app.providers.face_still import StillPhotoFaceRenderer

    assert isinstance(face, StillPhotoFaceRenderer)


@pytest.mark.unit
def test_get_face_picks_musetalk_kaggle_provider():
    settings = Settings(face_provider="musetalk_kaggle")
    face = registry.get_face(settings)

    from app.providers.face_musetalk_kaggle import MuseTalkKaggleFaceRenderer

    assert isinstance(face, MuseTalkKaggleFaceRenderer)


@pytest.mark.unit
def test_get_face_rejects_unknown_provider():
    settings = Settings(face_provider="not-a-real-provider")
    with pytest.raises(ValueError):
        registry.get_face(settings)


@pytest.mark.unit
def test_get_face_override_wins():
    fake = FakeFaceRenderer()
    registry.override(face=fake)
    try:
        assert registry.get_face() is fake
    finally:
        registry.clear_overrides()


@pytest.mark.unit
def test_get_voice_without_override_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        registry.get_voice()


@pytest.mark.db
def test_create_job_requires_text_or_audio(client: TestClient):
    response = client.post("/face/jobs", data={})
    assert response.status_code == 422


@pytest.mark.db
def test_create_and_fetch_job_with_audio(
    client: TestClient, fake_face_renderer: FakeFaceRenderer
):
    wav_bytes = FakeVoiceSynth().speak("hello")

    create_response = client.post(
        "/face/jobs", files={"audio": ("reply.wav", wav_bytes, "audio/wav")}
    )
    assert create_response.status_code == 200
    body = create_response.json()
    job_id = body["job_id"]
    assert body["status"] == "queued"
    assert body["mp4_url"] is None

    # TestClient runs the BackgroundTask synchronously as part of the POST's ASGI cycle, so
    # by the time we GET, rendering (against the fake renderer) has already finished.
    get_response = client.get(f"/face/jobs/{job_id}")
    assert get_response.status_code == 200
    done_body = get_response.json()
    assert done_body["status"] == "done"
    assert done_body["mp4_url"] == f"/face/jobs/{job_id}/video"
    assert len(fake_face_renderer.calls) == 1

    video_response = client.get(f"/face/jobs/{job_id}/video")
    assert video_response.status_code == 200
    assert b"ftyp" in video_response.content


@pytest.mark.db
def test_create_job_with_text_uses_voice_synth(
    client: TestClient, fake_voice_synth: FakeVoiceSynth, fake_face_renderer: FakeFaceRenderer
):
    response = client.post("/face/jobs", data={"text": "hello there"})
    assert response.status_code == 200

    assert len(fake_voice_synth.calls) == 1
    assert fake_voice_synth.calls[0]["text"] == "hello there"
    assert len(fake_face_renderer.calls) == 1


@pytest.mark.db
def test_get_unknown_job_returns_404(client: TestClient):
    response = client.get("/face/jobs/does-not-exist")
    assert response.status_code == 404


@pytest.mark.db
def test_video_not_ready_returns_409(client: TestClient, monkeypatch):
    """If a job is still queued/running, the video endpoint must not 200 with garbage."""
    from app.face import api as face_api

    # Create a job but don't let it run (patch run_job to a no-op for this one job).
    # Patched on app.face.api, not app.face.jobs: the route imported run_job by name, so
    # that's the reference `background_tasks.add_task` actually calls.
    monkeypatch.setattr(face_api, "run_job", lambda *_a, **_k: None)
    response = client.post(
        "/face/jobs", files={"audio": ("reply.wav", b"RIFF....WAVEfmt ", "audio/wav")}
    )
    job_id = response.json()["job_id"]

    video_response = client.get(f"/face/jobs/{job_id}/video")
    assert video_response.status_code == 409
