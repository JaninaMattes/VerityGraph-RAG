import re
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from src.shared.enums.document import DocumentStatus, DocumentType, LanguageType
from src.shared.enums.storage import StorageProvider


@dataclass(slots=True, frozen=True)
class StorageKey:
    """
    Canonical object identifier inside blob storage.
    Follows S3/MinIO best practices for lifecycle management and tenant isolation.
    """

    value: str

    @classmethod
    def document(
        cls,
        *,
        document_id: UUID,
        tenant_id: UUID,
        namespace: str,
        original_filename: str | None = None,  # allows to infer extension
    ) -> "StorageKey":
        now = datetime.now(UTC)
        # Clean namespace
        namespace = re.sub(r"[^a-zA-Z0-9\-]", "", namespace).lower() or "files"
        key = f"{tenant_id}/{namespace}/{now.year}/{now.month:02d}/{document_id}"

        # Handle optional extension
        if original_filename:
            ext = (
                original_filename.rsplit(".", 1)[-1]
                if "." in original_filename
                else None
            )
            if ext:
                safe_ext = re.sub(r"[^a-zA-Z0-9]", "", ext).lower()
                if safe_ext:
                    key += f".{safe_ext}"

        return cls(key)


@dataclass(slots=True, frozen=True)
class DocumentChecksum:
    """
    SHA-256 checksum of a document.
    """

    value: str

    @classmethod
    def from_hex(cls, value: str):
        return cls(value.lower())

    @classmethod
    def from_bytes(cls, data: bytes):
        digest = sha256(data).hexdigest()
        return cls(digest)

    def __str__(self) -> str:
        return self.value


@dataclass(slots=True, frozen=True)
class StoredFile:
    """
    Result returned by the storage provider after a successful upload.
    """

    storage_key: StorageKey
    mime_type: str | None
    size_bytes: int
    bucket_name: str | None
    version_id: str | None
    etag: str | None


@dataclass(slots=True, frozen=True)
class Document:
    filename: str
    mime_type: str
    size_bytes: int
    bucket_name: str
    storage_provider: StorageProvider
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime
    checksum: DocumentChecksum | None
    document_type: DocumentType | None
    language: LanguageType | None
    version_id: str | None
    etag: str | None
