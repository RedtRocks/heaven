"""Voice clone via Resemble AI's Chatterbox-Nano (MIT, https://github.com/resemble-ai/chatterbox).

Nano (GPT2-small backbone) is the CPU-oriented member of the family. It is only on the
GitHub branch, not in the PyPI release, so pyproject pins a git commit. Measured on the
Owner's Ryzen 5 7530U (docs/notes/voice.md): loads in ~9 s using ~2.5 GB RAM, and
synthesises at ~2.1x real time (a 3.4 s sentence takes ~7 s) with 6 threads.

Vendor imports (chatterbox, torch, torchaudio) happen only inside methods, so this
module, and `get_voice()`, can be imported without the optional `voice` extra.
"""

import io
import os
from pathlib import Path

# Physical cores beat logical ones for this workload (measured: 6 threads cold-starts in
# 7 s vs 26 s with 12).
_THREADS = int(os.environ.get("VOICE_THREADS", "6"))


class ChatterboxVoiceSynth:
    """Speaks text in the Owner's cloned voice on CPU. The model loads once, on first use."""

    def __init__(self, reference_wav_path: Path):
        self._reference_wav_path = reference_wav_path
        self._model = None

    def _model_instance(self):
        if self._model is None:
            import torch
            from chatterbox.tts_turbo import ChatterboxTurboTTS

            torch.set_num_threads(_THREADS)
            self._model = ChatterboxTurboTTS.from_pretrained("cpu", nano=True)
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
