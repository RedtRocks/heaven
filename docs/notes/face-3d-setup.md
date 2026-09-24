# Setting up your 3D talking face

This is the one-time setup for the real-time 3D face on `/clone`. It's Likeness
(your face), so the GLB file never gets committed to git — see `web/.gitignore`
(`web/public/avatar/`).

## 1. Create your avatar in Avaturn

1. Go to [avaturn.me](https://avaturn.me) and start the free avatar creator.
2. Upload 1-2 clear, front-facing photos of yourself (good lighting, neutral
   expression, no sunglasses/hats).
3. Adjust the generated avatar if you want (hair, skin tone, etc.) — the exact
   look doesn't need to be perfect, since the point is expressive lip-sync, not
   a photorealistic likeness.
4. Check Avaturn's current terms before exporting — the free tier may be
   non-commercial only. This is fine for personal use of Keepsake, but re-check
   if you ever plan to run Keepsake commercially.
5. Export the avatar as a **GLB**. Make sure the export includes **ARKit or
   Oculus visemes/blendshapes** (Avaturn's "for real-time lip-sync" or
   "ARKit blendshapes" export option — the important thing is that the mesh
   ends up with morph targets named like `viseme_aa`, `viseme_PP`,
   `mouthOpen`/`jawOpen`, etc.). Without these blendshapes the face will load
   but won't be able to move its mouth.

If Avaturn isn't available or doesn't fit your needs, the fallback is
MakeHuman + a hand-mapped photo texture, exported as GLB with the same
blendshape requirement — see `docs/notes/face-3d.md` for why this is the
fallback plan.

## 2. Put the file in place

Save the exported file as:

```
web/public/avatar/owner.glb
```

That directory is gitignored (`web/public/avatar/` in `.gitignore`) — this is
intentional, so your face is never pushed to any git remote. Nothing else in
the app needs to change; `FaceStage` looks for exactly this path.

## 3. Check it works

1. Start the web app (`cd web && pnpm dev`) and the backend as usual.
2. Open `http://localhost:3000/clone`. You should see your avatar instead of
   the "No 3D avatar yet" placeholder.
3. Send a chat message. The face should:
   - Move its lips while the Clone's reply is spoken, if `/voice/speak` is
     wired up on the backend (it plays the cloned-voice audio and drives the
     mouth from the actual waveform).
   - If `/voice/speak` isn't available yet (404/501/503), the mouth still
     moves (estimated from the words, no audio) and a small "Voice not set up"
     badge appears near the mute button. This is expected until the voice
     feature ships.
4. Add `?debug=1` to the URL (`http://localhost:3000/clone?debug=1`) to show
   an FPS counter in the top-left of the face panel. On the Owner's laptop
   (integrated Radeon GPU), this is worth checking after any change to the
   avatar or scene — a single skinned head should comfortably hold 30+ fps,
   but there's no guarantee until it's measured on the actual machine.
5. Use the "Mute" button in the bottom-right of the face panel to silence
   playback without stopping the lip movement.

## Troubleshooting

- **"No 3D avatar yet"** — the GLB isn't at `web/public/avatar/owner.glb`, or
  the dev server can't see it (restart `pnpm dev` after adding the file).
- **Avatar loads but the mouth never moves** — the GLB is probably missing the
  ARKit/Oculus viseme blendshapes. Re-export from Avaturn making sure the
  real-time/blendshapes option is selected.
- **Low frame rate** — try a lower-poly Avaturn export, close other GPU-heavy
  apps, and re-check with `?debug=1`.

## Development-only sample avatar

If you want to test the pipeline before making your own avatar, you can point
the face at a sample GLB (never your own Likeness) by setting, in
`web/.env.local`:

```
NEXT_PUBLIC_DEV_AVATAR_URL=https://example.com/path/to/sample-avatar.glb
```

Only use a URL you've checked the license for (e.g. one of the sample avatars
linked from the [TalkingHead repo](https://github.com/met4citizen/TalkingHead)).
Never commit `.env.local` or set this in production — it's for local
development only.
