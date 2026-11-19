import typing
import uuid

from sqlalchemy import UUID, BigInteger, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.postgres.base import Base
from src.infrastructure.database.postgres.models.mixins import (
    SoftDeleteMixin,
    TimestampMixin,
)
from src.libs.enums.document import DocumentStatus, DocumentType, LanguageType
from src.libs.enums.storage import StorageType

if typing.TYPE_CHECKING:
    from .chunk import DocumentChunk  # noqa: TC004
    from .ingestionjob import IngestionJob  # noqa: TC004
    from .tenant import Tenant  # noqa: TC004


class Document(TimestampMixin, SoftDeleteMixin, Base):
    """An uploaded file of one tenant. The bytes live in object storage."""

    __tablename__ = "document"

    document_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenant.tenant_id", ondelete="CASCADE"),
        index=True,
    )

    # Relationship
    tenant: Mapped[Tenant] = relationship(back_populates="documents")
    ingestion_jobs: Mapped[list[IngestionJob]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    document_chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )

    # Document properties
    filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str | None] = mapped_column(String(255))
    document_type: Mapped[DocumentType | None] = mapped_column(
        Enum(DocumentType, name="documenttype", native_enum=True)
    )
    language: Mapped[LanguageType | None] = mapped_column(
        Enum(LanguageType, name="languagetype", native_enum=True),
        default=LanguageType.ENGLISH,  # For now just english
    )
    bucket_name: Mapped[str | None] = mapped_column(Text)
    storage_key: Mapped[str] = mapped_column(Text)
    storage_type: Mapped[StorageType | None] = mapped_column(
        Enum(StorageType, name="storagetype", native_enum=True)
    )

    version_id: Mapped[str | None] = mapped_column(String(255))
    etag: Mapped[str | None] = mapped_column(String(255))
    checksum: Mapped[str | None] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(
        BigInteger, default=-1, server_default="-1"
    )  # -1 space holder for unknown size
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="documentstatus", native_enum=True),
        default=DocumentStatus.UPLOAD_PENDING,
    )

    __table_args__ = (
        Index(
            "ix_document_created_at",
            "created_at",
        ),
        Index(
            "ix_document_status",
            "status",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"Document("
            f"document_id={self.document_id!r}, "
            f"filename={self.filename!r}, "
            f"mime_type={self.mime_type!r}, "
            f"size_bytes={self.size_bytes!r}, "
            f"status={self.status!r}"
            ")"
        )
