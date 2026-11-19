"""Integration tests: the migrations and the chunk repository on real PostgreSQL.

They check what mocks cannot: the SQL, the constraints and the cascades.
"""

import os
import uuid

import pytest
from alembic.config import Config
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from alembic import command
from src.domain.chunks.entities import (
    BoundingBox,
    ChunkDraft,
    ChunkingConfig,
    ChunkSpan,
    build_chunks,
)
from src.infrastructure.database.postgres.models import (
    Document,
    DocumentChunk,
    DocumentChunkSpan,
    Embedding,
    PipelineConfig,
    Tenant,
    User,
)
from src.infrastructure.database.postgres.repositories.chunk import (
    PostgresChunkRepository,
)
from src.libs.enums.document import DocumentStatus

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is not set"
)

CONFIG = ChunkingConfig(
    component="docling-hybrid-chunker",
    component_version="2.150.1",
    model="BAAI/bge-small-en-v1.5",
    parameters={"max_tokens": 512},
)
SPAN = ChunkSpan(
    source_ref="#/texts/0",
    label="text",
    page_no=2,
    bbox=BoundingBox(72, 728.5, 180, 717.5),
    char_start=0,
    char_end=4,
)


async def add_document(session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    """Insert a tenant with one document; return (tenant_id, document_id)."""
    tenant_id, document_id = uuid.uuid4(), uuid.uuid4()
    session.add(Tenant(tenant_id=tenant_id, organisation="ACME"))
    await session.flush()
    session.add(
        Document(
            document_id=document_id,
            tenant_id=tenant_id,
            filename="report.pdf",
            storage_key=f"{tenant_id}/files/{document_id}.pdf",
            status=DocumentStatus.UPLOADED,
        )
    )
    await session.commit()
    return tenant_id, document_id


def chunks_for(tenant_id: uuid.UUID, document_id: uuid.UUID, *texts: str) -> list:
    drafts = [ChunkDraft(content=t, token_count=1, spans=(SPAN,)) for t in texts]
    return build_chunks(
        drafts, document_id=document_id, tenant_id=tenant_id, config=CONFIG
    )


class TestMigrations:
    """The migrations produce exactly the schema of the ORM models."""

    def test_models_match_migrated_schema(self, migrated: Config):
        """
        GIVEN a database migrated to the newest revision
        WHEN Alembic compares it with the models
        THEN it finds no difference
        """
        command.check(migrated)

    def test_newest_revision_can_be_reverted_and_reapplied(self, migrated: Config):
        """
        GIVEN an empty database at the newest revision
        WHEN the newest revision is reverted and applied again
        THEN both steps succeed AND the schema still matches the models
        """
        command.downgrade(migrated, "-1")
        command.upgrade(migrated, "head")

        command.check(migrated)


class TestChunkStorage:
    """Chunks and spans are stored, replaced and deleted as one unit."""

    async def test_chunks_and_spans_round_trip(self, session: AsyncSession):
        """
        GIVEN a document
        WHEN two chunks with spans are stored and listed again
        THEN the listed chunks equal the stored ones, in order, with server times
        """
        tenant_id, document_id = await add_document(session)
        chunks = chunks_for(tenant_id, document_id, "first", "second")
        repository = PostgresChunkRepository(session)

        await repository.replace_for_document(document_id, tenant_id, CONFIG, chunks)
        await session.commit()
        listed = await repository.list_for_document(document_id, tenant_id)

        assert [c.chunk_id for c in listed] == [c.chunk_id for c in chunks]
        assert listed[0].spans == (SPAN,)
        assert (listed[0].page_start, listed[0].page_end) == (2, 2)
        assert all(c.created_at is not None for c in listed)

    async def test_replace_is_idempotent(self, session: AsyncSession):
        """
        GIVEN chunks stored for a document
        WHEN the same chunks are stored again (a retried activity)
        THEN the document has the same chunks AND one pipeline config row
        """
        tenant_id, document_id = await add_document(session)
        chunks = chunks_for(tenant_id, document_id, "first", "second")
        repository = PostgresChunkRepository(session)

        for _ in range(2):
            await repository.replace_for_document(
                document_id, tenant_id, CONFIG, chunks
            )
            await session.commit()

        listed = await repository.list_for_document(document_id, tenant_id)
        configs = await session.scalar(select(func.count()).select_from(PipelineConfig))
        assert [c.chunk_id for c in listed] == [c.chunk_id for c in chunks]
        assert configs == 1

    async def test_replace_removes_old_chunks(self, session: AsyncSession):
        """
        GIVEN two chunks stored for a document
        WHEN one new chunk replaces them
        THEN only the new chunk and its spans remain
        """
        tenant_id, document_id = await add_document(session)
        repository = PostgresChunkRepository(session)
        await repository.replace_for_document(
            document_id, tenant_id, CONFIG, chunks_for(tenant_id, document_id, "a", "b")
        )
        await session.commit()

        await repository.replace_for_document(
            document_id, tenant_id, CONFIG, chunks_for(tenant_id, document_id, "new")
        )
        await session.commit()

        listed = await repository.list_for_document(document_id, tenant_id)
        spans = await session.scalar(
            select(func.count()).select_from(DocumentChunkSpan)
        )
        assert [c.content for c in listed] == ["new"]
        assert spans == 1

    async def test_other_tenant_sees_no_chunks(self, session: AsyncSession):
        """
        GIVEN chunks of a document of tenant A
        WHEN tenant B lists the chunks of that document
        THEN the list is empty
        """
        tenant_id, document_id = await add_document(session)
        repository = PostgresChunkRepository(session)
        await repository.replace_for_document(
            document_id, tenant_id, CONFIG, chunks_for(tenant_id, document_id, "a")
        )
        await session.commit()

        assert await repository.list_for_document(document_id, uuid.uuid4()) == []

    async def test_deleting_the_document_deletes_chunks_and_spans(
        self, session: AsyncSession
    ):
        """
        GIVEN a document with chunks and spans
        WHEN the document row is deleted
        THEN the database deletes its chunks and spans (ON DELETE CASCADE)
        """
        tenant_id, document_id = await add_document(session)
        await PostgresChunkRepository(session).replace_for_document(
            document_id, tenant_id, CONFIG, chunks_for(tenant_id, document_id, "a")
        )
        await session.commit()

        await session.delete(await session.get(Document, document_id))
        await session.commit()

        for model in (DocumentChunk, DocumentChunkSpan):
            count = await session.scalar(select(func.count()).select_from(model))
            assert count == 0


class TestConstraints:
    """The database rejects rows that break the provenance rules."""

    async def test_email_is_unique_per_tenant_only(self, session: AsyncSession):
        """
        GIVEN one email address
        WHEN it is used in two tenants, and then twice in one tenant
        THEN the first case is accepted AND the second is rejected
        """
        first, _ = await add_document(session)
        second, _ = await add_document(session)
        for tenant_id in (first, second):
            session.add(
                User(
                    user_id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    username="ada",
                    email="a@x.io",
                )
            )
        await session.commit()

        session.add(
            User(user_id=uuid.uuid4(), tenant_id=first, username="ada", email="a@x.io")
        )
        with pytest.raises(IntegrityError, match="uq_users_tenant_email"):
            await session.commit()

    @pytest.mark.parametrize(
        ("targets", "vector", "constraint"),
        [
            ({"chunk": True, "entity": True}, [0.1, 0.2], "ck_embedding_one_target"),
            ({}, [0.1, 0.2], "ck_embedding_one_target"),
            ({"chunk": True}, [0.1], "ck_embedding_dimensions"),
        ],
        ids=["two-targets", "no-target", "wrong-dimensions"],
    )
    async def test_invalid_embedding_is_rejected(
        self, session: AsyncSession, targets, vector, constraint
    ):
        """
        GIVEN an embedding with two targets, no target, or a vector of the wrong size
        WHEN it is inserted
        THEN the database rejects it with the named check constraint
        """
        tenant_id, document_id = await add_document(session)
        (chunk,) = chunks_for(tenant_id, document_id, "a")
        await PostgresChunkRepository(session).replace_for_document(
            document_id, tenant_id, CONFIG, [chunk]
        )
        await session.commit()

        session.add(
            Embedding(
                embedding_id=uuid.uuid4(),
                tenant_id=tenant_id,
                config_id=CONFIG.config_id,
                chunk_id=chunk.chunk_id if targets.get("chunk") else None,
                entity_id=uuid.uuid4() if targets.get("entity") else None,
                dimensions=2,
                vector=vector,
                content_hash=chunk.content_hash,
            )
        )
        with pytest.raises(IntegrityError, match=constraint):
            await session.commit()

    async def test_span_on_page_zero_is_rejected(self, session: AsyncSession):
        """
        GIVEN a stored chunk
        WHEN a span with page 0 is added to it
        THEN the database rejects it
        """
        tenant_id, document_id = await add_document(session)
        (chunk,) = chunks_for(tenant_id, document_id, "a")
        await PostgresChunkRepository(session).replace_for_document(
            document_id, tenant_id, CONFIG, [chunk]
        )
        await session.commit()

        session.add(
            DocumentChunkSpan(
                chunk_id=chunk.chunk_id,
                span_index=9,
                source_ref="#/x",
                label="text",
                page_no=0,
            )
        )
        with pytest.raises(IntegrityError, match="ck_span_page_no"):
            await session.commit()
