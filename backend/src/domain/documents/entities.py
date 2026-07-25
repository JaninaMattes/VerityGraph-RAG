from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from src.domain.documents.dataclasses import DocumentChecksum, StorageKey
from src.shared.enums import DocumentStatus, DocumentType, Language, StorageProvider


class DocumentEntity:
    """
    Domain representation of a document.

    This object lives inside the business layer and is independent of
    FastAPI, SQLAlchemy, or Pydantic.
    """

    def __init__(
        self,
        *,
        document_id: UUID,
        tenant_id: UUID,
        filename: str,
        mime_type: str | None = None,
        document_type: DocumentType | None = None,
        language: Language | None = None,
        bucket_name: str | None = None,
        storage_key: StorageKey,
        storage_provider: StorageProvider | None = None,
        version_id: str | None = None,
        etag: str | None = None,
        checksum: DocumentChecksum | None = None,
        size_bytes: int,
        status: DocumentStatus,
        created_at: datetime,
        updated_at: datetime,
        deleted_at: datetime | None = None,
        deleted_by: UUID | None = None,
    ) -> None:
        # Identity
        self.document_id = document_id
        self.tenant_id = tenant_id

        # Upload information
        self.filename = filename
        self.mime_type = mime_type
        self.document_type = document_type
        self.language = language

        self.storage_key = storage_key
        self.bucket_name = bucket_name
        self.storage_provider = storage_provider
        self.version_id = version_id
        self.etag = etag

        self.checksum = checksum
        self.size_bytes = size_bytes
        self.status = status

        # Audit
        self.created_at = created_at
        self.updated_at = updated_at
        self.deleted_at = deleted_at
        self.deleted_by = deleted_by

    @classmethod
    def create_pending(
        cls,
        *,
        document_id: UUID,
        tenant_id: UUID,
        storage_key: StorageKey,
    ) -> DocumentEntity:
        now = datetime.now(UTC)

        return cls(
            document_id=document_id,
            tenant_id=tenant_id,
            filename="",
            mime_type=None,
            document_type=None,
            language=None,
            storage_key=storage_key,
            bucket_name=None,
            storage_provider=None,
            version_id=None,
            etag=None,
            checksum=None,
            size_bytes=0,
            status=DocumentStatus.PENDING,
            created_at=now,
            updated_at=now,
        )

    def mark_processing(self) -> None:
        self.status = DocumentStatus.PROCESSING
        self.updated_at = datetime.now(UTC)

    def mark_ready(
        self,
        *,
        language: Language,
        parser_version: str,
        embedding_version: str,
    ) -> None:
        self.status = DocumentStatus.READY
        self.language = language
        self.updated_at = datetime.now(UTC)

    def mark_failed(self) -> None:
        self.status = DocumentStatus.FAILED
        self.updated_at = datetime.now(UTC)

    def mark_deleted(self, tenant_id: UUID) -> None:
        self.status = DocumentStatus.DELETED
        self.deleted_at = datetime.now(UTC)
        self.deleted_by = tenant_id

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DocumentEntity):
            return NotImplemented
        return self.document_id == other.document_id

    def __hash__(self) -> int:
        return hash(self.document_id)

    def __repr__(self) -> str:
        return (
            f"DocumentEntity("
            f"document_id={self.document_id!r}, "
            f"tenant_id={self.tenant_id!r}, "
            f"filename={self.filename!r}, "
            f"status={self.status.value!r})"
        )
