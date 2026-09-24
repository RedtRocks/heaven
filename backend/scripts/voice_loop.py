"""Live push-to-talk voice loop: talk to the Clone, out loud, in the Owner's cloned voice.

Loop: press Enter to talk -> record from the mic -> press Enter to stop -> speech-to-text
(Groq Whisper via get_stt()) -> LLM (get_llm()) with the Clone system prompt -> voice clone
(get_voice(), Chatterbox) -> play back through the speakers. Ctrl+C to quit.

Requires the optional `voice` dependency group for playback/recording and for Chatterbox
itself: `uv sync --extra voice`. Also needs GROQ_API_KEY and an LLM provider configured
in `.env` (see `.env.example`).

Follow-up (not done here): rebuild this on Pipecat (https://github.com/pipecat-ai/pipecat)
for a real-time, interrupt-capable pipeline instead of push-to-talk turns. A first pass at
wiring Pipecat's local audio transport around get_stt/get_llm/get_voice took more than a
reasonable effort to get right for this task's time budget (Pipecat wants async
FrameProcessors with its own turn-taking/VAD state machine, which doesn't map cleanly onto
our synchronous provider Protocols without a real adapter layer) so this push-to-talk loop
ships first, per task-voice.md's fallback instruction.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import Session  # noqa: E402

from app.conversation.contracts import MemoryRecall  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.persona.prompt import build_clone_system_prompt  # noqa: E402
from app.persona.recall import get_memory_recall  # noqa: E402
from app.providers import LLM, ChatMessage, SpeechToText, VoiceSynth  # noqa: E402
from app.providers.registry import get_llm, get_stt, get_voice  # noqa: E402

SAMPLE_RATE = 16_000


def run_turn(
    audio: bytes,
    *,
    llm: LLM,
    stt: SpeechToText,
    voice: VoiceSynth,
    recall: MemoryRecall,
    session: Session,
    history: list[ChatMessage],
) -> tuple[str, str, bytes]:
    """One push-to-talk turn: transcribe, build the Clone prompt, reply, speak it.

    Pure w.r.t. hardware (no mic/speaker access) so it can be unit-tested with fake
    providers. Mutates `history` in place (appends the user turn and the reply).
    Returns (heard_text, reply_text, reply_wav_bytes).
    """
    heard = stt.transcribe(audio, filename="turn.wav")
    recalled = recall.recall(heard, visitor_id=None)
    system = build_clone_system_prompt(session, None, recalled)

    history.append(ChatMessage("user", heard))
    reply = llm.complete(list(history), system=system)  # copy: history keeps changing after this call
    history.append(ChatMessage("assistant", reply))

    wav_bytes = voice.speak(reply)
    return heard, reply, wav_bytes


def _record_until_enter() -> bytes:
    """Record from the mic until Enter is pressed again; return WAV bytes."""
    import queue

    import sounddevice as sd
    import soundfile as sf
    import numpy as np

    chunks: queue.Queue = queue.Queue()

    def callback(indata, frames, time, status):  # noqa: ANN001, ARG001
        chunks.put(indata.copy())

    print("Recording... press Enter to stop.")
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", callback=callback):
        input()

    frames = []
    while not chunks.empty():
        frames.append(chunks.get())
    audio = np.concatenate(frames, axis=0) if frames else np.zeros((0, 1), dtype="float32")

    import io

    buffer = io.BytesIO()
    sf.write(buffer, audio, SAMPLE_RATE, format="WAV", subtype="PCM_16")
    return buffer.getvalue()


def _play(wav_bytes: bytes) -> None:
    import io

    import sounddevice as sd
    import soundfile as sf

    data, sample_rate = sf.read(io.BytesIO(wav_bytes))
    sd.play(data, sample_rate)
    sd.wait()


def main() -> None:
    llm = get_llm()
    stt = get_stt()
    voice = get_voice()

    history: list[ChatMessage] = []
    print("Voice loop ready. Press Enter to talk, Ctrl+C to quit.")
    while True:
        try:
            input("\nPress Enter to talk...")
        except (KeyboardInterrupt, EOFError):
            print("\nBye.")
            return

        audio = _record_until_enter()
        with SessionLocal() as session:
            recall = get_memory_recall(session)
            heard, reply, wav_bytes = run_turn(
                audio, llm=llm, stt=stt, voice=voice, recall=recall, session=session, history=history
            )
        print(f"You said: {heard}")
        if not heard.strip():
            print("(heard nothing, try again)")
            continue
        print(f"Clone: {reply}")
        _play(wav_bytes)


if __name__ == "__main__":
    main()
