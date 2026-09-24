# Task: voice (branch feat/voice), Phase 2

Goal: the Owner talks to the Clone out loud and it answers in the Owner's cloned voice, locally, for free.

Hardware: Windows 11, Ryzen 5 7530U (6 cores), integrated AMD GPU (NO CUDA), 16 GB RAM. Everything runs on CPU.

1. **Voice clone provider.** Implement `VoiceSynth` in `backend/app/providers/tts_chatterbox.py` using Resemble AI's Chatterbox (https://github.com/resemble-ai/chatterbox, MIT), preferring the CPU-oriented **Chatterbox-Nano** / smallest English model. Check the repo's README for the actual package name and API; don't guess. The reference clip is at `settings.likeness_dir / "voice" / "reference.wav"`. Add `get_voice()` to the registry. Put the dependency in an optional group `voice`: `uv add --optional voice ...`. Load the model lazily, once.
2. **Endpoint.** Add `POST /voice/speak` `{text}` → `audio/wav`, in `backend/app/voice/api.py`.
3. **Record the reference.** `backend/scripts/record_reference.py` records the Owner reading a displayed passage for ~30 s from the mic (use `sounddevice`) and saves it to the reference path. Add a second mode that converts an existing audio file.
4. **Live voice loop.** `backend/scripts/voice_loop.py`: mic → speech-to-text (`get_stt()`, Groq Whisper) → LLM (`get_llm()`) with a Clone system prompt → `get_voice()` → speaker. Try to build it on **Pipecat** (https://github.com/pipecat-ai/pipecat, local audio transport) with custom services wrapping our providers. If that takes more than a reasonable effort, ship a push-to-talk loop (press Enter to talk/stop) first and note Pipecat as the follow-up. The system prompt should come from `app.persona` if a function `build_clone_system_prompt` exists; otherwise use a short placeholder. Another agent is building persona, so import it defensively.
5. **Measure.** Actually install the voice group and synthesise 3 sentences with the default voice on this CPU. Record the real-time factor and first-audio latency in `docs/notes/voice.md`, with the command to reproduce it.

Tests: unit-test the endpoint and loop wiring with fake providers. Don't require the model in tests. Report as described in common-rules.
