# Phase 3: real-time 3D talking face — report

## What was built

- `web/components/FaceStage.tsx` — thin client wrapper that dynamically
  imports `FaceStageCanvas` with `ssr: false` (a `forwardRef` so the parent
  can reach `speak(text)`).
- `web/components/FaceStageCanvas.tsx` — the real component:
  - Loads the avatar from `NEXT_PUBLIC_DEV_AVATAR_URL || /avatar/owner.glb`
    via `@met4citizen/talkinghead`'s `TalkingHead` class. HEAD-checks the URL
    first so a missing GLB shows a friendly empty state (with a pointer to
    `docs/notes/face-3d-setup.md`) instead of spinning up WebGL for nothing.
  - `speak(text)`: POSTs `{API}/voice/speak {text}`.
    - On success, plays the returned WAV itself via an `<audio>` element and
      drives visemes every animation frame from the real waveform using
      **wawa-lipsync** (`Lipsync.connectAudio` + `processAudio()`), calling
      `head.setFixedValue(viseme, intensity)` — wawa-lipsync's viseme names
      (`viseme_PP`, `viseme_aa`, …) are exactly TalkingHead's Oculus viseme
      morph-target names, so no mapping table was needed.
    - On 404/501/503 (or any fetch/parse failure), falls back to
      `head.speakAudio({ audio: <silent buffer>, words, wtimes, wdurations })`
      with word timings estimated from the text
      (`web/lib/faceSpeech.ts::estimateWordTimings`), so TalkingHead's own
      English lip-sync module still drives the mouth with no audible sound.
      Shows a small "Voice not set up" badge in this case.
  - Mute toggle (mutes the `<audio>` element; lips keep moving).
  - Idle motion/blinking comes for free from TalkingHead's own render loop —
    nothing extra was needed there.
  - `modelPixelRatio` capped at 1.5 (`Math.min(devicePixelRatio, 1.5)`).
  - FPS counter shown top-left when the URL has `?debug=1` (own
    `requestAnimationFrame` counter, independent of TalkingHead internals).
- `web/lib/faceSpeech.ts` + `faceSpeech.test.ts` — the two pure decisions
  (which HTTP statuses mean "voice not set up", and how to estimate per-word
  timing for the silent fallback) extracted so they're unit-testable without
  a browser/WebGL/AudioContext. Added `vitest` (lightweight, not a heavy
  framework) with a `pnpm test` script; 5 tests, all passing.
- `web/types/talkinghead.d.ts` — minimal ambient `.d.ts` for the package
  (it ships plain `.mjs` with no types).
- `web/components/Chat.tsx` — new optional `onAssistantReply?: (text) => void`
  prop, called after each assistant reply is appended to `messages`.
  `/assistant/page.tsx` doesn't pass it, so that page is unaffected — the only
  other change there is switching `Chat`'s root `h-screen` to `h-full` (see
  below) with the page's own wrapper `div` now setting `h-screen` to keep the
  exact same full-viewport look.
- `web/app/clone/page.tsx` — face on top on narrow screens, left column
  (`lg:w-[420px]`) on wide screens, chat filling the rest; holds a
  `useRef<FaceStageHandle>` and passes `onAssistantReply={(t) =>
  faceRef.current?.speak(t)}` into `Chat`.
- `docs/notes/face-3d-setup.md` — Owner-facing guide: Avaturn photo → GLB
  export with ARKit/Oculus blendshapes → save at
  `web/public/avatar/owner.glb` → verify with `?debug=1`; troubleshooting;
  the dev-only `NEXT_PUBLIC_DEV_AVATAR_URL` escape hatch.

## TalkingHead version and import method — and why

**`@met4citizen/talkinghead@1.7.0` from npm**, imported as a normal ES module
(`import { TalkingHead } from "@met4citizen/talkinghead"`), bundled by
Turbopack like any other dependency. `three@^0.180.0` (its peer dep) also
installed from npm.

This was not the obvious choice. The npm package's `lipsyncGetProcessor`
method does `import(path + 'lipsync-' + lang + '.mjs')` — a dynamic import
built from a partly-dynamic string, used to lazy-load TalkingHead's
per-language lip-sync module. Two problems, both fixed by one `pnpm patch`
(`web/patches/@met4citizen__talkinghead@1.7.0.patch`, registered in
`web/pnpm-workspace.yaml`'s `patchedDependencies` so `pnpm install` reapplies
it automatically):

1. Turbopack **hard-fails the production build** trying to statically
   resolve that dynamic specifier (`Module not found: Can't resolve
   <dynamic>`), whereas webpack would only warn and fall back to a context
   module. Fixed by adding `/* webpackIgnore: true */ /* turbopackIgnore:
   true */` before the `import()` call, telling both bundlers to leave it
   as runtime-only.
