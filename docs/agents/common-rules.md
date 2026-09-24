# Rules for every agent working on Keepsake

You are one of several agents building Keepsake in parallel. Each agent has its own git worktree and branch.

1. Before writing code, read `CONTEXT.md` (the glossary), `docs/v1-plan.md` and `docs/adr/`. Use the glossary terms exactly (Owner, Visitor, Entry, Memory, Sealed, Trait…) in code, names and comments.
2. Work only inside your worktree directory. Never push, never switch branches, never touch `main` or other worktrees. Commit to your current branch often, with clear messages.
3. Backend (Python 3.13, FastAPI, managed with `uv`, in `backend/`):
   - Put your code in its own package `backend/app/<module>/`. Put models in `models.py` and HTTP routes in `api.py`, exposing `router = APIRouter(...)`.
   - Register the router with ONE line in `backend/app/main.py`: `app.include_router(...)`. Import your models module there too, so tables get created. Don't reorganise `main.py`.
   - Vendor SDKs (google-genai, openai, groq, chatterbox, etc.) are imported ONLY inside `backend/app/providers/`, behind the Protocols in `backend/app/providers/__init__.py`. Other code gets providers through `backend/app/providers/registry.py`.
   - Shared contracts already exist: `app/people/models.py` (Person), `app/conversation/contracts.py` (MemoryRecall, RecalledMemory), and the Embedder Protocol. Don't change their signatures. If you need something extra, add it in your own module.
   - Postgres + pgvector runs at `127.0.0.1:5433` (see `.env.example`). Tables are created with `Base.metadata.create_all` (no migrations yet).
   - Tests go in `backend/tests/`, run with `cd backend && uv run pytest -q`. There are NO real API keys. Tests must use fake providers and must pass before you finish. See `docs/testing.md` for the guide.
   - Add dependencies with `uv add`. Heavy ones (torch and so on) go in an optional group: `uv add --optional <group> <pkg>`.
4. Web app: Next.js + TypeScript in `web/`, using pnpm.
5. Never commit personal data, audio, video or model weights. `likeness/` and `data/` are gitignored.
6. When done, write a short report at `docs/agents/reports/<your-branch-name>.md`: what you built, how to run it, what you verified, and what's unverified or left undone. Commit it.
7. Database tests: use ONLY your own test database, `postgresql+psycopg://keepsake:keepsake@127.0.0.1:5433/test_<branch>` where `<branch>` is your branch name without `feat/` and with `-` replaced by `_` (e.g. `test_memory`). It already exists and has pgvector. You may create and drop tables in it freely. Never touch the `keepsake` database from tests.
