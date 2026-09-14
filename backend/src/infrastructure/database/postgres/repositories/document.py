from uuid import UUID

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.domain.documents.entities import DocumentEntity
from src.domain.documents.repository import DocumentRepository
from src.infrastructure.database.postgres.mapper.document import DocumentMapper
from src.infrastructure.database.postgres.models.document import Document
from src.shared.core.logger import get_logger
from src.shared.exception.exceptions import (
    DatabaseInternalException,
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
        except IntegrityError as exc:
            logger.warning(
                "Database error as new document %s exists already: %s",
                document.document_id,
                exc,
            )
            raise DatabaseOperationException(
                f"Document '{document.document_id}' already exists in database."
            ) from exc
        except SQLAlchemyError as exc:
            logger.warning(
                "Database error creating new document %s: %s",
                db_document.document_id,
                exc,
            )
            await self.session.rollback()
            raise DatabaseInternalException(
                f"Failed to create new document metadata entry for '{db_document.document_id}' in database."
            ) from exc
        return DocumentMapper.to_entity(db_document)  # after refresh

    async def get_one(self, document_id: UUID) -> DocumentEntity:
        """Retrieve a record by its primary key."""
        try:
            stmt = select(Document).where(Document.document_id == document_id)
            result = await self.session.execute(stmt)
            db_document: Document | None = result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            logger.warning(
                "Database error retrieving document %s: %s",
                document_id,
                exc,
            )
            await self.session.rollback()
            raise DatabaseInternalException(
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
                "Database error updating document %s: %s",
                db_document.document_id,
                exc,
            )
            await self.session.rollback()
            raise DatabaseInternalException(
                f"Failed to update document metadata for '{document.document_id}' in database."
            ) from exc

        return DocumentMapper.to_entity(merged_document)  # after refresh

    async def delete(
        self,
        document: DocumentEntity,
    ) -> None:
        db_document = DocumentMapper.to_model(document)

        try:
            merged_document = await self.session.merge(db_document)
            await self.session.delete(merged_document)
            await self.session.commit()
        except SQLAlchemyError as exc:
            logger.warning(
                "Database error removing document %s: %s",
                db_document.document_id,
                exc,
            )
            await self.session.rollback()
            raise DatabaseInternalException(
                f"Failed to remove document metadata for '{document.document_id}' in database."
            ) from exc