"""Capture the Owner's voice reference clip for Chatterbox voice cloning.

Two modes:

    uv run python scripts/record_reference.py record
        Displays a passage to read aloud, records ~30s from the default
        microphone, and saves it to `settings.likeness_dir / "voice" / "reference.wav"`.

    uv run python scripts/record_reference.py convert path/to/clip.mp3
        Converts an existing audio file (any format soundfile/ffmpeg can read)
        into the same reference path, resampled to mono 24kHz.

Requires the optional `voice` dependency group: `uv sync --extra voice`.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402

RECORD_SECONDS = 30
SAMPLE_RATE = 24_000

PASSAGE = """\
Please read the following out loud, at a natural pace, in a quiet room:

The quick brown fox jumps over the lazy dog near the riverbank at sunset.
I've been meaning to tell you about the trip we took last summer, the one
where everything that could go wrong somehow turned into the best story we
tell at dinner parties now. It's funny how memory works that way. Some days
I can't remember what I had for breakfast, but I remember the exact smell
of the rain that afternoon. Anyway, that's the kind of thing I'd like my
voice to carry when it tells you about the rest.
"""


def reference_path() -> Path:
    path = get_settings().likeness_dir / "voice" / "reference.wav"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def record() -> None:
    import sounddevice as sd
    import soundfile as sf

    print(PASSAGE)
    input(f"Press Enter to start recording ({RECORD_SECONDS}s)...")
    print("Recording...")
    audio = sd.rec(int(RECORD_SECONDS * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="float32")
    sd.wait()
    print("Done recording.")

    out_path = reference_path()
    sf.write(out_path, audio, SAMPLE_RATE, subtype="PCM_16")
    print(f"Saved reference clip to {out_path}")


def convert(source: str) -> None:
    import soundfile as sf
    from scipy.signal import resample

    data, sample_rate = sf.read(source, always_2d=True)
    mono = data.mean(axis=1)
    if sample_rate != SAMPLE_RATE:
        num_samples = int(len(mono) * SAMPLE_RATE / sample_rate)
        mono = resample(mono, num_samples)

    out_path = reference_path()
    sf.write(out_path, mono, SAMPLE_RATE, subtype="PCM_16")
    print(f"Saved reference clip to {out_path}")


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in {"record", "convert"}:
        print(__doc__)
        sys.exit(1)

    if sys.argv[1] == "record":
        record()
    else:
        if len(sys.argv) < 3:
            print("Usage: record_reference.py convert <path/to/audio/file>")
            sys.exit(1)
        convert(sys.argv[2])


if __name__ == "__main__":
    main()
