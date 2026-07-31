import typing
import uuid
from datetime import UTC, datetime

from sqlalchemy import UUID, BigInteger, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.postgres.base import Base
from src.shared.enums import (
    DocumentStatus,
    DocumentType,
    LanguageType,
    StorageProvider,
)

if typing.TYPE_CHECKING:
    from .tenant import Tenant  # noqa: TC004


class Document(Base):
    __tablename__ = "document"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        primary_key=True,
        index=True,
        # server_default=text("gen_random_uuid()"),  # server-side responsiblity
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenant.tenant_id", ondelete="CASCADE"),
        index=True,
    )

    # Relationship
    tenant: Mapped[Tenant] = relationship(back_populates="documents")

    # File details
    filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str | None] = mapped_column(String(255))
    document_type: Mapped[DocumentType | None] = mapped_column(
        Enum(DocumentType, name="documenttype", native_enum=True)
    )
    language: Mapped[LanguageType | None] = mapped_column(
        Enum(LanguageType, name="languagetype", native_enum=True)
    )
    bucket_name: Mapped[str | None] = mapped_column(Text)
    storage_key: Mapped[str] = mapped_column(Text)
    storage_provider: Mapped[StorageProvider | None] = mapped_column(
        Enum(StorageProvider, name="storageprovider", native_enum=True)
    )

    version_id: Mapped[str | None] = mapped_column(String(255))
    etag: Mapped[str | None] = mapped_column(String(255))
    checksum: Mapped[str | None] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(
        BigInteger, default=-1, server_default="-1"
    )  # -1 unknown size
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="documentstatus", native_enum=True),
        default=DocumentStatus.UPLOAD_PENDING,
    )

    # Audit information
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(UUID)

    # __table_args__ = (
    #     Index(
    #         "idx_documents_tenant_status",
    #         "tenant_id",
    #         "status",
    #     ),
    #     Index(
    #         "idx_documents_created",
    #         "created_at",
    #     ),
    # )

    def __repr__(self) -> str:
        return f"DocumentEntity(document_id={self.document_id!r}, filename={self.filename!s}"
