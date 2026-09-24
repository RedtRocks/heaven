"""Modal app: Chatterbox voice cloning on a GPU, behind a shared-secret HTTP endpoint.

Why this exists: the Clone must speak in the Owner's cloned voice, never a stock voice
(docs/adr/0003-clone-speaks-only-in-cloned-voice.md). On the Owner's CPU, Chatterbox-Nano
runs at ~2.1x real time (docs/notes/voice.md) - too slow to feel live. Modal gives $30/month
of free credit and scales to zero, so a small GPU can make cloned-voice synthesis fast at
no ongoing cost for Keepsake's traffic (docs/notes/voice-gpu.md).

Model choice: Chatterbox **Turbo** (`ChatterboxTurboTTS.from_pretrained(device, nano=False)`),
not Nano, and that's a deliberate trade against the CPU path:
  - Nano (GPT2-small backbone) exists specifically to make CPU inference survivable on
    limited RAM. On a GPU that constraint disappears - the GPU has the memory and compute
    Nano was built to avoid needing - so there's no reason to keep taking Nano's quality cut.
  - Turbo is the model the maintainers ship as the quality-focused default (the repo's own
    `from_pretrained` defaults to `nano=False`), and Turbo is also the one the reference
    RTF numbers in docs/notes/voice-gpu.md (the davidbrowne17 streaming fork) are quoted
    against.
  - A T4 has 16 GB VRAM; Turbo's checkpoint (~2.2 GB of fp16/fp32 weights) fits with room
    to spare, so there's no memory pressure pushing back toward Nano the way there was on
    the Owner's 14 GB shared-with-a-desktop CPU box.
  - If a future bench (see bench.py) shows Turbo doesn't clear 1x RTF on a T4, the fallback
    is to try Nano on the same GPU (should be faster, at Nano's lower quality) before
    reaching for a bigger GPU tier.

GPU choice: T4 (cheapest Modal GPU tier, ~$0.59/hr as of writing - see
docs/notes/modal-voice-setup.md for the up to date rate and a cost estimate against the
$30 credit). L4 is the fallback tier to try if T4 turns out too slow (bench.py's job) -
about 2x the hourly cost but meaningfully faster.

Scale-to-zero: `scaledown_window=60` (Modal's own default) - keeps containers around 60s
after the last request so a burst of sentences (this app synthesises sentence-by-sentence,
see docs/notes/voice.md) reuses one warm container, then shuts down. There is a real cold
start (model load onto GPU) on the first request after idling; bench.py measures it.

Auth: a Modal Secret (`keepsake-voice-secret`, containing `VOICE_SHARED_SECRET`) holds a
bearer token compared against the incoming `Authorization: Bearer <token>` header. Anyone
with the URL but not the token gets 401. This is the same shape as any other Keepsake
provider token (see app/config.py) - a shared secret, not real auth, because there is one
Owner and no user accounts here.

Streaming: not implemented. The maintained fork with true token-streaming
(davidbrowne17/chatterbox-streaming, see docs/notes/voice-gpu.md) is a different package
from the pinned `resemble-ai/chatterbox` this repo already depends on for the local
fallback, and wiring two different Chatterbox forks (one per provider) is more complexity
than this endpoint needs before we know whether plain per-sentence synthesis on a GPU
already clears 1x RTF. Follow-up: if bench.py shows Turbo-on-T4 is still not fast enough
for the live feel ADR 0003 wants, swap this image to chatterbox-streaming and add a
streaming endpoint variant (Modal supports HTTP streaming responses from a
`@modal.fastapi_endpoint`).

Deploy: `modal deploy deploy/modal_voice/app.py` from this repo (see
docs/notes/modal-voice-setup.md for the full first-time setup). Redeploying updates the
same app/endpoint URL.
"""

import base64
import io
import os

import modal
from fastapi import Header

APP_NAME = "keepsake-voice"
MODEL_VOLUME_NAME = "keepsake-voice-weights"
SECRET_NAME = "keepsake-voice-secret"

# Pin to the same commit backend/pyproject.toml uses for the local fallback, so both
# providers are running the same Chatterbox code even though local uses Nano and this uses
# Turbo.
CHATTERBOX_GIT_REV = "5de7a54aa4e5e2baadb0182dde554908b48b85c2"

app = modal.App(APP_NAME)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "ffmpeg")
    .pip_install(
        f"chatterbox-tts @ git+https://github.com/resemble-ai/chatterbox.git@{CHATTERBOX_GIT_REV}",
        "torch",
        "torchaudio",
        "fastapi[standard]",
    )
)

# Persists downloaded Hugging Face weights across deploys/cold starts, so only the first
# request ever pays for the ~2GB download.
weights_volume = modal.Volume.from_name(MODEL_VOLUME_NAME, create_if_missing=True)

secret = modal.Secret.from_name(SECRET_NAME)


@app.cls(
    gpu="T4",
    image=image,
    volumes={"/root/.cache/huggingface": weights_volume},
    secrets=[secret],
    scaledown_window=60,
    timeout=120,
)
class ChatterboxVoice:
    @modal.enter()
    def load_model(self):
        from chatterbox.tts_turbo import ChatterboxTurboTTS

        self.model = ChatterboxTurboTTS.from_pretrained("cuda", nano=False)
        # Make sure the download this cold start may have triggered is persisted for the
        # next container, not just held in this one's ephemeral disk.
        weights_volume.commit()

    def _synthesize(self, text: str, reference_wav_b64: str | None) -> bytes:
        import tempfile
        from pathlib import Path

        import torchaudio as ta

        kwargs = {}
        tmp_ref_path: Path | None = None
        if reference_wav_b64:
            tmp_ref_path = Path(tempfile.mkstemp(suffix=".wav")[1])
            tmp_ref_path.write_bytes(base64.b64decode(reference_wav_b64))
            kwargs["audio_prompt_path"] = str(tmp_ref_path)

        try:
            wav = self.model.generate(text, **kwargs)
        finally:
            if tmp_ref_path is not None:
                tmp_ref_path.unlink(missing_ok=True)

        buffer = io.BytesIO()
        ta.save(buffer, wav, self.model.sr, format="wav")
        return buffer.getvalue()

    @modal.fastapi_endpoint(method="POST")
    def speak(self, item: dict, authorization: str = Header(default="")):
        from fastapi import HTTPException
        from fastapi.responses import Response

        # `modal.fastapi_endpoint` methods are plain FastAPI route handlers, so headers are
        # read via FastAPI's own `Header(...)` dependency injection.
        expected = os.environ.get("VOICE_SHARED_SECRET", "")
        token = authorization.removeprefix("Bearer ").strip()
        if not expected or token != expected:
            raise HTTPException(status_code=401, detail="invalid or missing token")

        text = item.get("text", "")
        if not isinstance(text, str) or not text.strip():
            raise HTTPException(status_code=400, detail="'text' is required")

        reference_wav_b64 = item.get("reference_wav_b64")
        audio_bytes = self._synthesize(text, reference_wav_b64)
        return Response(content=audio_bytes, media_type="audio/wav")
