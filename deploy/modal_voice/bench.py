"""Bench the deployed Modal voice endpoint: cold start, then 3 sentences (RTF + time-to-audio).

Run this AFTER `modal deploy deploy/modal_voice/app.py` (see
docs/notes/modal-voice-setup.md). It's a plain script (not a pytest test) because it hits a
real, billed endpoint - the Owner runs it by hand, not CI.

Usage:
    MODAL_VOICE_URL=https://<workspace>--keepsake-voice-speak.modal.run \
    MODAL_VOICE_TOKEN=<the shared secret> \
    python deploy/modal_voice/bench.py [path/to/reference.wav]

If a reference WAV path is given, it's sent with every request so the bench measures the
actual cloned-voice path, not the model's default voice. Prints a table of wall time,
audio duration and RTF (wall time / audio duration - under 1.0 means faster than real time)
for a cold first sentence and two warm follow-ups, plus time-to-first-byte for each.
"""

from __future__ import annotations

import base64
import io
import os
import struct
import sys
import time

import httpx

SENTENCES = [
    "Hello, this is a test of the Modal voice endpoint.",
    "The quick brown fox jumps over the lazy dog near the riverbank.",
    "Keepsake keeps a personal memory archive so the clone can speak from real events.",
]


def _wav_duration_seconds(wav_bytes: bytes) -> float:
    """Read the duration from a WAV file's fmt/data chunks without extra dependencies."""
    buf = io.BytesIO(wav_bytes)
    if buf.read(4) != b"RIFF":
        return float("nan")
    buf.read(4)  # chunk size
    if buf.read(4) != b"WAVE":
        return float("nan")

    channels = sample_rate = bits_per_sample = None
    data_size = None
    while True:
        header = buf.read(8)
        if len(header) < 8:
            break
        chunk_id, chunk_size = struct.unpack("<4sI", header)
        if chunk_id == b"fmt ":
            fmt = buf.read(chunk_size)
            _, channels, sample_rate, _, _, bits_per_sample = struct.unpack("<HHIIHH", fmt[:16])
        elif chunk_id == b"data":
            data_size = chunk_size
            buf.seek(chunk_size, 1)
        else:
            buf.seek(chunk_size, 1)
    if not (channels and sample_rate and bits_per_sample and data_size):
        return float("nan")
    bytes_per_frame = channels * (bits_per_sample // 8)
    return data_size / bytes_per_frame / sample_rate


def main() -> None:
    url = os.environ.get("MODAL_VOICE_URL", "")
    token = os.environ.get("MODAL_VOICE_TOKEN", "")
    if not url or not token:
        print("Set MODAL_VOICE_URL and MODAL_VOICE_TOKEN first.", file=sys.stderr)
        sys.exit(1)

    reference_wav_b64 = None
    if len(sys.argv) > 1:
        with open(sys.argv[1], "rb") as f:
            reference_wav_b64 = base64.b64encode(f.read()).decode("ascii")

    headers = {"Authorization": f"Bearer {token}"}
    rows: list[tuple[str, float, float, float]] = []

    with httpx.Client(timeout=120.0) as client:
        for i, sentence in enumerate(SENTENCES):
            label = "cold start (1st sentence)" if i == 0 else f"warm (sentence {i + 1})"
            payload: dict[str, str] = {"text": sentence}
            if reference_wav_b64:
                payload["reference_wav_b64"] = reference_wav_b64

            start = time.monotonic()
            response = client.post(url, json=payload, headers=headers)
            elapsed = time.monotonic() - start

            if response.status_code != 200:
                print(f"[{label}] FAILED: {response.status_code} {response.text[:300]}")
                continue

            duration = _wav_duration_seconds(response.content)
            rtf = elapsed / duration if duration and duration > 0 else float("nan")
            rows.append((label, elapsed, duration, rtf))

    print(f"\n{'label':<28} {'wall (s)':>10} {'audio (s)':>10} {'RTF':>8}")
    print("-" * 60)
    for label, elapsed, duration, rtf in rows:
        print(f"{label:<28} {elapsed:>10.2f} {duration:>10.2f} {rtf:>8.2f}")
    print()
    if rows:
        warm = [r for r in rows[1:]]
        if warm:
            avg_rtf = sum(r[3] for r in warm) / len(warm)
            verdict = "FASTER than real time" if avg_rtf < 1.0 else "SLOWER than real time"
            print(f"Average warm RTF: {avg_rtf:.2f} ({verdict})")


if __name__ == "__main__":
    main()
