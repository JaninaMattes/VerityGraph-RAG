"""Storage port: the object-storage operations that the domain needs.

Adapters (for example MinIO) implement this protocol in the infrastructure layer.
All methods are blocking; async callers run them with asyncio.to_thread.
"""

from datetime import timedelta
from typing import Protocol

from src.domain.documents.dataclasses import StorageKey, StoredFile


class StorageProvider(Protocol):
    """Object storage for documents (MinIO, AWS S3, ...).

    Errors: BucketNotFoundException, ObjectNotFoundException,
    StorageAccessDeniedException or StorageException.
    """

    def create_bucket(self) -> None:
        """Create the configured bucket if it does not exist."""
        raise NotImplementedError

    def check_available(self) -> None:
        """Return if the configured bucket is reachable; raise a storage error if not."""
        raise NotImplementedError

    def create_presigned_url(
        self,
        storage_key: StorageKey,
        expires_at: timedelta,
        method: str,
        user_metadata: dict[str, str] | None = None,
    ) -> str:
        """Return a URL that allows `method` ('PUT' or 'GET') on the object until expiry.

        For PUT, `user_metadata` is signed into the URL as 'x-amz-meta-*' values.
        """
        raise NotImplementedError

    def get_obj_metadata(self, storage_key: StorageKey) -> StoredFile:
        """Return size, type, version and ETag of the stored object."""
        raise NotImplementedError

    def delete_object(self, storage_key: StorageKey) -> None:
        """Delete the stored object."""
        raise NotImplementedError

    def download_object(self, bucket: str, storage_key: str, file_path: str) -> None:
        """Download the object to the local `file_path`."""
        raise NotImplementedError
