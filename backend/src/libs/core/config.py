"""Application settings, loaded from environment variables and the nearest .env file."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, HttpUrl, PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Dynamically find the directory of .env file
CURRENT_FILE = Path(__file__).resolve()
BASE_DIR = CURRENT_FILE.parent

# Walk up the directory tree
while not (BASE_DIR / ".env").exists() and BASE_DIR.parent != BASE_DIR:
    BASE_DIR = BASE_DIR.parent


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
    log_level: str = "INFO"
    debug: bool = False
    api_prefix: str = "/api/v1"

    # Signs the access tokens. HS256 needs at least 32 bytes of key (RFC 7518).
    secret_key: SecretStr = Field(min_length=32)
    algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    access_token_expire_minutes: int = Field(default=30, gt=0)
    reset_token_expire_minutes: int = Field(default=60, gt=0)

    # ---------------------------------------------------------
    # Database (e.g. PostgreSQL)
    # ---------------------------------------------------------

    postgres_url: PostgresDsn
    postgres_echo: bool = False
    # Connections per process. Keep (replicas x workers x pool) below max_connections.
    postgres_pool_size: int = Field(default=5, gt=0)

    # ---------------------------------------------------------
    # S3 Storage (e.g. MinIO S3)
    # ---------------------------------------------------------

    minio_url: str
    minio_root_user: SecretStr
    minio_root_password: SecretStr
    minio_default_bucket: str = "files"
    minio_region: str = "us-east-1"
    minio_secure: bool = False

    # ---------------------------------------------------------
    # Message Broker (e.g. Kafka KRaft). Offsets are always committed manually.
    # ---------------------------------------------------------

    kafka_bootstrap_servers: str
    kafka_topics: list[str] = ["minio-events"]
    kafka_group_id: str = "minio-ingestion-group"
    kafka_auto_offset_reset: Literal["earliest", "latest"] = "earliest"

    # ---------------------------------------------------------
    # Temporal
    # ---------------------------------------------------------

    temporal_url: str
    temporal_default_namespace: str = "default"
    temporal_task_queue: str

    # ---------------------------------------------------------
    # Chunking (ingestion worker)
    # ---------------------------------------------------------

    # Use the tokenizer of the embedding model, so no chunk exceeds its input size.
    chunk_tokenizer_model: str = "BAAI/bge-small-en-v1.5"
    chunk_max_tokens: int = Field(default=512, gt=0)
    # OCR is slow; digital PDFs (for example SEC filings) have a text layer.
    docling_do_ocr: bool = False
    # A presigned PUT cannot limit the upload size, so the worker refuses larger
    # files before it downloads or parses them.
    max_upload_bytes: int = Field(default=50 * 1024 * 1024, gt=0)
    max_document_pages: int = Field(default=500, gt=0)
    # Files that one worker process parses at the same time (Docling is not
    # thread-safe, so more than 1 only queues inside the process).
    max_concurrent_parses: int = Field(default=1, gt=0)

    # ---------------------------------------------------------
    # Frontend
    # ---------------------------------------------------------

    frontend_url: HttpUrl

    @property
    def log_json(self) -> bool:
        """Log JSON lines everywhere except in development (readable console lines)."""
        return self.environment != "development"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings. Raise ValidationError if a required value is missing."""
    return Settings()  # type: ignore[call-arg]
