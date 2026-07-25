from dataclasses import dataclass
from hashlib import sha256
from typing import BinaryIO
from uuid import UUID


@dataclass(slots=True, frozen=True)
class DocumentStream:
    """
    Domain representation of an incoming document.

    This object is independent of FastAPI's UploadFile and can be created from
    uploads, local files, web crawlers, S3 downloads, etc.
    """

    stream: BinaryIO
    filename: str
    content_type: str | None
    size_bytes: int | None


@dataclass(slots=True, frozen=True)
class StorageKey:
    """
    Canonical object identifier inside blob storage.
    """

    value: str

    @classmethod
    def document(
        cls,
        *,
        tenant_id: UUID,
        document_id: UUID,
        namespace: str = "documents",
        extension: str | None = None,
    ):
        key = f"{tenant_id}/{namespace}/{document_id}"

        if extension:
            key += f".{extension.lstrip('.')}"

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
    mime_type: str
    checksum: DocumentChecksum
    size_bytes: int
    bucket_name: str | None = None
    version_id: str | None = None
    etag: str | None = None