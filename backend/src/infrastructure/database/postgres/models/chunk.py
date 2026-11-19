"""Chunks (text units) and their evidence spans: the base of all provenance.

Embeddings, entity mentions and relationship evidence refer to chunk_id. Deleting a
chunk deletes everything derived from it (ON DELETE CASCADE).
"""

import typing
import uuid

from sqlalchemy import (
    ARRAY,
    UUID,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.postgres.base import Base
from src.infrastructure.database.postgres.models.mixins import CreatedAtMixin

if typing.TYPE_CHECKING:
    from .document import Document  # noqa: TC004


class DocumentChunk(CreatedAtMixin, Base):
    """One chunk of a document. Rows are immutable: re-chunking replaces them."""

    __tablename__ = "document_chunk"

    chunk_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document.document_id", ondelete="CASCADE")
    )
    # Copied from the document, so every store can filter by tenant without a join.
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenant.tenant_id", ondelete="CASCADE")
    )
    # How the chunk was made (parser, version, tokenizer, parameters).
    config_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pipeline_config.config_id", ondelete="RESTRICT")
    )

    document: Mapped[Document] = relationship(back_populates="document_chunks")
    spans: Mapped[list["DocumentChunkSpan"]] = relationship(
        back_populates="chunk",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DocumentChunkSpan.span_index",
    )

    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))  # SHA-256 hex of content
    token_count: Mapped[int] = mapped_column(Integer)
    headings: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=list, server_default="{}"
    )
    # Derived from the spans; stored for page filters and citations.
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunk_document_index"),
        Index("ix_chunk_tenant_content_hash", "tenant_id", "content_hash"),
        Index("ix_chunk_config_id", "config_id"),
        CheckConstraint("chunk_index >= 0", name="ck_chunk_index"),
        CheckConstraint("token_count >= 0", name="ck_chunk_token_count"),
        CheckConstraint("page_start <= page_end", name="ck_chunk_page_range"),
    )

    def __repr__(self) -> str:
        return (
            f"DocumentChunk("
            f"chunk_id={self.chunk_id!r}, "
            f"document_id={self.document_id!r}, "
            f"chunk_index={self.chunk_index!r}, "
            f"page_start={self.page_start!r}, "
            f"page_end={self.page_end!r}"
            ")"
        )


class DocumentChunkSpan(Base):
    """Where one part of a chunk comes from: page, box and character range."""

    __tablename__ = "chunk_span"

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_chunk.chunk_id", ondelete="CASCADE"), primary_key=True
    )
    span_index: Mapped[int] = mapped_column(Integer, primary_key=True)

    chunk: Mapped[DocumentChunk] = relationship(back_populates="spans")

    source_ref: Mapped[str] = mapped_column(String(255))  # for example '#/texts/12'
    label: Mapped[str] = mapped_column(String(64))  # for example 'text', 'table'
    page_no: Mapped[int | None] = mapped_column(Integer)
    bbox_left: Mapped[float | None] = mapped_column(Float)
    bbox_top: Mapped[float | None] = mapped_column(Float)
    bbox_right: Mapped[float | None] = mapped_column(Float)
    bbox_bottom: Mapped[float | None] = mapped_column(Float)
    bbox_origin: Mapped[str | None] = mapped_column(String(16))
    char_start: Mapped[int | None] = mapped_column(Integer)
    char_end: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        CheckConstraint("page_no >= 1", name="ck_span_page_no"),
        CheckConstraint(
            "(char_start IS NULL) = (char_end IS NULL)"
            " AND (char_start IS NULL OR (0 <= char_start AND char_start <= char_end))",
            name="ck_span_char_range",
        ),
        CheckConstraint(
            "(bbox_left IS NULL) = (bbox_origin IS NULL)", name="ck_span_bbox"
        ),
    )
