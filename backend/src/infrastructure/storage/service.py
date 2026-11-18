from minio import Minio

from src.infrastructure.storage.minio.storage import MinioStorage
from src.libs.core.config import Settings


def create_storage_service(client: Minio, settings: Settings) -> MinioStorage:
    """Wrap the MinIO client in the StorageProvider adapter for the default bucket."""
    return MinioStorage(client=client, bucket_name=settings.minio_default_bucket)
