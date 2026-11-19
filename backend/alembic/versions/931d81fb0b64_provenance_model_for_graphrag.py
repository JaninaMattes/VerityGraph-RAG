"""Provenance model for GraphRAG: chunks, spans, graph, embeddings.

Postgres becomes the source of truth from which Neo4j and Qdrant can be rebuilt:
- document_chunk is rebuilt (tenant, config, hash, headings, page range) and gets
  chunk_span for page and box evidence. The old table was never written to; the
  upgrade stops if it holds rows, so no data is dropped silently.
- pipeline_config records how chunks, mentions and vectors were produced.
- entity, entity_mention, entity_relationship, relationship_evidence, community,
  community_member and community_report hold the graph (after Microsoft GraphRAG).
- embedding stores vectors, so a Qdrant rebuild is a copy.
- Clean-up: redundant indexes are dropped, users.email is unique per tenant, and the
  audit columns get server defaults.

Revision ID: 931d81fb0b64
Revises: 85002e92591a
Create Date: 2026-11-19 10:41:14.372308
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "931d81fb0b64"
down_revision: str | Sequence[str] | None = "85002e92591a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tables with audit columns: (table, has updated_at).
AUDITED_TABLES = [
    ("tenant", True),
    ("users", True),
    ("credentials", True),
    ("document", True),
    ("ingestion_job", True),
]
# Indexes that duplicate a primary key or a unique constraint, or are never used.
REDUNDANT_INDEXES = [
    ("ix_tenant_tenant_id", "tenant", ["tenant_id"]),
    ("ix_users_user_id", "users", ["user_id"]),
    ("ix_credentials_credentials_id", "credentials", ["credentials_id"]),
    ("ix_document_document_id", "document", ["document_id"]),
    ("ix_ingestion_job_job_id", "ingestion_job", ["job_id"]),
    ("ix_job_workflow_run_id", "ingestion_job", ["workflow_run_id"]),
    ("ix_job_attempt_count", "ingestion_job", ["attempt_count"]),
]
CHAR_RANGE = (
    "(char_start IS NULL) = (char_end IS NULL)"
    " AND (char_start IS NULL OR (0 <= char_start AND char_start <= char_end))"
)
NOW = sa.text("now()")


def created_at() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False
    )


def updated_at() -> sa.Column:
    return sa.Column(
        "updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False
    )


def fail_if_rows(table: str, reason: str) -> None:
    """Stop the migration if `table` has rows, instead of dropping them."""
    op.execute(
        f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM {table}) THEN "
        f"RAISE EXCEPTION '{table} is not empty: {reason}'; END IF; END $$;"
    )


def upgrade() -> None:
    fail_if_rows("document_chunk", "delete the old chunks before this upgrade")
    op.drop_table("document_chunk")

    op.create_table(
        "pipeline_config",
        sa.Column("config_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("component", sa.String(length=255), nullable=False),
        sa.Column("component_version", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column(
            "parameters",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("config_hash", sa.String(length=64), nullable=False),
        created_at(),
        sa.PrimaryKeyConstraint("config_id"),
        sa.UniqueConstraint("kind", "config_hash", name="uq_pipeline_config_hash"),
    )

    op.create_table(
        "document_chunk",
        sa.Column("chunk_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("config_id", sa.UUID(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("headings", sa.ARRAY(sa.Text()), server_default="{}", nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        created_at(),
        sa.CheckConstraint("chunk_index >= 0", name="ck_chunk_index"),
        sa.CheckConstraint("token_count >= 0", name="ck_chunk_token_count"),
        sa.CheckConstraint("page_start <= page_end", name="ck_chunk_page_range"),
        sa.ForeignKeyConstraint(
            ["document_id"], ["document.document_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenant.tenant_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["config_id"], ["pipeline_config.config_id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("chunk_id"),
        sa.UniqueConstraint(
            "document_id", "chunk_index", name="uq_chunk_document_index"
        ),
    )
    op.create_index("ix_chunk_config_id", "document_chunk", ["config_id"])
    op.create_index(
        "ix_chunk_tenant_content_hash", "document_chunk", ["tenant_id", "content_hash"]
    )

    op.create_table(
        "chunk_span",
        sa.Column("chunk_id", sa.UUID(), nullable=False),
        sa.Column("span_index", sa.Integer(), nullable=False),
        sa.Column("source_ref", sa.String(length=255), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("page_no", sa.Integer(), nullable=True),
        sa.Column("bbox_left", sa.Float(), nullable=True),
        sa.Column("bbox_top", sa.Float(), nullable=True),
        sa.Column("bbox_right", sa.Float(), nullable=True),
        sa.Column("bbox_bottom", sa.Float(), nullable=True),
        sa.Column("bbox_origin", sa.String(length=16), nullable=True),
        sa.Column("char_start", sa.Integer(), nullable=True),
        sa.Column("char_end", sa.Integer(), nullable=True),
        sa.CheckConstraint("page_no >= 1", name="ck_span_page_no"),
        sa.CheckConstraint(CHAR_RANGE, name="ck_span_char_range"),
        sa.CheckConstraint(
            "(bbox_left IS NULL) = (bbox_origin IS NULL)", name="ck_span_bbox"
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id"], ["document_chunk.chunk_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("chunk_id", "span_index"),
    )

    op.create_table(
        "entity",
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("normalized_name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("aliases", sa.ARRAY(sa.Text()), server_default="{}", nullable=False),
        sa.Column(
            "external_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        created_at(),
        updated_at(),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenant.tenant_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("entity_id"),
        sa.UniqueConstraint(
            "tenant_id", "type", "normalized_name", name="uq_entity_tenant_type_name"
        ),
    )

    op.create_table(
        "entity_mention",
        sa.Column("mention_id", sa.UUID(), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("chunk_id", sa.UUID(), nullable=False),
        sa.Column("config_id", sa.UUID(), nullable=False),
        sa.Column("mention_text", sa.Text(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=True),
        sa.Column("char_end", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        created_at(),
        sa.CheckConstraint(CHAR_RANGE, name="ck_mention_char_range"),
        sa.CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0 AND 1",
            name="ck_mention_confidence",
        ),
        sa.ForeignKeyConstraint(
            ["entity_id"], ["entity.entity_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id"], ["document_chunk.chunk_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["config_id"], ["pipeline_config.config_id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("mention_id"),
    )
    op.create_index("ix_mention_entity_id", "entity_mention", ["entity_id"])
    op.create_index("ix_mention_chunk_id", "entity_mention", ["chunk_id"])

    op.create_table(
        "entity_relationship",
        sa.Column("relationship_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("source_entity_id", sa.UUID(), nullable=False),
        sa.Column("target_entity_id", sa.UUID(), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("weight", sa.Float(), server_default="1", nullable=False),
        created_at(),
        updated_at(),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenant.tenant_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source_entity_id"], ["entity.entity_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["target_entity_id"], ["entity.entity_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("relationship_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "source_entity_id",
            "target_entity_id",
            "type",
            name="uq_relationship_edge",
        ),
    )
    op.create_index(
        "ix_relationship_target", "entity_relationship", ["target_entity_id"]
    )

    op.create_table(
        "relationship_evidence",
        sa.Column("relationship_id", sa.UUID(), nullable=False),
        sa.Column("chunk_id", sa.UUID(), nullable=False),
        sa.Column("config_id", sa.UUID(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        created_at(),
        sa.CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0 AND 1",
            name="ck_evidence_confidence",
        ),
        sa.ForeignKeyConstraint(
            ["relationship_id"],
            ["entity_relationship.relationship_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id"], ["document_chunk.chunk_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["config_id"], ["pipeline_config.config_id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("relationship_id", "chunk_id", "config_id"),
    )
    op.create_index("ix_evidence_chunk_id", "relationship_evidence", ["chunk_id"])

    op.create_table(
        "community",
        sa.Column("community_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("config_id", sa.UUID(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.UUID(), nullable=True),
        created_at(),
        sa.CheckConstraint("level >= 0", name="ck_community_level"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenant.tenant_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["config_id"], ["pipeline_config.config_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["community.community_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("community_id"),
    )
    op.create_index(
        "ix_community_tenant_level", "community", ["tenant_id", "config_id", "level"]
    )

    op.create_table(
        "community_member",
        sa.Column("community_id", sa.UUID(), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["community_id"], ["community.community_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["entity_id"], ["entity.entity_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("community_id", "entity_id"),
    )
    op.create_index("ix_member_entity_id", "community_member", ["entity_id"])

    op.create_table(
        "community_report",
        sa.Column("community_id", sa.UUID(), nullable=False),
        sa.Column("config_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("full_content", sa.Text(), nullable=False),
        sa.Column(
            "findings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("rank", sa.Float(), nullable=True),
        created_at(),
        sa.ForeignKeyConstraint(
            ["community_id"], ["community.community_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["config_id"], ["pipeline_config.config_id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("community_id"),
    )

    op.create_table(
        "embedding",
        sa.Column("embedding_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("config_id", sa.UUID(), nullable=False),
        sa.Column("chunk_id", sa.UUID(), nullable=True),
        sa.Column("entity_id", sa.UUID(), nullable=True),
        sa.Column("community_id", sa.UUID(), nullable=True),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("vector", sa.ARRAY(sa.REAL()), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        created_at(),
        sa.CheckConstraint(
            "num_nonnulls(chunk_id, entity_id, community_id) = 1",
            name="ck_embedding_one_target",
        ),
        sa.CheckConstraint(
            "dimensions > 0 AND cardinality(vector) = dimensions",
            name="ck_embedding_dimensions",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenant.tenant_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["config_id"], ["pipeline_config.config_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id"], ["document_chunk.chunk_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["entity_id"], ["entity.entity_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["community_id"], ["community_report.community_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("embedding_id"),
        sa.UniqueConstraint("config_id", "chunk_id", name="uq_embedding_chunk"),
        sa.UniqueConstraint("config_id", "entity_id", name="uq_embedding_entity"),
        sa.UniqueConstraint("config_id", "community_id", name="uq_embedding_community"),
    )

    # Clean-up of the existing tables.
    for name, table, _ in REDUNDANT_INDEXES:
        op.drop_index(name, table_name=table)
    op.drop_constraint("users_email_key", "users", type_="unique")
    op.create_unique_constraint(
        "uq_users_tenant_email", "users", ["tenant_id", "email"]
    )
    for table, has_updated_at in AUDITED_TABLES:
        op.alter_column(table, "created_at", server_default=NOW)
        if has_updated_at:
            op.alter_column(table, "updated_at", server_default=NOW)


def downgrade() -> None:
    fail_if_rows("document_chunk", "the old schema cannot hold the new chunks")

    for table, has_updated_at in AUDITED_TABLES:
        op.alter_column(table, "created_at", server_default=None)
        if has_updated_at:
            op.alter_column(table, "updated_at", server_default=None)
    op.drop_constraint("uq_users_tenant_email", "users", type_="unique")
    op.create_unique_constraint("users_email_key", "users", ["email"])
    for name, table, columns in REDUNDANT_INDEXES:
        op.create_index(name, table, columns)

    for table in (
        "embedding",
        "community_report",
        "community_member",
        "community",
        "relationship_evidence",
        "entity_relationship",
        "entity_mention",
        "entity",
        "chunk_span",
        "document_chunk",
        "pipeline_config",
    ):
        op.drop_table(table)

    # The document_chunk table of revision 85002e92591a.
    op.create_table(
        "document_chunk",
        sa.Column("chunk_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section_title", sa.String(length=255), nullable=True),
        sa.Column(
            "chunk_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "source_locator", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("chunk_hash", sa.String(length=64), nullable=True),
        sa.Column("qdrant_point_id", sa.UUID(), nullable=True),
        sa.Column("neo4j_node_id", sa.String(length=255), nullable=True),
        created_at(),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"], ["document.document_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("chunk_id"),
        sa.UniqueConstraint(
            "document_id", "chunk_index", name="uq_document_chunk_index"
        ),
    )
    for name, columns in [
        ("ix_chunk_chunk_hash", ["chunk_hash"]),
        ("ix_chunk_created_at", ["created_at"]),
        ("ix_chunk_document_order", ["document_id", "chunk_index"]),
        ("ix_chunk_neo4j_node_id", ["neo4j_node_id"]),
        ("ix_chunk_page_number", ["page_number"]),
        ("ix_chunk_qdrant_point_id", ["qdrant_point_id"]),
        ("ix_chunk_section_title", ["section_title"]),
        ("ix_document_chunk_chunk_id", ["chunk_id"]),
        ("ix_document_chunk_document_id", ["document_id"]),
    ]:
        op.create_index(name, "document_chunk", columns)
