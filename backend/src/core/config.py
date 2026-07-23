# Loads settings from .env using Pydantic
from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    # ---------------------------------------------------------
    # Application
    # ---------------------------------------------------------

    app_name: str = "Graph RAG Backend"
    debug: bool = True
    api_prefix: str = "/api/v1"

    # ---------------------------------------------------------
    # PostgreSQL
    # ---------------------------------------------------------

    postgresql_url: str
    postgresql_echo: bool = False

    # ---------------------------------------------------------
    # MinIO
    # ---------------------------------------------------------

    minio_url: str
    minio_bucket_name: str
    minio_access_key: str
    minio_secret_key: str
    minio_region: str = "us-east-1"

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env.app",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore
