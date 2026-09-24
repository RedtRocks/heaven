"""Voice clone via Resemble AI's Chatterbox (MIT, https://github.com/resemble-ai/chatterbox).

Chatterbox-Nano (110M params) is the CPU-oriented member of the family the task asked
for, loaded via `ChatterboxTurboTTS.from_pretrained(device="cpu", nano=True)` per the
GitHub README. In practice, the released PyPI package (`chatterbox-tts==0.1.7`, the
latest available at the time this was written) does NOT support `nano=True` yet:
`ChatterboxTurboTTS.from_pretrained` takes only `device`, and hardcodes
`REPO_ID = "ResembleAI/chatterbox-turbo"` — Nano support is on GitHub's default branch
but not released to PyPI. So this uses the standard `ChatterboxTTS` (`chatterbox.tts`,
the original "English" model, `REPO_ID = "ResembleAI/chatterbox"`), which the README
also describes as CPU-capable and is the closest real option installable from PyPI.
Swap in Nano here once a release adds it — `generate()`/`audio_prompt_path` is the same
API either way.

Vendor imports (chatterbox, torch, torchaudio) happen only inside methods, so this
module — and `get_voice()` — can be imported even when the optional `voice` dependency
group isn't installed; only actually synthesising speech requires it.
"""

import io
from pathlib import Path


class ChatterboxVoiceSynth:
    """Speaks text in the Owner's cloned voice using Chatterbox, on CPU.

    The model is loaded lazily on first `speak()` call, once, and kept for the life of
    this instance — loading it takes several seconds.
    """

    def __init__(self, reference_wav_path: Path):
        self._reference_wav_path = reference_wav_path
        self._model = None

    def _model_instance(self):
        if self._model is None:
            from chatterbox.tts import ChatterboxTTS

            self._model = ChatterboxTTS.from_pretrained(device="cpu")
        return self._model

    def speak(self, text: str) -> bytes:
        import torchaudio as ta

        model = self._model_instance()
        kwargs = {}
        if self._reference_wav_path.exists():
            kwargs["audio_prompt_path"] = str(self._reference_wav_path)
        wav = model.generate(text, **kwargs)
        buffer = io.BytesIO()
        ta.save(buffer, wav, model.sr, format="wav")
        return buffer.getvalue()
