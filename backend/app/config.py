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

    # Local files holding the Owner's Likeness (voice clips, face assets). Never committed.
    likeness_dir: Path = REPO_ROOT / "likeness"


@lru_cache
def get_settings() -> Settings:
    return Settings()
