# Real-time 3D face (Phase 3): research notes

Researched 2026-09-24. Items marked *unverified* need checking before relying on them.

## Decision for v1

1. **Head asset**: a stylized, rigged GLB of the Owner from photos, made with **Avaturn**'s free tier (*unverified*: check avaturn.me terms first). Fallback: MakeHuman + hand-mapped photo texture.
2. **Rendering and lip-sync**: **[met4citizen/TalkingHead](https://github.com/met4citizen/TalkingHead)** (three.js, actively maintained) loads GLB avatars with ARKit/Oculus visemes. Its **HeadAudio** module derives visemes from the audio signal in the browser, so Chatterbox's plain WAV (no timestamps) works as-is. **[wawa-lipsync](https://github.com/wass08/wawa-lipsync)** is a drop-in alternative.
3. Measure frame rate on the Owner's integrated Radeon (*unverified*; a single skinned mesh should be fine).

## What's ruled out, and why

- **Ready Player Me** was acquired by Netflix, and its creator and APIs shut down on 2026-01-31 ([TechCrunch](https://techcrunch.com/2025/12/19/netflix-acquires-gaming-avatar-maker-ready-player-me/)). Old GLBs still load.
- **Gaussian-splat heads** (GaussianAvatars): viseme-driven splat heads have no verified browser viewer, so this is a stretch goal only.
- **Rhubarb**: offline CLI, which adds a server round trip. Not needed now that HeadAudio exists.

## Stretch: better likeness

Fit a FLAME identity with **[inferno/EMICA](https://github.com/radekd91/inferno)** (the successor to DECA/EMOCA/MICA) on a Kaggle T4, then retarget to a GLB blendshape rig. There's no turnkey exporter (*unverified*), and the FLAME license is non-commercial.

## Alternative TTS path

**[HeadTTS](https://github.com/met4citizen/HeadTTS)** (Kokoro) outputs phoneme timestamps, which give tighter sync. But it isn't the Owner's cloned voice, so we keep Chatterbox + HeadAudio.
