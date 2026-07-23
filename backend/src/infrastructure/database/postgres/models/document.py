from datetime import datetime
import typing
import uuid
from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UUID,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.postgres.models.base import Base
from src.shared.enums import DocumentStatus, DocumentType, Language, StorageProvider

if typing.TYPE_CHECKING:
    from .tenant import Tenant


class Document(Base):
    __tablename__ = "document"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        primary_key=True,
        server_default=text("gen_random_uuid()"),  # server-side responsiblity
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.tenant_id"))
    tenant: Mapped["Tenant"] = relationship(back_populates="documents")

    # File details
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type: Mapped[DocumentType | None] = mapped_column(
        Enum(DocumentType, native_enum=True)
    )
    language: Mapped[Language | None] = mapped_column(Enum(Language, native_enum=True))

    bucket_name: Mapped[str | None] = mapped_column(Text)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    storage_provider: Mapped[StorageProvider | None] = mapped_column(
        Enum(StorageProvider, native_enum=True)
    )
    version_id: Mapped[str | None] = mapped_column(Integer)
    etag: Mapped[str | None] = mapped_column(String(55))

    checksum: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=-1)  # -1 unknown size

    # Status information
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, native_enum=True), default=DocumentStatus.UPLOADED
    )

    # Audit information
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=None, onupdate=func.now()
    )
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID,
        default=None,
    )

    __table_args__ = (
        Index(
            "idx_documents_tenant_status",
            "tenant_id",
            "status",
        ),
        Index(
            "idx_documents_created",
            "created_at",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"DocumentEntity("
            f"document_id={self.document_id!r}, "
            f"tenant_id={self.tenant_id!r}, "
            f"filename={self.filename!r}, "
            f"status={self.status.value!r})"
        )
