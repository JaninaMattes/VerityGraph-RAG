# SQLAlchemy implementation
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger
from src.domain.documents.entities import DocumentEntity
from src.domain.documents.repository import DocumentRepository
from src.infrastructure.database.postgres.mapper.document import DocumentMapper
from src.infrastructure.database.postgres.models.document import Document
from src.utils.exceptions import (
    DatabaseOperationException,
    DocumentNotFoundException,
)

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
        except SQLAlchemyError as exc:
            logger.warning(
                "Raised database related error for %s. This could be due to an invalid or conflicting function argument.",
                db_document.document_id,
            )
            await self.session.rollback()

            raise DatabaseOperationException(
                f"Failed to create new document metadata entry for '{db_document.document_id}' in database."
            ) from exc

        return DocumentMapper.to_entity(db_document)  # after refresh

    async def get(self, document_id: UUID) -> DocumentEntity:
        """Retrieve a record by its primary key."""
        try:
            db_document = await self.session.get(Document, document_id)
        except SQLAlchemyError as exc:
            logger.warning(
                "Raised database related error for %s. This could be due to an invalid or conflicting function argument.",
                document_id,
            )
            await self.session.rollback()

            raise DatabaseOperationException(
                f"Failed to read document metadata for '{document_id}' in database."
            ) from exc

        if db_document is None:
            raise DocumentNotFoundException(document_id=document_id)

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
        except SQLAlchemyError as exc:
            logger.warning(
                "Raised database related error for %s. This could be due to an invalid or conflicting function argument.",
                document.document_id,
            )
            await self.session.rollback()

            raise DatabaseOperationException(
                f"Failed to update document metadata for '{document.document_id}' in database."
            ) from exc

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
        except SQLAlchemyError as exc:
            logger.warning(
                "Raised database related error for %s. This could be due to an invalid or conflicting function argument.",
                document.document_id,
            )
            await self.session.rollback()

            raise DatabaseOperationException(
                f"Failed to remove document metadata for '{document.document_id}' in database."
            ) from exc

        return DocumentMapper.to_entity(merged_document)
