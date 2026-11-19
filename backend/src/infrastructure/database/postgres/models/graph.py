"""The knowledge graph in the source of truth (after Microsoft GraphRAG).

Entities and relationships are tenant-wide (merged across documents). Every
mention and every piece of relationship evidence points to the chunk it was
extracted from, so each node and edge can be traced back to the source text.
Neo4j holds a projection of these tables and can be rebuilt from them.
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.postgres.base import Base
from src.infrastructure.database.postgres.models.mixins import (
    CreatedAtMixin,
    TimestampMixin,
)

CHUNK_FK = "document_chunk.chunk_id"
CONFIG_FK = "pipeline_config.config_id"
ENTITY_FK = "entity.entity_id"
TENANT_FK = "tenant.tenant_id"


class Entity(TimestampMixin, Base):
    """A real-world thing (company, person, product, ...) of one tenant."""

    __tablename__ = "entity"

    entity_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(TENANT_FK, ondelete="CASCADE")
    )
    type: Mapped[str] = mapped_column(String(64))  # for example 'COMPANY'
    name: Mapped[str] = mapped_column(Text)
    # Lower case, without punctuation: the key for entity resolution.
    normalized_name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    aliases: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=list, server_default="{}"
    )
    # Identifiers from other systems, for example {"ticker": "MSFT", "cik": "789019"}.
    external_ids: Mapped[dict[str, typing.Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "type", "normalized_name", name="uq_entity_tenant_type_name"
        ),
    )


class EntityMention(CreatedAtMixin, Base):
    """One place in a chunk where an extractor found an entity."""

    __tablename__ = "entity_mention"

    mention_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(ENTITY_FK, ondelete="CASCADE")
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(CHUNK_FK, ondelete="CASCADE")
    )
    config_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(CONFIG_FK, ondelete="RESTRICT")
    )
    mention_text: Mapped[str] = mapped_column(Text)
    char_start: Mapped[int | None] = mapped_column(Integer)
    char_end: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (
        Index("ix_mention_entity_id", "entity_id"),
        Index("ix_mention_chunk_id", "chunk_id"),
        CheckConstraint(
            "(char_start IS NULL) = (char_end IS NULL)"
            " AND (char_start IS NULL OR (0 <= char_start AND char_start <= char_end))",
            name="ck_mention_char_range",
        ),
        CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0 AND 1",
            name="ck_mention_confidence",
        ),
    )


class EntityRelationship(TimestampMixin, Base):
    """A typed, directed edge between two entities of one tenant."""

    __tablename__ = "entity_relationship"

    relationship_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(TENANT_FK, ondelete="CASCADE")
    )
    source_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(ENTITY_FK, ondelete="CASCADE")
    )
    target_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(ENTITY_FK, ondelete="CASCADE")
    )
    type: Mapped[str] = mapped_column(String(64))  # for example 'INVESTS_IN'
    description: Mapped[str | None] = mapped_column(Text)
    # Strength of the edge, for example the number of supporting chunks.
    weight: Mapped[float] = mapped_column(Float, default=1.0, server_default="1")

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "source_entity_id",
            "target_entity_id",
            "type",
            name="uq_relationship_edge",
        ),
        Index("ix_relationship_target", "target_entity_id"),
    )


class RelationshipEvidence(CreatedAtMixin, Base):
    """A chunk that supports a relationship. An edge needs at least one row here."""

    __tablename__ = "relationship_evidence"

    relationship_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entity_relationship.relationship_id", ondelete="CASCADE"),
        primary_key=True,
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(CHUNK_FK, ondelete="CASCADE"), primary_key=True
    )
    config_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(CONFIG_FK, ondelete="RESTRICT"), primary_key=True
    )
    description: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (
        Index("ix_evidence_chunk_id", "chunk_id"),
        CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0 AND 1",
            name="ck_evidence_confidence",
        ),
    )


class Community(CreatedAtMixin, Base):
    """A cluster of entities on one level of the hierarchy (for example Leiden)."""

    __tablename__ = "community"

    community_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(TENANT_FK, ondelete="CASCADE")
    )
    config_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(CONFIG_FK, ondelete="RESTRICT")
    )
    level: Mapped[int] = mapped_column(Integer)  # 0 = the coarsest level
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("community.community_id", ondelete="CASCADE")
    )

    __table_args__ = (
        Index("ix_community_tenant_level", "tenant_id", "config_id", "level"),
        CheckConstraint("level >= 0", name="ck_community_level"),
    )


class CommunityMember(Base):
    """An entity that belongs to a community."""

    __tablename__ = "community_member"

    community_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("community.community_id", ondelete="CASCADE"), primary_key=True
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(ENTITY_FK, ondelete="CASCADE"), primary_key=True
    )

    __table_args__ = (Index("ix_member_entity_id", "entity_id"),)


class CommunityReport(CreatedAtMixin, Base):
    """The LLM summary of a community, used for global search."""

    __tablename__ = "community_report"

    community_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("community.community_id", ondelete="CASCADE"), primary_key=True
    )
    config_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(CONFIG_FK, ondelete="RESTRICT")
    )
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    full_content: Mapped[str] = mapped_column(Text)
    # [{"summary": ..., "explanation": ...}, ...] as in GraphRAG.
    findings: Mapped[list[dict[str, typing.Any]]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    rank: Mapped[float | None] = mapped_column(Float)  # importance, for ordering
