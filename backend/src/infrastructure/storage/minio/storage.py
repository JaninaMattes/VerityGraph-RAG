from datetime import timedelta

from minio import Minio, S3Error
from minio.sse import SseCustomerKey

from src.core.logger import get_logger
from src.domain.documents.dataclasses import (
    StorageKey,
    StoredFile,
)
from src.infrastructure.storage.provider import StorageProvider
from src.utils.exceptions import (
    AccessDeniedException,
    ObjectNotFoundException,
    StorageOperationException,
)

logger = get_logger("api.infra.minio")

class MinioStorage(StorageProvider):
    def __init__(
        self,
        client: Minio,
        bucket_name: str,
        sse_key: SseCustomerKey | None = None,
    ) -> None:
        self.client = client
        self.bucket_name = bucket_name
        self.sse_key = sse_key


    def create_bucket(self) -> None:
        """Checks if bucket already exists for warm start."""
        try:
            found = self.client.bucket_exists(bucket_name=self.bucket_name)
            if not found:
                self.client.make_bucket(bucket_name=self.bucket_name)
                logger.info(f"A bucket with name {self.bucket_name} was created.")
            else:
                logger.info(f"A bucket with name {self.bucket_name} already exists.")
        except S3Error as exc:
            if exc.code == "AccessDenied" or exc.code == "InvalidAccessKeyId":
                logger.warning(
                    "Access to bucket %s denied due to missing permissions or bad credentials.",
                    self.bucket_name,
                )
                raise AccessDeniedException(
                    bucket_name=self.bucket_name,
                ) from exc
            logger.warning(
                "Raised error for bucket %s. "
                "This could be due to an invalid or conflicting function argument.",
                self.bucket_name,
            )
            raise StorageOperationException(
                f"Failed to create bucket '{self.bucket_name}'."
            ) from exc

    def create_presigned_url(
        self, storage_key: StorageKey, expires_at: timedelta, method="PUT"
    ) -> str:
        """
        Generate a presigned PUT URL for an object.
        The response-content-type as application/json and one two hour expiry.
        """
        try:
            return self.client.get_presigned_url(
                method=method,
                bucket_name=self.bucket_name,
                object_name=storage_key.value,
                expires=expires_at,
                extra_query_params={"response-content-type": "application/json"},
            )
        except S3Error as exc:
            logger.warning(
                "Raised storage related error for key %s in bucket %s. This could be due to an invalid or conflicting function argument.",
                storage_key,
                self.bucket_name,
            )
            raise StorageOperationException(
                f"Failed to generate presigned '{method}' URL for object '{storage_key}'."
            ) from exc

    def create_download_url(
        self, storage_key: StorageKey, expires_at: timedelta, method="GET"
    ) -> str:
        """Generate a presigned GET URL for an object.
        with two hour expiry.
        """
        try:
            return self.client.get_presigned_url(
                method=method,
                bucket_name=self.bucket_name,
                object_name=storage_key.value,
                expires=expires_at,
            )
        except S3Error as exc:
            logger.warning(
                "Raised storage related error for key %s in bucket %s. This could be due to an invalid or conflicting function argument.",
                storage_key,
                self.bucket_name,
            )
            raise StorageOperationException(
                f"Failed to generate presigned '{method}' URL for object '{storage_key}'."
            ) from exc

    def create_delete_url(
        self, storage_key: StorageKey, expires_at: timedelta, method="DELETE"
    ) -> str:
        """Generate a presigned DELETE URL for an object.
        with one day expiry.
        """
        try:
            return self.client.get_presigned_url(
                method=method,
                bucket_name=self.bucket_name,
                object_name=storage_key.value,
                expires=expires_at,
            )
        except S3Error as exc:
            logger.warning(
                "Raised error for key %s in bucket %s. This could be due to an invalid or conflicting function argument.",
                storage_key,
                self.bucket_name,
            )
            raise StorageOperationException(
                f"Failed to generate presigned '{method}' URL for object '{storage_key}'."
            ) from exc

    def get_obj_metadata(
        self,
        storage_key: StorageKey,
    ) -> StoredFile:
        """Get 'bucket-object' information from MinIO bucket."""
        try:
            metadata = self.client.stat_object(
                bucket_name=self.bucket_name,
                object_name=storage_key.value,
            )
            assert metadata.size is not None
            return StoredFile(
                storage_key=storage_key,
                mime_type=metadata.content_type,
                size_bytes=metadata.size,
                bucket_name=metadata.bucket_name,
                version_id=metadata.version_id,
                etag=metadata.etag,
            )
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                logger.warning(
                    "Object %s not found in bucket %s.",
                    storage_key,
                    self.bucket_name,
                )
                raise ObjectNotFoundException(
                    storage_key=storage_key.value,
                    bucket_name=self.bucket_name,
                ) from exc
            logger.warning(
                "Raised error for key %s in bucket %s. This could be due to an invalid or conflicting function argument.",
                storage_key,
                self.bucket_name,
            )
            raise StorageOperationException(
                f"Failed to get statistical data for object '{storage_key}'."
            ) from exc