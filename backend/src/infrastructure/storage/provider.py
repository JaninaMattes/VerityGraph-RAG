from datetime import timedelta
from typing import Protocol

from src.domain.documents.dataclasses import (
    StorageKey,
    StoredFile,
)


class StorageProvider(Protocol):
    """Decouple specific service (e.g. MinIO, AWS S3 etc.)"""

    def create_bucket(self) -> None: ...

    def create_presigned_url(
        self, storage_key: StorageKey, expires_at: timedelta, method: str
    ) -> str: ...

    def get_obj_metadata(
        self,
        storage_key: StorageKey,
    ) -> StoredFile: ...

    def delete_object(self, storage_key: StorageKey) -> None: ...