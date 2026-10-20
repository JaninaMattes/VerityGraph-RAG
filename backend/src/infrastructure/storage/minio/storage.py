from datetime import timedelta

from minio import Minio, S3Error
from minio.helpers import DictType
from minio.sse import SseCustomerKey

from src.domain.documents.dataclasses import (
    StorageKey,
    StoredFile,
)
from src.infrastructure.storage.provider import StorageProvider
from src.libs.core.logger import get_logger
from src.libs.exceptions.exceptions import (
    AccessDeniedException,
    BucketNotFoundException,
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
            if exc.code in ("AccessDenied", "InvalidAccessKeyId"):
                logger.warning(
                    "Access to bucket %s denied due to missing permissions or bad credentials.",
                    self.bucket_name,
                )
                raise AccessDeniedException(
                    bucket_name=self.bucket_name,
                ) from exc
            logger.warning(
                "Failed creating bucket %s.",
                self.bucket_name,
            )
            raise StorageOperationException(
                self.bucket_name,
                description=f"Creating bucket '{self.bucket_name}' failed.",
            ) from exc

    def create_presigned_url(
        self,
        storage_key: StorageKey,
        expires_at: timedelta,
        method: str,
        user_metadata: dict[str, str] | None = None,
    ) -> str:
        """
        Generate a presigned URL for an object in storage.

        :param storage_key: The canonical storage key dataclass.
        :param expires_at: Expiration time for the URL.
        :param method: HTTP method (e.g., "PUT" or "GET").
        :param user_metadata: Optional metadata to be cryptographically signed
                              into the URL (only applicable for "PUT").
        :return: The presigned URL string.
        """
        normalized_method = method.upper()
        extra_query_params: DictType | None = None

        if user_metadata and normalized_method == "PUT":
            extra_query_params = {
                (
                    k.lower()
                    if k.lower().startswith("x-amz-meta-")
                    else f"x-amz-meta-{k.lower()}"
                ): str(v)
                for k, v in user_metadata.items()
            }

        try:
            return self.client.get_presigned_url(
                method=method,
                bucket_name=self.bucket_name,
                object_name=storage_key.value,
                expires=expires_at,
                extra_query_params=extra_query_params,
            )
        except S3Error as exc:
            if exc.code == "NoSuchBucket":
                logger.warning(
                    "The specified bucket %s does not exist.",
                    self.bucket_name,
                )
                raise BucketNotFoundException(bucket_name=self.bucket_name)
            if exc.code == "NoSuchKey":
                logger.warning(
                    "The specified object key %s does not exist in the bucket %s.",
                    storage_key,
                    self.bucket_name,
                )
                raise ObjectNotFoundException(
                    storage_key=storage_key.value,
                    bucket_name=self.bucket_name,
                ) from exc
            logger.warning(
                "Failed generating presigned %s URL for object %s from bucket %s.",
                method,
                storage_key,
                self.bucket_name,
            )
            raise StorageOperationException(
                self.bucket_name,
                description=f"Generation of presigned '{method}' URL for object '{storage_key}' failed.",
            ) from exc

    def get_obj_metadata(
        self,
        storage_key: StorageKey,
    ) -> StoredFile:
        """Get 'bucket-object' information from MinIO bucket.
        :param storage_key: The object key of the file to get information from
        :return: 'bucket-object' meta information
        """
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
                    "The specified object key %s does not exist in the bucket %s.",
                    storage_key,
                    self.bucket_name,
                )
                raise ObjectNotFoundException(
                    storage_key=storage_key.value,
                    bucket_name=self.bucket_name,
                ) from exc
            logger.warning(
                "Failed to extract statistical data for object %s from bucket %s.",
                storage_key,
                self.bucket_name,
            )
            raise StorageOperationException(
                self.bucket_name,
                description=f"Gathering statistical data for '{storage_key}' failed.",
            ) from exc

    def delete_object(self, storage_key: StorageKey) -> None:
        """Delete file from S3 bucket.

        :param storage_key: The object key of the file to delete
        """
        try:
            self.client.remove_object(
                bucket_name=self.bucket_name,
                object_name=storage_key.value,
            )
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                logger.warning(
                    "Object %s does not exist in bucket %s.",
                    storage_key,
                    self.bucket_name,
                )
                raise ObjectNotFoundException(
                    storage_key=storage_key.value,
                    bucket_name=self.bucket_name,
                ) from exc

            if exc.code in ("AccessDenied", "InvalidAccessKeyId"):
                logger.warning(
                    "Access denied while deleting %s from bucket %s.",
                    storage_key,
                    self.bucket_name,
                )
                raise AccessDeniedException(
                    bucket_name=self.bucket_name,
                ) from exc
            logger.warning(
                "Failed deleting object %s from bucket %s.",
                storage_key,
                self.bucket_name,
            )
            raise StorageOperationException(
                self.bucket_name,
                description=f"Deleting object '{storage_key}' failed.",
            ) from exc

    def download_object(self, bucket: str, storage_key: str, file_path: str) -> None:
        """Download file from S3 bucket to local file system.
        :param bucket: The bucket name.
        :param storage_key: The storage key.
        :param target_path: The temporary target path.
        """
        try:
            self.client.fget_object(bucket, storage_key, file_path=file_path)
            logger.info(
                "Downloaded object %s from bucket %s to %s.",
                storage_key,
                bucket,
                file_path,
            )
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                logger.warning(
                    "Object %s does not exist in bucket %s.",
                    storage_key,
                    self.bucket_name,
                )
                raise ObjectNotFoundException(
                    storage_key=storage_key,
                    bucket_name=self.bucket_name,
                ) from exc
