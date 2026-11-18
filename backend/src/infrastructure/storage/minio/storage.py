"""MinIO adapter for the StorageProvider port."""

from datetime import timedelta

from minio import Minio, S3Error
from minio.helpers import DictType

from src.domain.documents.dataclasses import StorageKey, StoredFile
from src.domain.documents.storage import StorageProvider
from src.libs.core.logger import get_logger
from src.libs.exceptions.exceptions import (
    AccessDeniedException,
    ApplicationException,
    BucketNotFoundException,
    ObjectNotFoundException,
    StorageOperationException,
)

logger = get_logger("api.infra.minio")

ACCESS_DENIED_CODES = ("AccessDenied", "InvalidAccessKeyId")
METADATA_PREFIX = "x-amz-meta-"


class MinioStorage(StorageProvider):
    """Stores documents in one MinIO bucket. Every S3Error becomes a domain exception."""

    def __init__(self, client: Minio, bucket_name: str) -> None:
        self.client = client
        self.bucket_name = bucket_name

    def _to_domain_error(
        self, exc: S3Error, action: str, object_name: str | None = None
    ) -> ApplicationException:
        """Return the domain exception for the S3 error code of a failed `action`."""
        logger.warning(
            "MinIO failed to %s (%s): %s", action, exc.code, object_name or ""
        )
        if exc.code == "NoSuchBucket":
            return BucketNotFoundException(bucket_name=self.bucket_name)
        if exc.code == "NoSuchKey" and object_name:
            return ObjectNotFoundException(
                storage_key=object_name, bucket_name=self.bucket_name
            )
        if exc.code in ACCESS_DENIED_CODES:
            return AccessDeniedException(bucket_name=self.bucket_name)
        return StorageOperationException(
            self.bucket_name, description=f"Failed to {action}."
        )

    def create_bucket(self) -> None:
        """Create the bucket if it does not exist."""
        try:
            if not self.client.bucket_exists(bucket_name=self.bucket_name):
                self.client.make_bucket(bucket_name=self.bucket_name)
                logger.info("Created bucket %s.", self.bucket_name)
        except S3Error as exc:
            raise self._to_domain_error(exc, "create the bucket") from exc

    def create_presigned_url(
        self,
        storage_key: StorageKey,
        expires_at: timedelta,
        method: str,
        user_metadata: dict[str, str] | None = None,
    ) -> str:
        """Return a presigned URL. Only PUT URLs sign `user_metadata` as 'x-amz-meta-*'."""
        method = method.upper()
        extra_query_params: DictType | None = None
        if user_metadata and method == "PUT":
            extra_query_params = {}
            for key, value in user_metadata.items():
                name = key.lower()
                if not name.startswith(METADATA_PREFIX):
                    name = METADATA_PREFIX + name
                extra_query_params[name] = str(value)

        try:
            return self.client.get_presigned_url(
                method=method,
                bucket_name=self.bucket_name,
                object_name=storage_key.value,
                expires=expires_at,
                extra_query_params=extra_query_params,
            )
        except S3Error as exc:
            raise self._to_domain_error(
                exc, f"sign a {method} URL", storage_key.value
            ) from exc

    def get_obj_metadata(self, storage_key: StorageKey) -> StoredFile:
        """Return the object metadata. An unknown size is reported as -1."""
        try:
            stat = self.client.stat_object(
                bucket_name=self.bucket_name, object_name=storage_key.value
            )
        except S3Error as exc:
            raise self._to_domain_error(
                exc, "read metadata", storage_key.value
            ) from exc
        return StoredFile(
            storage_key=storage_key,
            mime_type=stat.content_type,
            size_bytes=stat.size if stat.size is not None else -1,
            bucket_name=stat.bucket_name,
            version_id=stat.version_id,
            etag=stat.etag,
        )

    def delete_object(self, storage_key: StorageKey) -> None:
        """Delete the object."""
        try:
            self.client.remove_object(
                bucket_name=self.bucket_name, object_name=storage_key.value
            )
        except S3Error as exc:
            raise self._to_domain_error(
                exc, "delete the object", storage_key.value
            ) from exc

    def download_object(self, bucket: str, storage_key: str, file_path: str) -> None:
        """Download the object from `bucket` to the local `file_path`."""
        try:
            self.client.fget_object(bucket, storage_key, file_path=file_path)
        except S3Error as exc:
            raise self._to_domain_error(
                exc, "download the object", storage_key
            ) from exc
        logger.info("Downloaded object %s from bucket %s.", storage_key, bucket)
