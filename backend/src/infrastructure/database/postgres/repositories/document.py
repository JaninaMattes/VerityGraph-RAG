# SQLAlchemy implementation
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger
from src.domain.documents.entities import DocumentEntity
from src.domain.documents.repository import DocumentRepository
from src.infrastructure.database.postgres.mapper.document import DocumentMapper
from src.infrastructure.database.postgres.models.document import Document
from src.utils.exceptions import DocumentNotFoundException, PostgreSQLOperationError

logger = get_logger("api-backend.infra.postgres.doc")


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
                f"Failed to create new document metadata entry with ID {document.document_id}!",
            )
            await self.session.rollback()
            raise PostgreSQLOperationError(
                "PostgreSQL DB Error",
                f"Failed to create new document metadata entry with ID {document.document_id}!",
            ) from e

        return DocumentMapper.to_entity(db_document)  # refresh

    async def update(
        self,
        document: DocumentEntity,
    ) -> DocumentEntity:

        db_document = DocumentMapper.to_model(document)

        # Add objects to session
        try:
            merged_document = await self.session.merge(db_document)
            await self.session.commit()
            await self.session.refresh(merged_document)
        except Exception as e:
            logger.exception(
                f"Failed to update document metadata with ID {document.document_id}!",
            )
            await self.session.rollback()
            raise PostgreSQLOperationError(
                "PostgreSQL DB Error",
                f"Failed to update document metadata with ID {document.document_id}!",
            ) from e

        return DocumentMapper.to_entity(merged_document)  # refresh

    async def get(self, document_id: UUID) -> DocumentEntity:
        db_document = None
        try:
            db_document = await self.session.get(Document, document_id)
        except Exception as e:
            logger.exception(
                f"Failed to get document metadata with ID {document_id}!",
            )
            await self.session.rollback()
            raise PostgreSQLOperationError(
                "PostgreSQL DB Error",
                f"Failed to get document metadata with ID {document_id}!",
            ) from e

        if db_document is None:
            raise DocumentNotFoundException(
                name="Document Repository Error",
                message=f"Requested document with ID {document_id} not found!",
            )

        return DocumentMapper.to_entity(db_document)

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
                f"Failed to delete document metadata with ID {document.document_id}!",
            )
            await self.session.rollback()
            raise PostgreSQLOperationError(
                "PostgreSQL DB Error",
                f"Failed to delete document metadata with ID {document.document_id}!",
            ) from e

        return DocumentMapper.to_entity(merged_document)
