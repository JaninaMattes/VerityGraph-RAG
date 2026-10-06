"""
Framework-agnostic dependency factories.
Used by both FastAPI (for global singletons) and Temporal/Kafka workers.
"""

from minio import Minio

from src.libs.core.config import Settings
from src.libs.core.logger import get_logger

logger = get_logger("storage.client")


def create_storage_client(settings: Settings) -> Minio:
    """Initialize the MinIO Client."""
    logger.info("Initializing MinIO client.")
    return Minio(
        endpoint=settings.minio_url,
        access_key=settings.minio_root_user.get_secret_value(),
        secret_key=settings.minio_root_password.get_secret_value(),
        region=settings.minio_region,
        secure=settings.minio_secure,
    )
