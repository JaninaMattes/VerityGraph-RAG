# Loads settings from .env using Pydantic
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, HttpUrl, PostgresDsn, RedisDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # prevents crash
    )
    # ---------------------------------------------------------
    # Application
    # ---------------------------------------------------------

    app_name: str = "Graph RAG Backend"
    environment: Literal["development", "testing", "production"] = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"

    secret_key: SecretStr
    algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    access_token_expire_minutes: int = Field(default=30, gt=0)
    reset_token_expire_minutes: int = Field(default=60, gt=0)

    # ---------------------------------------------------------
    # Database (e.g. PostgreSQL)
    # ---------------------------------------------------------

    postgres_url: PostgresDsn
    postgres_echo: bool = False

    # ---------------------------------------------------------
    # Blob Storagee (e.g. MinIO S3)
    # ---------------------------------------------------------

    minio_endpoint: str
    minio_root_user: SecretStr
    minio_root_password: SecretStr
    minio_default_bucket: str = "files"
    minio_region: str = "us-east-1"
    minio_secure: bool = True
    minio_sse_customer_key: SecretStr

    # ---------------------------------------------------------
    # Cache (e.g. Redis)
    # ---------------------------------------------------------
    cache_url: RedisDsn

    # ---------------------------------------------------------
    # Temporal
    # ---------------------------------------------------------

    temporal_endpoint: str
    temporal_namespace: str = "default"
    temporal_task_queue: str

    # ---------------------------------------------------------
    # Frontend
    # ---------------------------------------------------------
    frontend_url: HttpUrl


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore
