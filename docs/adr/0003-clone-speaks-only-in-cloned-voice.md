# The Clone speaks only in the Owner's cloned voice

Speech-to-speech APIs (Gemini Live, OpenAI Realtime) feel far more natural than our own pipeline, which runs about 2× slower than real time on the Owner's CPU. But their free options only offer stock voices. The Owner decided the Clone must never speak in a voice that isn't theirs: a Clone with a stranger's voice defeats the point for a Visitor. So the Clone always uses the cloned-voice path, even when it's slower. Stock Voices, including fast speech-to-speech APIs, are allowed only for the Memory Assistant (the Owner hearing their own voice answer them feels wrong) and for testing.

## Consequences

- Any "live mode" built on a stock-voice speech-to-speech API belongs to the Memory Assistant, never to `/clone`.
- Making the Clone feel live means making cloned-voice synthesis faster (GPU, streaming), not swapping voices.
