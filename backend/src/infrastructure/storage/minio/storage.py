from datetime import timedelta

from minio import Minio, S3Error
from minio.sse import SseCustomerKey

from src.core.logger import get_logger
from src.domain.documents.dataclasses import (
    DocumentChecksum,
    DocumentStream,
    StorageKey,
    StoredFile,
)
from src.infrastructure.storage.provider import StorageProvider
from src.utils.exceptions import StorageOperationError

logger = get_logger("api-backend.infra.minio")


DEFAULT_PART_SIZE = 10 * 1024 * 1024


class MinioStorage(StorageProvider):
    def __init__(
        self,
        client: Minio,
        bucket: str,
        sse_key: SseCustomerKey | None = None,
    ) -> None:
        self.client = client
        self.bucket_name = bucket
        self.sse_key = sse_key

    def create_bucket(self) -> None:
        """Checks if bucket already exists for warm start."""
        found = self.client.bucket_exists(bucket_name=self.bucket_name)
        if not found:
            self.client.make_bucket(bucket_name=self.bucket_name)
            logger.info(f"Minio bucket {self.bucket_name} created.")

    def create_upload_url(self, storage_key: StorageKey, expires_at: timedelta) -> str:
        """Get presigned URL string to upload 'bucket-object' in MinIO bucket
        with response-content-type as application/json and one two hour expiry.
        """
        try:
            return self.client.get_presigned_url(
                method="PUT",
                bucket_name=self.bucket_name,
                object_name=storage_key.value,
                expires=expires_at,
                extra_query_params={"response-content-type": "application/json"},
            )
        except S3Error as e:
            logger.exception(
                f"Failed to generate presigned upload URL for '{storage_key}' with MinIO!",
            )
            raise StorageOperationError(
                "MinIO Storage Error",
                f"Failed to generate presigned upload URL for '{storage_key}' with MinIO!",
            ) from e

    def create_download_url(
        self, storage_key: StorageKey, expires_at: timedelta
    ) -> str:
        """Get presigned URL string to download 'bucket-object' in MinIO bucket
        with two hour expiry.
        """
        try:
            return self.client.get_presigned_url(
                method="GET",
                bucket_name=self.bucket_name,
                object_name=storage_key.value,
                expires=expires_at,
            )
        except S3Error as e:
            logger.exception(
                f"Failed to generate presigned download URL for '{storage_key}' with MinIO!",
            )
            raise StorageOperationError(
                "MinIO Storage Error",
                f"Failed to generate presigned download URL for '{storage_key}' with MinIO!",
            ) from e

    def create_delete_url(self, storage_key: StorageKey, expires_at: timedelta) -> str:
        """Get presigned URL string to delete 'bucket-object' in MinIO bucket
        with one day expiry.
        """
        try:
            return self.client.get_presigned_url(
                method="DELETE",
                bucket_name=self.bucket_name,
                object_name=storage_key.value,
                expires=expires_at,
            )
        except S3Error as e:
            logger.exception(
                f"Failed to generate presigned URL for '{storage_key}' with MinIO!",
            )
            raise StorageOperationError(
                "MinIO Storage Error",
                f"Failed to generate presigned URL for '{storage_key}' with MinIO!",
            ) from e

    def store_file(
        self,
        file: DocumentStream,
        storage_key: StorageKey,
        checksum: DocumentChecksum | None = None,
    ) -> StoredFile:
        """
        Uploads a document stream to MinIO blob storage.
        """
        # Determine size parameters
        length = file.size_bytes if file.size_bytes is not None else -1
        part_size = DEFAULT_PART_SIZE if length == -1 else 0
        content_type = file.content_type or "application/octet-stream"

        try:
            uploaded_file = self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=storage_key.value,
                data=file.stream,
                length=length,
                part_size=part_size,
                content_type=content_type,
                sse=self.sse_key,  # from dotenv file
            )

            logger.info(
                f"Successfully uploaded '{uploaded_file.object_name}' to MinIO bucket '{self.bucket_name}'",
                extra={
                    "storage_key": storage_key,
                    "bucket": self.bucket_name,
                    "etag": uploaded_file.etag,
                    "version_id": uploaded_file.version_id,
                },
            )

            # Construct the returned domain model
            return StoredFile(
                storage_key=StorageKey(uploaded_file.object_name),
                size_bytes=file.size_bytes
                if file.size_bytes is not None
                else 0,  # TODO: track actual bytes written
                mime_type=content_type,
                version_id=uploaded_file.version_id,
                bucket_name=uploaded_file.bucket_name,
                etag=uploaded_file.etag,
                checksum=checksum or DocumentChecksum(""),
            )

        except S3Error as e:
            logger.exception(
                f"Failed to upload binary file '{storage_key}' from MinIO!",
            )
            raise StorageOperationError(
                "MinIO Storage Error",
                f"Failed to upload binary file '{storage_key}' from MinIO!",
            ) from e


    def delete_file(
        self,
        storage_key: StorageKey,
    ) -> None:
        try:
            self.client.remove_object(self.bucket_name, storage_key.value)
            logger.info(
                f"Successfully removed '{storage_key}' from MinIO bucket '{self.bucket_name}'",
                extra={
                    "storage_key": storage_key,
                    "bucket": self.bucket_name,
                },
            )
        except S3Error as e:
            logger.exception(
                f"Failed to remove binary file '{storage_key}' from MinIO!",
            )
            raise StorageOperationError(
                "MinIO Storage Error",
                f"Failed to remove binary file '{storage_key}' from MinIO!",
            ) from e
