from abc import abstractmethod
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

    @abstractmethod
    def create_upload_url(
        self, storage_key: StorageKey, expires_at: timedelta
    ) -> str: ...

    @abstractmethod
    def create_download_url(
        self, storage_key: StorageKey, expires_at: timedelta
    ) -> str: ...

    @abstractmethod
    def create_delete_url(
        self, storage_key: StorageKey, expires_at: timedelta
    ) -> str: ...

    @abstractmethod
    def store_file(
        self,
        file: DocumentStream,
        storage_key: StorageKey,
        checksum: DocumentChecksum | None = None,
    ) -> StoredFile: ...

    @abstractmethod
    def delete_file(
        self,
        storage_key: StorageKey,
    ) -> None: ...
