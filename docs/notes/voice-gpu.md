# Making the cloned voice fast: free GPU options

Researched 2026-09-24. *Unverified* marks claims without a primary source.

The Clone must use the Owner's cloned voice (ADR 0003). On the Owner's CPU, Chatterbox-Nano runs at ~2.1× real time (docs/notes/voice.md). Options for getting below 1×:

| Option | Free amount | Serving a live API allowed? | Fit |
|---|---|---|---|
| **[Modal](https://modal.com/pricing)** | $30/month credits, renews | Yes, it's the product | **Best.** ~7–10 GPU-hours/month; scales to zero; ~1–2 s cold start |
| [Colab free](https://research.google.com/colaboratory/faq.html) | T4, ≤12 h sessions | **No.** The FAQ disallows "remote control such as SSH shells, remote desktops", "bypassing the notebook UI to interact primarily via a web UI" and "connecting to remote proxies" | Manual benchmarking inside a notebook only |
| [Kaggle](https://www.kaggle.com/docs/efficient-gpu-usage) | 30 GPU-h/week (P100 or 2×T4) | *Unverified*; no explicit clause found, against the spirit | Batch jobs (MuseTalk already runs this way) |
| [HF ZeroGPU](https://huggingface.co/docs/hub/en/spaces-zerogpu) | ~3.5 GPU-min/day | Yes, private Space + token | Short tests only |
| GCP trial | $300 once, 90 days | Yes | One-off, not ₹0 long term |

## Streaming

Official Chatterbox doesn't stream ([#71](https://github.com/resemble-ai/chatterbox/issues/71), [#193](https://github.com/resemble-ai/chatterbox/issues/193)). Community forks do:
- [davidbrowne17/chatterbox-streaming](https://github.com/davidbrowne17/chatterbox-streaming): RTF ~0.5 and ~0.47 s to first chunk on an RTX 4090. T4 numbers are *unverified*; expect roughly 1.5–2.5 s to first chunk.
- [devnen/Chatterbox-TTS-Server](https://github.com/devnen/Chatterbox-TTS-Server): an OpenAI-compatible streaming server, a good deployment reference.

## Faster CPU cloners

Nothing confirmed faster than Nano with a permissive license. ZeroTTS and ZipVoice-Distill claims are *unverified* (ZeroTTS appears to be Vietnamese-focused). Kokoro is fast but can't clone.

## Decision

1. **Primary path:** deploy Chatterbox (Nano or Turbo) on **Modal** behind a `ModalVoiceSynth` provider. `VOICE_PROVIDER=modal|local`.
2. **Always-available fallback:** local Nano on CPU (what we have now).
3. **Measure first:** before building streaming, benchmark on Modal's T4/A10G to see whether plain per-sentence synthesis already goes below 1× RTF.
4. **Not used:** Colab or Kaggle as a live server (terms).
