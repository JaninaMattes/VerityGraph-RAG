"""Chunk use cases."""

from uuid import UUID

from src.domain.chunks.entities import Chunk
from src.domain.chunks.repository import ChunkRepository
from src.domain.documents.repository import DocumentRepository


class ChunkService:
    """Reads the chunks of a document. Errors propagate unchanged."""

    def __init__(
        self, doc_repository: DocumentRepository, chunk_repository: ChunkRepository
    ) -> None:
        self.doc_repository = doc_repository
        self.chunk_repository = chunk_repository

    async def list_for_document(
        self, document_id: UUID, tenant_id: UUID
    ) -> list[Chunk]:
        """Return the chunks of a document of the tenant, in order.

        Raise DocumentNotFoundException if the tenant has no such document, so an
        unknown id and a foreign id give the same answer.
        """
        await self.doc_repository.get_one(document_id, tenant_id)
        return await self.chunk_repository.list_for_document(document_id, tenant_id)
