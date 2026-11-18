from uuid import UUID

from sqlalchemy import delete, select

from src.domain.documents.entities import DocumentEntity
from src.domain.documents.repository import DocumentRepository
from src.infrastructure.database.postgres.mapper.document import DocumentMapper
from src.infrastructure.database.postgres.models.document import Document
from src.infrastructure.database.postgres.repositories.base import PostgresRepository
from src.libs.exceptions.exceptions import DocumentNotFoundException


class PostgresDocumentRepository(PostgresRepository, DocumentRepository):
    """Documents in PostgreSQL. Every query is scoped to one tenant."""

    async def create(self, document: DocumentEntity) -> DocumentEntity:
        """Insert or overwrite the document, so a retried activity does not fail."""
        return DocumentMapper.to_entity(
            await self._merge(DocumentMapper.to_model(document))
        )

    async def update(self, document: DocumentEntity) -> DocumentEntity:
        return DocumentMapper.to_entity(
            await self._merge(DocumentMapper.to_model(document))
        )

    async def delete(self, document_id: UUID, tenant_id: UUID) -> None:
        await self._delete_one(
            delete(Document).where(
                Document.document_id == document_id, Document.tenant_id == tenant_id
            ),
            DocumentNotFoundException(document_id),
        )

    async def get_one(self, document_id: UUID, tenant_id: UUID) -> DocumentEntity:
        row = await self._scalar_one(
            select(Document).where(
                Document.document_id == document_id, Document.tenant_id == tenant_id
            ),
            DocumentNotFoundException(document_id),
        )
        return DocumentMapper.to_entity(row)
