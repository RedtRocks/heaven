"""Voice clone via Resemble AI's Chatterbox (MIT, https://github.com/resemble-ai/chatterbox).

Uses Chatterbox-Nano (110M params), the CPU-oriented member of the Chatterbox family
(Turbo/Nano share the ChatterboxTurboTTS class; Nano is selected with nano=True). Vendor
imports (chatterbox, torch, torchaudio) happen only inside methods, so this module — and
`get_voice()` — can be imported even when the optional `voice` dependency group isn't
installed; only actually synthesising speech requires it.
"""

import io
from pathlib import Path


class ChatterboxVoiceSynth:
    """Speaks text in the Owner's cloned voice using Chatterbox-Nano, on CPU.

    The model (~110M params) is loaded lazily on first `speak()` call, once, and kept
    for the life of this instance — loading it takes several seconds.
    """

    def __init__(self, reference_wav_path: Path):
        self._reference_wav_path = reference_wav_path
        self._model = None

    def _model_instance(self):
        if self._model is None:
            from chatterbox.tts_turbo import ChatterboxTurboTTS

            self._model = ChatterboxTurboTTS.from_pretrained(device="cpu", nano=True)
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
