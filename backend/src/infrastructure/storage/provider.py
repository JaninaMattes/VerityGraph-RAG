from datetime import timedelta
from typing import Protocol

from src.domain.documents.dataclasses import (
    DocumentChecksum,
    DocumentStream,
    StorageKey,
    StoredFile,
)


class StorageProvider(Protocol):
    """Decouple specific service (e.g. MinIO, AWS S3 etc.)"""

    def create_upload_url(
        self, storage_key: StorageKey, expires_at: timedelta
    ) -> str: ...

    def create_download_url(
        self, storage_key: StorageKey, expires_at: timedelta
    ) -> str: ...

    def create_delete_url(
        self, storage_key: StorageKey, expires_at: timedelta
    ) -> str: ...

    def store_file(
        self,
        file: DocumentStream,
        storage_key: StorageKey,
        checksum: DocumentChecksum | None = None,
    ) -> StoredFile: ...

    def delete_file(
        self,
        storage_key: StorageKey,
    ) -> None: ...
