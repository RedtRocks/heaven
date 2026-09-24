# Setting up fast cloned voice on Modal

The Clone must always speak in the Owner's cloned voice (ADR 0003), but Chatterbox on the
Owner's CPU runs at ~2.1x real time (docs/notes/voice.md) — too slow to feel live. This
wires the same Chatterbox model to a Modal GPU, which is fast and, at Keepsake's traffic,
free under Modal's $30/month credit. See `docs/notes/voice-gpu.md` for why Modal was chosen
over Colab/Kaggle/HF ZeroGPU, and `deploy/modal_voice/app.py` for why Turbo (not Nano) and
a T4 (not a bigger GPU) were chosen.

This is a manual, one-time setup only the Owner can do (it needs their own Modal account
and billing). Nothing here runs automatically or in CI.

## 1. Create a Modal account and CLI token

1. Sign up at <https://modal.com> (GitHub login is fine).
2. Install the CLI and authenticate:
   ```
   pip install modal
   modal token new
   ```
   This opens a browser to link the CLI to your account and writes a token to
   `~/.modal.toml`.
3. Check the current free-tier terms and GPU pricing at
   <https://modal.com/pricing> — this doc's cost estimate below was accurate as of
   2026-09-24 but Modal can change rates.

## 2. Create the shared-secret Modal Secret

The deployed endpoint checks an `Authorization: Bearer <token>` header against a Modal
Secret so a leaked URL alone isn't enough to use your GPU minutes.

1. Pick a long random token, e.g.:
   ```
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
2. Create the secret (name must match `SECRET_NAME` in `deploy/modal_voice/app.py`,
   currently `keepsake-voice-secret`):
   ```
   modal secret create keepsake-voice-secret VOICE_SHARED_SECRET=<the token you generated>
   ```
   You can also do this from the Modal dashboard under Secrets.
3. Keep that token — you'll put it in `backend/.env` as `MODAL_VOICE_TOKEN` in step 4.

## 3. Deploy

From the repo root:

```
pip install modal fastapi
modal deploy deploy/modal_voice/app.py
```

The first deploy builds the image (installs Chatterbox + torch on Modal's build
infrastructure, not your machine) and prints a URL that looks like:

```
https://<your-workspace>--keepsake-voice-speak.modal.run
```

That's `MODAL_VOICE_URL`. The first real request after deploy triggers a cold start that
downloads Chatterbox-Turbo's weights (~2 GB) into the persistent Modal Volume
(`keepsake-voice-weights`) — slow once, cached for every request after (on any container,
since the Volume is shared).

Redeploying (after editing `app.py`) reuses the same app name and URL.

## 4. Point the backend at it

In `backend/.env` (copy from `.env.example` if you haven't):

```
VOICE_PROVIDER=modal
MODAL_VOICE_URL=https://<your-workspace>--keepsake-voice-speak.modal.run
MODAL_VOICE_TOKEN=<the token from step 2>
```

Leave `VOICE_PROVIDER=local` (the default) to keep using CPU-only Chatterbox-Nano — for
example while developing without spending Modal credit. With `VOICE_PROVIDER=modal`, any
Modal failure (network error, timeout, non-2xx) automatically falls back to local
Chatterbox-Nano and logs a warning — see `ModalVoiceSynth`/`FallbackVoiceSynth` in
`backend/app/providers/tts_modal.py`.

## 5. Run the bench

```
MODAL_VOICE_URL=https://<your-workspace>--keepsake-voice-speak.modal.run \
MODAL_VOICE_TOKEN=<the token> \
python deploy/modal_voice/bench.py likeness/voice/reference.wav
```

(Omit the WAV path to bench the model's default voice instead of the Owner's clone.) It
prints wall time, audio duration and RTF for a cold first sentence and two warm ones. RTF
under 1.0 on the warm sentences means the GPU path is faster than real time — see
`docs/notes/voice-gpu.md` for the streaming follow-up if it isn't quite there yet.

## Cost estimate against the $30/month credit

Modal's per-second GPU billing (checked 2026-09-24, verify current rates at
<https://modal.com/pricing> before relying on this):

| GPU | ~$/hour | Hours in $30 credit |
|---|---|---|
| T4 (this deploy) | ~$0.59/hr | ~50 hours/month |
| L4 (fallback tier if T4 is too slow) | ~$0.80/hr | ~37 hours/month |

With `scaledown_window=60` (deploy/modal_voice/app.py), the container only bills while
warm — idle time between conversations costs nothing. A Visitor conversation with, say, 20
spoken sentences at ~2–4 s of GPU time each is roughly a minute of billed GPU time; even a
generous 2 hours/day of actual speaking time would use ~60 GPU-hours/month, which is over
budget on T4 alone. In practice conversations are bursty (most of the 60 s scaledown
window per burst is idle-but-billed, not generating audio), so real usage is likely well
under that — the bench script's cold-start number matters here too, since frequent cold
starts (many short, spaced-out conversations) cost more GPU-seconds per sentence than a
few long warm conversations. Watch actual spend in the Modal dashboard for the first
month and lower `scaledown_window` (bills less idle time, more cold starts) or move to a
paid Modal plan if the free credit isn't enough.

## Troubleshooting

- **401 from the endpoint**: `MODAL_VOICE_TOKEN` doesn't match the Modal Secret's
  `VOICE_SHARED_SECRET`. Re-check step 2, or `modal secret list` / dashboard to confirm the
  secret's value.
- **Deploy fails to build the image**: usually a pip install failure in
  `deploy/modal_voice/app.py`'s `image` — check the pinned Chatterbox git commit still
  resolves (`CHATTERBOX_GIT_REV`) and that PyTorch's CUDA wheel is compatible with the
  image's Python version.
- **Cold start much slower than expected**: check the Modal dashboard's container logs —
  if it's re-downloading weights every time, the Volume isn't being reused (confirm the
  Volume name in `app.py` matches what's mounted, and that `weights_volume.commit()` ran).
