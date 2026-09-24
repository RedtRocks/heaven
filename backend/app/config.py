from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    database_url: str = "postgresql+psycopg://keepsake:keepsake@127.0.0.1:5433/keepsake"

    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-lite-latest"
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = "gpt-5-nano"

    groq_api_key: str = ""
    groq_stt_model: str = "whisper-large-v3-turbo"

    embedder_provider: str = "gemini"
    gemini_embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = 768

    # Days a new Memory waits before it's available to the Clone (ADR 0001).
    holding_period_days: int = 7
    # How many days ahead the Release Digest looks for Memories about to release.
    digest_window_days: int = 3

    # Load and warm the voice model in the background at startup, so the first
    # /voice/speak isn't a ~50 s wait. Off by default so tests never load the model.
    voice_warmup: bool = False

    # Local files holding the Owner's Likeness (voice clips, face assets). Never committed.
    likeness_dir: Path = REPO_ROOT / "likeness"

    # Face rendering: "musetalk_kaggle" (MuseTalk on a free Kaggle GPU) or "still" (a static
    # photo of the Owner dubbed with the audio via ffmpeg). See docs/notes/face-musetalk.md.
    face_provider: str = "still"
    face_jobs_dir: Path = REPO_ROOT / "data" / "face_jobs"
    face_photo_path: Path = REPO_ROOT / "likeness" / "face" / "photo.jpg"
    ffmpeg_path: str = "ffmpeg"

    # Kaggle: free-tier GPU used to run MuseTalk. See docs/notes/face-musetalk.md.
    kaggle_username: str = ""
    kaggle_key: str = ""
    kaggle_kernel_id: str = ""  # "<kaggle-username>/keepsake-musetalk"
    kaggle_jobs_dataset_id: str = ""  # "<kaggle-username>/keepsake-face-jobs"
    kaggle_poll_interval_seconds: float = 15.0
    kaggle_timeout_seconds: float = 1800.0

    # Live mode (Memory Assistant only, Stock Voice - see ADR 0003 and
    # docs/notes/live-mode.md). Gemini Live's free native-audio model as of the
    # research date; check https://ai.google.dev/gemini-api/docs/pricing before relying
    # on this, since model names moved from 2.5 to 3.x during 2026.
    live_model: str = "gemini-2.5-flash-native-audio-preview-09-2025"
    live_voice: str = "Puck"


@lru_cache
def get_settings() -> Settings:
    return Settings()
