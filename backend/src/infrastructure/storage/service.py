import base64

from minio import Minio
from minio.sse import SseCustomerKey

from src.infrastructure.storage.minio.storage import MinioStorage
from src.libs.core.config import Settings
from src.libs.core.logger import get_logger

logger = get_logger("storage.service")


def create_storage_service(client: Minio, settings: Settings) -> MinioStorage:
    """Wraps the client in your custom Storage Provider."""
    logger.info("Initializing MinIO S3 service.")
    return MinioStorage(
        client=client,
        bucket_name=settings.minio_default_bucket,
        sse_key=SseCustomerKey(
            key=base64.b64decode(settings.minio_sse_customer_key.get_secret_value())
        ),  # string to byte code
    )
