from typing import Protocol
from uuid import UUID

from src.domain.documents.entities import DocumentEntity


class DocumentRepository(Protocol):
    """The repository layer handles all CRUD requests against a databse."""

    async def create(
        self,
        document: DocumentEntity,
    ) -> DocumentEntity: ...

    async def update(
        self,
        document: DocumentEntity,
    ) -> DocumentEntity: ...

    async def get_one(self, document_id: UUID) -> DocumentEntity: ...

    async def delete(
        self,
        document: DocumentEntity,
    ) -> None: ...
