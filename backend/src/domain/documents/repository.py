from typing import Protocol
from uuid import UUID

from src.domain.documents.entities import DocumentEntity


class DocumentRepository(Protocol):
    """The repository layer handles all CRUD requests against a databse."""

    async def create(
        self, document: DocumentEntity, idempotency_key: str
    ) -> DocumentEntity:
        raise NotImplementedError("Subclasses must implement create method")

    async def update(
        self, document: DocumentEntity, idempotency_key: str
    ) -> DocumentEntity:
        raise NotImplementedError("Subclasses must implement update method")

    async def delete(self, document_id: UUID, tenant_id: UUID) -> None:
        raise NotImplementedError("Subclasses must implement delete method")

    async def get_one(self, document_id: UUID, tenant_id: UUID) -> DocumentEntity:
        raise NotImplementedError("Subclasses must implement get_one method")
