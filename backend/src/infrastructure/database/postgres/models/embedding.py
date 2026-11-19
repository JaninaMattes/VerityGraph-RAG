"""Embedding vectors in the source of truth, so Qdrant can be rebuilt by copying.

Postgres only stores the vectors; Qdrant searches them. One row embeds exactly one
target (a chunk, an entity description or a community report) with one model.
"""

import uuid

from sqlalchemy import (
    ARRAY,
    REAL,
    UUID,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.postgres.base import Base
from src.infrastructure.database.postgres.models.mixins import CreatedAtMixin


class Embedding(CreatedAtMixin, Base):
    """The vector of one target, made by the model that config_id names."""

    __tablename__ = "embedding"

    embedding_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenant.tenant_id", ondelete="CASCADE")
    )
    config_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pipeline_config.config_id", ondelete="RESTRICT")
    )
    # Exactly one target is set (ck_embedding_one_target). Real foreign keys keep
    # the vectors consistent: deleting the target deletes its vectors.
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_chunk.chunk_id", ondelete="CASCADE")
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("entity.entity_id", ondelete="CASCADE")
    )
    community_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("community_report.community_id", ondelete="CASCADE")
    )
    dimensions: Mapped[int] = mapped_column(Integer)
    vector: Mapped[list[float]] = mapped_column(ARRAY(REAL))
    # SHA-256 of the embedded text: a changed text marks the vector as stale.
    content_hash: Mapped[str] = mapped_column(String(64))

    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(chunk_id, entity_id, community_id) = 1",
            name="ck_embedding_one_target",
        ),
        CheckConstraint(
            "dimensions > 0 AND cardinality(vector) = dimensions",
            name="ck_embedding_dimensions",
        ),
        UniqueConstraint("config_id", "chunk_id", name="uq_embedding_chunk"),
        UniqueConstraint("config_id", "entity_id", name="uq_embedding_entity"),
        UniqueConstraint("config_id", "community_id", name="uq_embedding_community"),
    )
