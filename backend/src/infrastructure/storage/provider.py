from datetime import timedelta
from typing import Protocol

from src.domain.documents.dataclasses import (
    StorageKey,
    StoredFile,
)


class StorageProvider(Protocol):
    """Decouple specific service (e.g. MinIO, AWS S3 etc.)"""

    def create_bucket(self) -> None:
        raise NotImplementedError("Subclasses must implement create_bucket method")

    def create_presigned_url(
        self, storage_key: StorageKey, expires_at: timedelta, method: str
    ) -> str:
        raise NotImplementedError(
            "Subclasses must implement create_presigned_url method"
        )

    def get_obj_metadata(
        self,
        storage_key: StorageKey,
    ) -> StoredFile:
        raise NotImplementedError("Subclasses must implement get_obj_metadata method")

    def delete_object(self, storage_key: StorageKey) -> None:
        raise NotImplementedError("Subclasses must implement delete_object method")