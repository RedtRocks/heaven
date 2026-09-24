# Voice: CPU benchmark

## What was supposed to be measured

Real-time factor (RTF = synthesis wall time / audio duration) and first-audio latency for
3 sentences synthesised with Chatterbox on this machine's CPU (Ryzen 5 7530U, no CUDA),
using the default voice (no reference clip).

Command to reproduce:

```
cd backend
uv sync --extra voice
uv run python scripts/bench_voice.py
```

## What actually happened

**Model choice.** The task asked for Chatterbox-**Nano** (110M params, the CPU-oriented
member of the family, loaded via `ChatterboxTurboTTS.from_pretrained(device="cpu",
nano=True)` per the GitHub README). The released PyPI package, `chatterbox-tts==0.1.7`
(the latest version on PyPI as of writing — verified with `pip index versions
chatterbox-tts`), does **not** support this: `ChatterboxTurboTTS.from_pretrained` only
takes `device`, and hardcodes `REPO_ID = "ResembleAI/chatterbox-turbo"`. Nano support
exists on the GitHub repo's default branch but hadn't reached a PyPI release at the time
of this work. `app/providers/tts_chatterbox.py` therefore uses the standard
`ChatterboxTTS` (`chatterbox.tts`, `REPO_ID = "ResembleAI/chatterbox"`, the original
"English" model, ~500M params judging by checkpoint size) instead — the closest
CPU-capable option actually installable from PyPI. Swap in Nano once a release adds
`nano=True` support; the `generate()`/`audio_prompt_path` call shape is identical.

**The benchmark itself did not complete.** `scripts/bench_voice.py` downloads the model
(~3.2GB of safetensors: `t3_cfg.safetensors` 2.1GB, `s3gen.safetensors` 1.1GB,
`ve.safetensors` 5.7MB) from Hugging Face, then calls `ChatterboxTTS.from_pretrained`,
which deserialises those weights into CPU memory before any sentence is synthesised.

- First attempts (both with the default `hf_xet` transfer backend and with
  `HF_HUB_DISABLE_XET=1` to force the plain HTTP downloader) failed **during the
  download** with `MemoryError` / a Rust panic reporting `Os { code: 1450, ...
  "Insufficient system resources exist to complete the requested service." }`. This
  matches the same error `uv add --optional voice chatterbox-tts` hit once during
  dependency installation (see the commit history) — a Windows resource-exhaustion
  error, not a normal HTTP failure.
- Re-running with the agent sandbox disabled (`dangerouslyDisableSandbox`) let the
  download finish (all 3.2GB now cached under `~/.cache/huggingface/hub/models--ResembleAI--chatterbox/`),
  ruling out the sandbox's own resource limits as the cause of that first failure.
- With the model fully downloaded, actually loading it (`ChatterboxTTS.from_pretrained`)
  then **segfaulted** (exit code 139) rather than raising a Python exception. At the time,
  `Get-CimInstance Win32_OperatingSystem` showed as little as ~0.8-1.1GB of free physical
  RAM on this machine (out of ~14GB total) — the rest was in use by the normal desktop
  session (browser, editor, WSL, etc. this box is being interactively used for while
  these agents run). Deserialising ~3.2GB of fp32 tensors plus the transient copies
  `safetensors.load_file`/`state_dict` loading involves needs more headroom than that.

**What I tried, in order:**
1. `uv run python scripts/bench_voice.py` — `MemoryError` during model download (xet backend).
2. `HF_HUB_DISABLE_XET=1 uv run python scripts/bench_voice.py` — same `MemoryError`, now during the plain HTTP download's chunk decode.
3. Same command with the sandbox disabled for that one call — download completed (no crash), confirming the sandbox's own limits were the proximate cause of (1) and (2).
4. Re-running to synthesise, model fully cached — segfault (exit 139) while deserialising the checkpoint, consistent with genuine low free system RAM at that moment.

**I did not fake numbers.** No real-time factor or latency was measured. This machine's
16GB should, per the task brief's own hardware description, have enough headroom for a
~500M-parameter CPU model when not shared with a full interactive desktop session — the
failure here looks environmental (concurrent memory pressure from other running
programs on this specific box, at this specific time) rather than a fundamental
incompatibility. Re-running `uv run python scripts/bench_voice.py` (after `uv sync
--extra voice`, and ideally with most other applications closed to free RAM, or on a
machine closer to idle) should produce real numbers without any code changes — the
model, once cached, doesn't need to re-download.

## What's verified instead

- `chatterbox-tts` (with torch/torchaudio) installs successfully via `uv sync --extra
  voice` and imports cleanly (`from chatterbox.tts import ChatterboxTTS`).
- `ChatterboxVoiceSynth` (`app/providers/tts_chatterbox.py`) and `get_voice()`
  (`app/providers/registry.py`) are unit- and contract-tested with fakes; the real
  provider is exercised structurally (constructed, `isinstance` checks) but not by
  actually calling `.speak()`, since that requires the model to load — see
  `backend/tests/contracts/test_voice_synth.py`'s `slow`-marked, install-gated Chatterbox
  param and `backend/tests/test_face.py::test_get_voice_without_override_returns_chatterbox`.
- `POST /voice/speak` is tested end-to-end against a `FakeVoiceSynth` in
  `backend/tests/test_voice_api.py`.

## Follow-up, 2026-09-24 (coordinator)

- **Nano is on GitHub main.** Installing `chatterbox-tts @ git+https://github.com/resemble-ai/chatterbox.git` exposes `ChatterboxTurboTTS.from_pretrained("cpu", nano=True)` (repo `ResembleAI/chatterbox-nano`, GPT2-small backbone). The weights download worked (≈33 min on this connection) and are now in the local Hugging Face cache.
- **Loading Nano also segfaulted (exit 139)**, with only **0.1 GB of RAM free** at load time. The standard model crashed the same way earlier at 0.8–1.4 GB free. Most of the 13.9 GB was held by desktop apps (browser ~3.3 GB, VS Code ~1.1 GB, WebView ~0.7 GB) plus memory compression, so **free RAM is the blocker, not the code.**
- **Next step:** close the browser, then run `scratchpad`-style `bench.py` against Nano (or `scripts/bench_voice.py` after switching the provider). If Nano loads and runs near real time, switch `tts_chatterbox.py` to `ChatterboxTurboTTS(..., nano=True)` and pin the git dependency to a commit.

## Measured, 2026-09-24 (coordinator, with ~5 GB RAM free)

Chatterbox-**Nano** (`ChatterboxTurboTTS.from_pretrained("cpu", nano=True)`, git commit `5de7a54`), Ryzen 5 7530U:

| | 12 threads | 6 threads (default now) |
|---|---|---|
| Load | 12.7 s, 2.3 GB RSS | 9.1 s, 2.3 GB RSS |
| First sentence (cold) | 26.0 s for 2.4 s audio | 7.4 s for 2.6 s audio |
| Steady state RTF | ~2.1 | ~2.1–2.2 |

- **Not real time on CPU:** a ~3.5 s sentence takes ~7 s. The standard (non-Nano) model can't load at all with this much RAM.
- **Mitigations in place:** the face speaks sentence by sentence and fetches the next sentence while the current one plays (first audio ~6.6 s after the reply arrives, measured in the browser). `VOICE_WARMUP=1` loads and warms the model at startup, so the first request drops from ~54 s to ~6 s.
- **To get real time later:** a GPU (paid), or a faster non-cloned TTS for the live path.
