# SQLAlchemy implementation
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger
from src.domain.documents.entities import DocumentEntity
from src.domain.documents.repository import DocumentRepository
from src.infrastructure.database.postgres.mapper.document import DocumentMapper
from src.infrastructure.database.postgres.models.document import Document
from src.utils.exceptions import DocumentNotFoundException, PostgreSQLOperationError

logger = get_logger("api.infra.postgres.doc")


class PostgresDocumentRepository(DocumentRepository):
    def __init__(
        self,
        session: AsyncSession,
    ):
        self.session = session

    async def create(self, document: DocumentEntity) -> DocumentEntity:

        db_document = DocumentMapper.to_model(document)

        # Add new object to session
        try:
            self.session.add(db_document)
            await self.session.commit()
            await self.session.refresh(db_document)
        except Exception as e:
            logger.exception(
                f"Failed to create new entry for document metadata with ID {document.document_id!r}!",
            )
            await self.session.rollback()
            raise PostgreSQLOperationError(
                "PostgreSQL DB Error",
                f"Failed to create new entry for document metadata with ID {document.document_id!r}!",
            ) from e

        return DocumentMapper.to_entity(db_document)  # after refresh

    async def get(self, document_id: UUID) -> DocumentEntity:
        """Retrieve a record by its primary key."""
        try:
            db_document = await self.session.get(Document, document_id)
            if db_document is None:
                raise DocumentNotFoundException(
                    name="Document Repository Error",
                    message=f"Requested document with ID {document_id} not found!",
                )
        except Exception as e:
            logger.exception(
                f"Failed to get document metadata with ID {document_id!r}!",
            )
            await self.session.rollback()
            raise PostgreSQLOperationError(
                "PostgreSQL DB Error",
                f"Failed to get document metadata with ID {document_id!r}!",
            ) from e

        return DocumentMapper.to_entity(db_document)

    async def update(
        self,
        document: DocumentEntity,
    ) -> DocumentEntity:
        """Update an entry."""
        db_document = DocumentMapper.to_model(document)

        # Add objects to session
        try:
            merged_document = await self.session.merge(db_document)
            await self.session.commit()
            await self.session.refresh(merged_document)
        except Exception as e:
            logger.exception(
                f"Failed to update document metadata with ID {document.document_id!r}!",
            )
            await self.session.rollback()
            raise PostgreSQLOperationError(
                "PostgreSQL DB Error",
                f"Failed to update document metadata with ID {document.document_id!r}!",
            ) from e

        return DocumentMapper.to_entity(merged_document)  # after refresh

    async def delete(
        self,
        document: DocumentEntity,
    ):
        db_document = DocumentMapper.to_model(document)

        try:
            merged_document = await self.session.merge(db_document)
            await self.session.delete(merged_document)
            await self.session.commit()
        except Exception as e:
            logger.exception(
                f"Failed to delete document metadata with ID {document.document_id!r}!",
            )
            await self.session.rollback()
            raise PostgreSQLOperationError(
                "PostgreSQL DB Error",
                f"Failed to delete document metadata with ID {document.document_id!r}!",
            ) from e

        return DocumentMapper.to_entity(merged_document)
