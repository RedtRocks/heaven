from tests.fakes import FakeVoiceSynth


def test_speak_returns_wav_audio(client: object) -> None:
    resp = client.post("/voice/speak", json={"text": "Hello there"})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/wav"
    assert resp.content.startswith(b"RIFF")


def test_speak_calls_the_voice_provider(client: object, fake_voice_synth: FakeVoiceSynth) -> None:
    client.post("/voice/speak", json={"text": "Hello there"})
    assert fake_voice_synth.calls == [{"text": "Hello there"}]
