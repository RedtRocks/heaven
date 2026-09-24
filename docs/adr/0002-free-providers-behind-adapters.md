# Free-tier AI providers behind swappable adapters, no Claude API

The project has a budget of about ₹100–200/month, so it cannot use the Claude API. Every AI capability (LLM, speech-to-text, voice synthesis, face rendering) sits behind its own adapter. The first providers are free tiers or local open-source models: Gemini Flash-Lite or gpt-5-nano, Groq Whisper, Chatterbox-Nano and MuseTalk. We don't create multiple accounts to reuse free credits, because OpenRouter's and Google's terms forbid it. The Owner's Likeness (voice reference clips, face data) lives in local files, never only inside a provider account, so switching providers never loses it.

## Consequences

- Free-tier Gemini content may be used by Google and read by human reviewers. We accept this for v1. Sensitive processing will move to a local model later.
