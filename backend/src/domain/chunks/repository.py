"""Persistence port for chunks and their evidence spans."""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from src.domain.chunks.entities import Chunk, ChunkingConfig


class ChunkRepository(Protocol):
    """Chunks in the source of truth. Implementations flush but never commit."""

    async def replace_for_document(
        self,
        document_id: UUID,
        tenant_id: UUID,
        config: ChunkingConfig,
        chunks: Sequence[Chunk],
    ) -> None:
        """Delete all chunks of the document, then store `chunks` and `config`.

        Safe to repeat. Deleting a chunk also deletes the data derived from it
        (spans, mentions, relationship evidence, embeddings).
        """
        raise NotImplementedError

    async def list_for_document(
        self,
        document_id: UUID,
        tenant_id: UUID,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Chunk]:
        """Return the chunks after the first `offset`, in order, with their spans.

        `limit` caps the number of chunks; None returns all (for example to rebuild
        a projection).
        """
        raise NotImplementedError
