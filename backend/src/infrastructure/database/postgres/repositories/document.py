from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.documents.entities import DocumentEntity
from src.domain.documents.repository import DocumentRepository
from src.infrastructure.database.postgres.mapper.document import DocumentMapper
from src.infrastructure.database.postgres.models.document import Document
from src.libs.core.logger import get_logger
from src.libs.exceptions.exceptions import (
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
        self._session = session

    async def create(
        self, document: DocumentEntity, idempotency_key: str
    ) -> DocumentEntity:
        db_document = DocumentMapper.to_model(document)

        try:
            # Add new object to session
            self._session.add(db_document)
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
            logger.error(
                "Database error when creating new entry for document with id '%s'.",
                db_document.document_id,
            )
            raise DatabaseInternalException(
                f"Failed to create new document metadata entry for '{db_document.document_id}' in database."
            ) from exc
        return DocumentMapper.to_entity(db_document)  # after refresh


    async def update(
        self, document: DocumentEntity, idempotency_key: str
    ) -> DocumentEntity:
        """Update an entry."""
        db_document = DocumentMapper.to_model(document)
        try:
            merged_document = await self._session.merge(db_document)
            await self._session.refresh(merged_document)
        except SQLAlchemyError as exc:
            logger.error(
                "Failed to update document with id '%s' in database.",
                db_document.document_id,
            )
            raise DatabaseInternalException(
                f"Failed to update document metadata for '{document.document_id}' in database."
            ) from exc

        return DocumentMapper.to_entity(merged_document)  # after refresh

    async def delete(self, document_id: UUID, tenant_id: UUID) -> None:

        try:
            stmt = delete(Document).where(
                Document.document_id == document_id, Document.tenant_id == tenant_id
            )
            result = await self._session.execute(stmt)

            if result.scalar_one_or_none() is None:
                logger.exception(
                    "Document with id '%s' could not be found.", document_id
                )
                raise DocumentNotFoundException(document_id)

        except SQLAlchemyError as exc:
            logger.error(
                "Failed to remove document with id '%s' in database.",
                document_id,
            )
            raise DatabaseInternalException(
                f"Failed to remove document metadata for '{document_id}' in database."
            ) from exc

    async def get_one(self, document_id: UUID, tenant_id: UUID) -> DocumentEntity:
        """Retrieve a record by its primary key."""
        try:
            stmt = select(Document).where(
                Document.document_id == document_id, Document.tenant_id == tenant_id
            )
            result = await self._session.execute(stmt)
            db_document = result.scalar_one_or_none()

            if db_document is None:
                logger.exception(
                    "Document with id '%s' could not be found.", document_id
                )
                raise DocumentNotFoundException(document_id=document_id)

        except SQLAlchemyError as exc:
            logger.error(
                "Database error when fetching document with id '%s'.",
                document_id,
            )
            raise DatabaseInternalException(
                f"Failed to read document metadata for '{document_id}' in database."
            ) from exc

        return DocumentMapper.to_entity(db_document)