2. That alone wasn't sufficient: ignoring the import doesn't change where it
   resolves *at runtime* — the default `path="./"` makes the browser fetch
   `lipsync-en.mjs` relative to the bundled chunk's own URL
   (`/_next/static/chunks/<hash>.js`), where no such file exists, so it would
   404 silently (the `.then` has no `.catch`) and TalkingHead's English
   lip-sync module would never load. I confirmed this by grepping the built
   chunk for the literal `import(...)` call and its default path. Fixed by
   copying the (dependency-free) `lipsync-en.mjs` to
   `web/public/talkinghead-modules/` and changing the patched default path to
   `/talkinghead-modules/`, then re-verified by grepping the rebuilt chunk
   for that new path string.

I considered the CDN ES-module route from the README (`<script
type="importmap">` pointing at jsdelivr for `three`, `three/addons/`, and
`talkinghead`) instead, since it sidesteps the bundler issue entirely (the
browser resolves the dynamic per-language import natively, relative to the
already-remote module URL). I didn't use it because import maps must be
present before any module script starts fetching, which is brittle to
guarantee inside a Next.js app that already ships its own module chunks —
and it would also mean the avatar rendering code and its type-checking sit
outside Next's normal build/lint/test pipeline (`pnpm lint`/`pnpm build`
couldn't touch it at all). The npm package + patch keeps everything inside
the normal toolchain, and the patch is one clearly-commented line.

## What I verified

- `pnpm lint` — clean, no errors or warnings.
- `pnpm build` — succeeds with Turbopack, all 9 routes prerender
  (`/clone` included).
- `pnpm test` (vitest) — 5/5 passing, covering the voice-unavailable status
  check and the word-timing estimator.
- Read `TalkingHead`'s README (fetched from GitHub) and the installed
  package source directly (`node_modules/@met4citizen/talkinghead`,
  `talkinghead.mjs`) to confirm constructor options, `showAvatar`,
  `speakAudio`, `setFixedValue`, and the exact shape of the dynamic
  lip-sync-module import that needed patching.
- Read `wawa-lipsync`'s compiled `dist/index.d.ts` to confirm its `VISEMES`
  enum values are the literal strings `viseme_sil`, `viseme_PP`, `viseme_aa`,
  etc. — the same names TalkingHead's `setFixedValue` expects for Oculus
  visemes, so no translation layer was needed between the two libraries.

## What I could not verify (no GPU, no audio, no browser here)

- **Frame rate on the Owner's integrated Radeon.** The FPS counter
  (`?debug=1`) is wired up and the pixel ratio is capped at 1.5, but I have
  no way to run the app in a real browser with a GPU from this environment.
  The Owner needs to check this themselves per `face-3d-setup.md` step 4.
- **That an actual Avaturn GLB loads and its blendshapes drive
  `viseme_*`/`setFixedValue` correctly.** I never had a real GLB to load —
  there's no avatar checked in (by design; it's gitignored Likeness) and I
  didn't fetch a third-party sample GLB to test with. The HEAD-check /
  missing-avatar empty state was exercised implicitly (no file exists in
  this worktree, so that's the state `pnpm dev` would currently show), but
  the "avatar found and displays" and "mouth actually moves" paths are
  unverified beyond reading the library source.
- **That `/voice/speak` behaves as specified.** It's being built by another
  agent in parallel; I coded against the stated contract
  (`POST {text} -> audio/wav`, `404/501/503` meaning "not set up") but
  haven't run against a live implementation.
- **That the browser can actually fetch `/talkinghead-modules/lipsync-en.mjs`
  at runtime.** I confirmed by grepping the built chunk that the dynamic
  import now targets that static path (rather than a nonexistent relative
  chunk path, which is what it targeted before this fix), and that the file
  exists under `web/public/`, but I couldn't launch a browser here to load
  the page and watch the network tab confirm the fetch succeeds and
  `module.LipsyncEn` is a valid class.
- **Audio playback and lip-sync quality/timing**, obviously — I can't hear
  or watch it move. If the mouth still doesn't move in the silent fallback
  path once the Owner tests it, check the browser console/network tab for
  that dynamic import first.

## What the Owner must do by hand

1. Create the avatar in Avaturn from their own photos and export as GLB with
   ARKit/Oculus blendshapes (full steps in `docs/notes/face-3d-setup.md`).
2. Save it at `web/public/avatar/owner.glb` (gitignored — never commit it).
3. Run `cd web && pnpm dev`, open `/clone?debug=1`, confirm the avatar loads,
   the FPS counter reads a reasonable number, and (once `/voice/speak` is
   live) the mouth moves in sync with audio.
4. If the mouth doesn't move at all even though the avatar loads, check the
   browser console for a dynamic-import error on `lipsync-en.mjs` — see the
   turbopackIgnore caveat above — and report back so the patch can be
   adjusted (e.g. pointing `lipsyncGetProcessor`'s `path` argument at an
   absolute `/talkinghead-modules/` URL served from `public/` instead of
   relying on the bundled chunk's relative resolution).
