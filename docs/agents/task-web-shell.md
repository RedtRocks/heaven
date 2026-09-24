# Task: web shell (branch feat/web-shell)

Build the Next.js web app in `web/` (App Router, TypeScript, Tailwind, pnpm). Scaffold it non-interactively.

Pages:
- `/`: home. Short intro and links to the other pages.
- `/assistant`: Memory Assistant chat. It calls `POST {API}/assistant/chat` with `{message, history: [{role, content}]}` and gets back `{reply, citations: [{id, text, happened_on}]}`. Show citations under each reply. Until that endpoint exists, if it returns 404, fall back to `POST {API}/llm/ping` with `{message}` → `{reply}`.
- `/clone`: Clone chat, with the same shape at `POST {API}/clone/chat` plus an optional `visitor_id`. Leave a clearly marked area on the page (a `components/face/FaceStage.tsx` placeholder) where the 3D face will go later. Include a "play voice" button per reply that calls `POST {API}/voice/speak` with `{text}` → `audio/wav` and plays it. Hide the button if the endpoint 404s.
- `/entries`: a textarea to write today's Entry, which calls `POST {API}/entries` with `{text}`. Also record a voice Entry in the browser (MediaRecorder) and upload it to `POST {API}/entries/audio` (multipart field `file`).
- `/memories`: list from `GET {API}/memories`, with seal/unseal buttons calling `PATCH {API}/memories/{id}` with `{sealed: bool}`.

Use one reusable `Chat` component for both chats. The API base comes from `NEXT_PUBLIC_API_URL`, defaulting to `http://localhost:8000`. Every page must handle the backend being down gracefully.

Design: calm, warm, minimal. This is a personal memory app, not a SaaS dashboard. Support dark mode.

Done when `pnpm build` passes and `pnpm lint` is clean. Report as described in common-rules.
