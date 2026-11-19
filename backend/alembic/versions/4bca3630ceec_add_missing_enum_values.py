"""Add the enum values that the application uses but the database lacked.

- ingestionstage: INITIALISING (the stage of every new ingestion job) and
  VECTOR_BUILDING.
- documenttype: UNKNOWN (an upload without a file extension).

Without them every new ingestion job, and every upload without an extension, fails
on insert. The downgrade removes the values again; it stops if a row uses one.

Revision ID: 4bca3630ceec
Revises: 931d81fb0b64
Create Date: 2026-11-19 15:10:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "4bca3630ceec"
down_revision: str | Sequence[str] | None = "931d81fb0b64"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Enum type -> (table, column, values before this revision, values added here).
ENUMS = {
    "ingestionstage": (
        "ingestion_job",
        "current_stage",
        [
            "DOWNLOAD",
            "PARSING",
            "CHUNKING",
            "EMBEDDING",
            "GRAPH_BUILDING",
            "EVALUATION",
        ],
        {"INITIALISING": "DOWNLOAD", "VECTOR_BUILDING": "GRAPH_BUILDING"},
    ),
    "documenttype": (
        "document",
        "document_type",
        ["PDF", "DOCX", "DOC", "MARKDOWN", "CSV", "HTML", "IMAGE", "PPTX"],
        {"UNKNOWN": None},
    ),
}


def upgrade() -> None:
    """Add each value at its place in the order of the Python enum."""
    for type_name, (_, _, _, added) in ENUMS.items():
        for value, before in added.items():
            position = f" BEFORE '{before}'" if before else ""
            op.execute(
                f"ALTER TYPE {type_name} ADD VALUE IF NOT EXISTS '{value}'{position}"
            )


def downgrade() -> None:
    """Recreate each type without the added values. Stop if a row uses one."""
    for type_name, (table, column, previous, added) in ENUMS.items():
        used = ", ".join(f"'{value}'" for value in added)
        op.execute(
            f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM {table} WHERE {column}::text IN ({used})) THEN
                    RAISE EXCEPTION '{table}.{column} uses a value of {type_name} that '
                        'the downgrade removes. Change these rows first.';
                END IF;
            END $$;
            """
        )
        values = ", ".join(f"'{value}'" for value in previous)
        op.execute(f"ALTER TYPE {type_name} RENAME TO {type_name}_old")
        op.execute(f"CREATE TYPE {type_name} AS ENUM ({values})")
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} TYPE {type_name}"
            f" USING {column}::text::{type_name}"
        )
        op.execute(f"DROP TYPE {type_name}_old")
