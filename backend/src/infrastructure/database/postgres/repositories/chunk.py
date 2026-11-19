from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload

from src.domain.chunks.entities import Chunk, ChunkingConfig
from src.domain.chunks.repository import ChunkRepository
from src.infrastructure.database.postgres.mapper.chunk import ChunkMapper
from src.infrastructure.database.postgres.models.chunk import (
    DocumentChunk,
    DocumentChunkSpan,
)
from src.infrastructure.database.postgres.models.pipeline import PipelineConfig
from src.infrastructure.database.postgres.repositories.base import (
    PostgresRepository,
    translate_db_errors,
)


class PostgresChunkRepository(PostgresRepository, ChunkRepository):
    """Chunks and spans in PostgreSQL. Every query is scoped to one tenant."""

    async def replace_for_document(
        self,
        document_id: UUID,
        tenant_id: UUID,
        config: ChunkingConfig,
        chunks: Sequence[Chunk],
    ) -> None:
        """Store the config (once), delete the old chunks, insert the new ones.

        The caller commits, so readers see either the old or the new chunks. The
        config insert ignores an existing row, so parallel workers do not conflict.
        """
        with translate_db_errors("replace the chunks of a document"):
            await self._session.execute(
                insert(PipelineConfig)
                .values(**ChunkMapper.config_values(config))
                .on_conflict_do_nothing()
            )
            old_chunk_ids = select(DocumentChunk.chunk_id).where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.tenant_id == tenant_id,
            )
            # Delete spans with the ORM too (not only by cascade), so loaded span
            # objects leave the session and do not collide with the new rows.
            await self._session.execute(
                delete(DocumentChunkSpan)
                .where(DocumentChunkSpan.chunk_id.in_(old_chunk_ids))
                .execution_options(synchronize_session="fetch")
            )
            await self._session.execute(
                delete(DocumentChunk)
                .where(DocumentChunk.chunk_id.in_(old_chunk_ids))
                .execution_options(synchronize_session="fetch")
            )
            self._session.add_all([ChunkMapper.to_model(chunk) for chunk in chunks])
            await self._session.flush()

    async def list_for_document(
        self, document_id: UUID, tenant_id: UUID
    ) -> list[Chunk]:
        statement = (
            select(DocumentChunk)
            .where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.tenant_id == tenant_id,
            )
            .options(selectinload(DocumentChunk.spans))
            .order_by(DocumentChunk.chunk_index)
        )
        with translate_db_errors("list the chunks of a document"):
            rows = (await self._session.execute(statement)).scalars().all()
        return [ChunkMapper.to_entity(row) for row in rows]
