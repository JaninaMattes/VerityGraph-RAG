from abc import abstractmethod
from typing import Protocol
from uuid import UUID

from src.domain.documents.entities import DocumentEntity


class DocumentRepository(Protocol):
    """The repository layer handles all CRUD requests against a databse."""

    @abstractmethod
    async def create(
        self,
        document: DocumentEntity,
    ) -> DocumentEntity: ...

    @abstractmethod
    async def update(
        self,
        document: DocumentEntity,
    ) -> DocumentEntity: ...

    @abstractmethod
    async def get(self, document_id: UUID) -> DocumentEntity: ...

    @abstractmethod
    async def delete(
        self,
        document: DocumentEntity,
    ) -> DocumentEntity: ...
