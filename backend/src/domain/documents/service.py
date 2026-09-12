# src/domain/documents/service.py
import asyncio
import uuid
from datetime import timedelta

from src.domain.documents.dataclasses import StorageKey
from src.domain.documents.repository import DocumentRepository
from src.infrastructure.storage.provider import StorageProvider
from src.shared.core.logger import get_logger
from src.shared.exception.exceptions import (
    DatabaseException,
    DocumentServiceException,
    NotFoundException,
    StorageException,
)
from src.shared.schemas.document import (
    DocumentStatusResponse,
    PresignedURLResponse,
)

logger = get_logger("api.domain.doc.service")


class DocumentService:
    """The service layer defines the business logic that ineracts with the repository."""

    def __init__(
        self,
        repository: DocumentRepository,
        storage: StorageProvider,
    ) -> None:
        self.repository = repository
        self.storage = storage

    async def create_upload_url(
        self,
        namespace: str = "documents",
    ) -> PresignedURLResponse:
        """Create presigned PUT URL to upload file to S3 bucket."""

        # Create storage key
        document_id = uuid.uuid4()
        try:
            storage_key = StorageKey.document(
                document_id=document_id,
                namespace=namespace,
            )

            # Create presigned URL
            expires_at = timedelta(minutes=30)  # 30 mins expiration
            presigned_url = await asyncio.to_thread(
                self.storage.create_presigned_url,
                storage_key=storage_key,
                expires_at=expires_at,
                method="PUT",
            )
            return PresignedURLResponse(
                document_id=document_id,
                url=presigned_url,
                expires_at=expires_at,
            )
        except DatabaseException:
            raise
        except StorageException:
            raise
        except Exception as exc:
            logger.warning(
                "Unexpected error occured when generating presigned PUT URL for document %s.",
                document_id,
            )
            raise DocumentServiceException(
                "Failed to create presigned upload URL.",
            ) from exc

    async def get_download_url(
        self,
        document_id: uuid.UUID,
    ) -> PresignedURLResponse:
        """Create presigned GET URL to download file from S3 bucket."""
        try:
            db_document = await self.repository.get_one(document_id=document_id)
            expires_at = timedelta(minutes=30)  # 30 mins expiration
            presigned_url = await asyncio.to_thread(
                self.storage.create_presigned_url,
                storage_key=db_document.storage_key,
                expires_at=expires_at,
                method="GET",
            )
            return PresignedURLResponse(
                document_id=document_id,
                url=presigned_url,
                expires_at=expires_at,
            )
        except DatabaseException:
            raise
        except StorageException:
            raise
        except Exception as exc:
            logger.warning(
                "Unexpected error occured when generating presigned GET URL for document %s.",
                document_id,
            )
            raise DocumentServiceException(
                "Failed to create presigned upload URL.",
            ) from exc

    async def finalize_upload(
        self,
        document_id: uuid.UUID,
    ) -> DocumentStatusResponse:
        try:
            # Fetch document metadata
            db_document = await self.repository.get_one(document_id)

            # Retrieve blob storage metadata
            metadata = await asyncio.to_thread(
                self.storage.get_obj_metadata,
                storage_key=db_document.storage_key,
            )

            # Modulate document metadata
            db_document.update_storage_metadata(metadata)
            # If object, then we can mark it as uploaded
            db_document.mark_uploaded()

            # Persist document metdata
            updated = await self.repository.update(db_document)
            return DocumentStatusResponse(
                document_id=updated.document_id, status=updated.status
            )
        except DatabaseException:
            raise
        except NotFoundException:
            raise
        except Exception as exc:
            logger.warning(
                "Unexpected error occured when updating metadata for document %s.",
                document_id,
            )
            raise DocumentServiceException(
                "Failed to update document metadata.",
            ) from exc

    async def remove_document(self, document_id: uuid.UUID) -> None:
        try:
            # Retrieve actual document
            db_document = await self.repository.get_one(document_id)

            # Delete from database
            await self.repository.delete(db_document)

            # Delete from blob storage
            await asyncio.to_thread(
                self.storage.delete_object,
                storage_key=db_document.storage_key,
            )

        except DatabaseException:
            raise
        except NotFoundException:
            raise
        except Exception as exc:
            logger.warning(
                "Unexpected error occured when removing document %s metadata.",
                document_id,
            )
            raise DocumentServiceException(
                "Failed to remove document metadata.",
            ) from exc
