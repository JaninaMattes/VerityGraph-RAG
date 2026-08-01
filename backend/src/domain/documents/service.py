# src/domain/documents/service.py
import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from src.core.logger import get_logger
from src.domain.documents.dataclasses import StorageKey
from src.domain.documents.entities import DocumentEntity
from src.domain.documents.repository import DocumentRepository
from src.domain.documents.schemas import (
    DeleteResponse,
    MetadataRequest,
    MetadataResponse,
    URLResponse,
)
from src.infrastructure.storage.provider import StorageProvider
from src.shared.enums import DocumentStatus
from src.utils.exceptions import (
    DatabaseException,
    DocumentServiceException,
    NotFoundException,
    StorageException,
)
from src.workflows.ingestion.workflow import WorkflowClient

logger = get_logger("api.domain.doc.service")


class DocumentService:
    """The service layer defines the business logic that ineracts with the repository."""

    def __init__(
        self,
        repository: DocumentRepository,
        storage: StorageProvider,
        workflow: WorkflowClient,
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.workflow = workflow

    async def create_upload_url(
        self,
        file: MetadataRequest,
        namespace: str = "documents",
    ) -> URLResponse:
        """Create presigned PUT URL to upload file to S3 bucket."""

        # Create storage key
        now = datetime.now(UTC)
        document_id = uuid.uuid4()
        try:
            storage_key = StorageKey.document(
                tenant_id=file.tenant_id,
                document_id=document_id,
                namespace=namespace,
            )
            # Persist metadata
            entity = DocumentEntity(
                document_id=document_id,
                tenant_id=file.tenant_id,
                filename=file.filename,
                storage_key=storage_key,
                status=DocumentStatus.UPLOAD_PENDING,  # upload in progress
                created_at=now,
                updated_at=now,
            )
            db_document = await self.repository.create(document=entity)

            # Create presigned URL
            expires_at = timedelta(minutes=30)  # 30 mins expiration
            presigned_url = await asyncio.to_thread(
                self.storage.create_presigned_url,
                storage_key=storage_key,
                expires_at=expires_at,
                method="PUT",
            )
            return URLResponse(
                document_id=db_document.document_id,
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

    async def create_download_url(
        self,
        document_id: uuid.UUID,
    ) -> URLResponse:
        """Create presigned GET URL to download file from S3 bucket."""
        try:
            db_document = await self.repository.get(document_id=document_id)
            expires_at = timedelta(minutes=30)  # 30 mins expiration
            presigned_url = await asyncio.to_thread(
                self.storage.create_presigned_url,
                storage_key=db_document.storage_key,
                expires_at=expires_at,
                method="GET",
            )
            return URLResponse(
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

    async def update_metadata(
        self,
        document_id: uuid.UUID,
    ) -> MetadataResponse:
        try:
            # Fetch document metadata
            db_document = await self.repository.get(document_id=document_id)
            # Retrieve blob storage metadata
            metadata = await asyncio.to_thread(
                self.storage.get_obj_metadata,
                storage_key=db_document.storage_key,
            )

            # Modulate document metadata
            db_document.storage_key = metadata.storage_key
            db_document.mime_type = metadata.mime_type
            db_document.size_bytes = metadata.size_bytes
            db_document.bucket_name = metadata.bucket_name
            db_document.version_id = metadata.version_id
            db_document.etag = metadata.etag
            # If object, then we can mark it as uploaded
            db_document.mark_uploaded()

            # Update document metdata
            updated = await self.repository.update(db_document)
            return MetadataResponse(
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

    async def delete(
        self, document_id: uuid.UUID, user_id: uuid.UUID
    ) -> DeleteResponse:
        try:
            # Retrieve actual document
            document = await self.repository.get(document_id)
            document.mark_deleted(user_id)

            # Update metadata
            db_document = await self.repository.update(document)

            return DeleteResponse(
                document_id=db_document.document_id, status=db_document.status
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
