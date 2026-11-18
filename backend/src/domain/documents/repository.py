from typing import Protocol
from uuid import UUID

from src.domain.documents.entities import DocumentEntity


class DocumentRepository(Protocol):
    """Persistence port for documents. Implementations flush but never commit."""

    async def create(self, document: DocumentEntity) -> DocumentEntity:
        """Insert the document, or overwrite it if it exists (safe for retries)."""
        raise NotImplementedError

    async def update(self, document: DocumentEntity) -> DocumentEntity:
        """Save the changed document."""
        raise NotImplementedError

    async def delete(self, document_id: UUID, tenant_id: UUID) -> None:
        """Delete the document. Raise DocumentNotFoundException if it does not exist."""
        raise NotImplementedError

    async def get_one(self, document_id: UUID, tenant_id: UUID) -> DocumentEntity:
        """Return the document. Raise DocumentNotFoundException if it does not exist."""
        raise NotImplementedError
