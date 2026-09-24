from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.archive import models as _archive_models  # noqa: F401  (registers tables)
from app.archive.api import router as archive_router
from app.db import create_all, get_session
from app.people import models as _people_models  # noqa: F401  (registers tables)
from app.persona import models as _persona_models  # noqa: F401  (registers tables)
from app.persona.api import router as persona_router
from app.providers import ChatMessage
from app.providers.registry import get_llm


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_all()
    yield


app = FastAPI(title="Keepsake", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["http://localhost:3000"], allow_methods=["*"], allow_headers=["*"]
)
app.include_router(archive_router)
app.include_router(persona_router)


@app.get("/health")
def health(session: Session = Depends(get_session)) -> dict:
    vector = session.execute(text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")).scalar()
    return {"ok": True, "pgvector": vector}


class PingRequest(BaseModel):
    message: str


@app.post("/llm/ping")
def llm_ping(body: PingRequest) -> dict:
    """Phase 0 check: one text round-trip through the LLM adapter."""
    reply = get_llm().complete([ChatMessage("user", body.message)])
    return {"reply": reply}
