"""Measure Chatterbox-Nano's CPU real-time factor and first-audio latency.

Synthesises 3 sentences with the default voice (no reference clip) on CPU and prints:
- model load time
- per-sentence: wall time, audio duration, real-time factor (wall / audio), and
  first-audio latency (time from calling generate() to getting audio back)

Run with: `uv run python scripts/bench_voice.py` (needs the `voice` extra installed:
`uv sync --extra voice`).
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SENTENCES = [
    "Hi there, it's good to hear your voice today.",
    "I've been meaning to tell you about the trip we took last summer, the one where "
    "everything that could go wrong somehow turned into the best story we tell at dinner "
    "parties now.",
    "Anyway, that's enough from me for now, talk soon.",
]


def main() -> None:
    from app.providers.tts_chatterbox import ChatterboxVoiceSynth

    synth = ChatterboxVoiceSynth(Path("does-not-exist.wav"))  # no reference clip: default voice

    load_start = time.perf_counter()
    synth._model_instance()  # force the lazy load now so it's not counted in per-sentence timing
    load_seconds = time.perf_counter() - load_start
    print(f"Model load time: {load_seconds:.2f}s")

    for i, text in enumerate(SENTENCES, start=1):
        start = time.perf_counter()
        wav_bytes = synth.speak(text)
        elapsed = time.perf_counter() - start

        import io
        import wave

        with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            audio_seconds = frames / float(rate)

        rtf = elapsed / audio_seconds if audio_seconds else float("inf")
        print(
            f"Sentence {i} ({len(text)} chars): wall={elapsed:.2f}s audio={audio_seconds:.2f}s "
            f"real-time-factor={rtf:.2f}x"
        )


if __name__ == "__main__":
    main()
