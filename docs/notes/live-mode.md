# Live mode for the Memory Assistant (Stock Voice)

Researched 2026-09-24. *Unverified* marks claims without a primary source. Per ADR 0003, this is for the Memory Assistant and testing only, never the Clone.

## Choice: Gemini Live API (native audio), proxied through our backend

- **Free:** native-audio Live models are listed as free on the [pricing page](https://ai.google.dev/gemini-api/docs/pricing). Model names moved from 2.5 to 3.x during 2026, so check the page at build time (`gemini-2.5-flash-native-audio-preview` is documented; "Gemini 3.8 Live" is listed). Exact free-tier Live rate limits are *unverified*; check [rate limits](https://ai.google.dev/gemini-api/docs/rate-limits).
- **Privacy:** free-tier content **is used to improve Google's products**, and this includes spoken memories. This was accepted for v1 (design Q26, ADR 0002). Sealed Memories must still never be sent.
- **Sessions:** audio-only sessions cap at 15 min without context compression. The WebSocket drops about every 10 min and must be resumed ([session docs](https://ai.google.dev/gemini-api/docs/live-session)).
- **Voices:** 30 HD voices, default "Puck", set with `speechConfig.voiceName` ([capabilities](https://ai.google.dev/gemini-api/docs/live-api/capabilities)).
- **Tools:** function calling is supported, so `recall_memories(query)` runs server-side.
- **Security:** don't give the browser ephemeral tokens without locking the setup server-side. A 2026 flaw let clients override the model, tools and system prompt ([report](https://cybersecuritynews.com/gemini-live-voice-session-flaw/)). **Proxy through FastAPI:** the browser talks to our WebSocket, and our backend holds the key and runs tools.
- **SDK:** `google-genai`, `client.aio.live.connect(model=..., config=...)`.

## Lip-sync

Live output is raw 16-bit LE PCM (commonly 24 kHz). Decode it, queue it into Web Audio with the sample rate set explicitly, and feed the same audio to wawa-lipsync / TalkingHead. TalkingHead accepts PCM 16-bit chunks directly.

## Rejected

- **OpenAI `gpt-realtime-mini`:** about $0.02–0.15/min, so ~30 min/week comes to $2.60+/month. Over budget.
- **Local Pipecat + faster-whisper + Kokoro:** ₹0 and private, but probably 1–3 s end to end on CPU (*unverified*). This is the fallback if the Google data use becomes unacceptable.
- **Moshi / Ultravox:** need a GPU.
