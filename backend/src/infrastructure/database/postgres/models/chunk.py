import typing
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    UUID,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.postgres.base import Base

if typing.TYPE_CHECKING:
    from .document import Document  # noqa: TC004


class DocumentChunk(Base):
    __tablename__ = "document_chunk"

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        primary_key=True,
        index=True,
        # server_default=text("gen_random_uuid()"),  # server-side responsiblity
    )
    document_id = mapped_column(
        ForeignKey("document.document_id", ondelete="CASCADE"),
        index=True,
    )

    # Relationship
    document: Mapped[Document] = relationship(back_populates="document_chunks")

    # Properties
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)  # ordering
    content: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    page_number: Mapped[int | None] = mapped_column(Integer)
    section_title: Mapped[str | None] = mapped_column(String(255))
    chunk_metadata: Mapped[dict[str, typing.Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    # Provenance
    source_locator: Mapped[dict[str, typing.Any]] = mapped_column(
        JSONB,
        default=dict,
    )

    # Deduplication (Required for deduplication)
    chunk_hash: Mapped[str | None] = mapped_column(
        String(64), index=True, nullable=True
    )

    # Bridge to Vector DB (Required for idempotent updates/deletions)
    qdrant_point_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, index=True, nullable=True
    )

    # Bridge to Graph DB (Required for idempotent updates/deletions)
    neo4j_node_id: Mapped[str | None] = mapped_column(
        String(255), index=True, nullable=True
    )

    # Audit information
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk_index"),
        Index("ix_chunk_document_order", "document_id", "chunk_index"),
        Index("ix_chunk_page_number", "page_number"),
        Index("ix_chunk_section_title", "section_title"),
        Index("ix_chunk_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"Chunk("
            f"chunk_id={self.chunk_id!r}, "
            f"document_id={self.document_id!r}, "
            f"chunk_idx={self.chunk_index!r}, "
            f"token_count={self.token_count!r}, "
            f"page_number={self.page_number!r}, "
            f"section_title={self.section_title!r}, "
            f"qdrant_point_id={self.qdrant_point_id!r}, "
            f"neo4j_node_id={self.neo4j_node_id!r}"
            ")"
        )
