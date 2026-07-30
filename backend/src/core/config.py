# Loads settings from .env using Pydantic
from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    # ---------------------------------------------------------
    # Application
    # ---------------------------------------------------------

    app_name: str = "Graph RAG Backend"
    debug: bool = True
    api_prefix: str = "/api/v1"

    secret_key: SecretStr
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    reset_token_expire_minutes: int = 60

    # ---------------------------------------------------------
    # Database (e.g. PostgreSQL)
    # ---------------------------------------------------------

    database_url: str

    # ---------------------------------------------------------
    # Blob Storage (e.g. MinIO S3)
    # ---------------------------------------------------------

    # TODO: Store secrets safely as SecretStr
    storage_url: str
    storage_default_buckets: str
    storage_access_key: str
    storage_secret_key: str
    storage_sse_customer_key: str
    storage_region: str = "us-east-1"
    storage_secure: bool

    # ---------------------------------------------------------
    # Frontend
    # ---------------------------------------------------------
    frontend_url: str

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )



@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore
