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
from src.utils.exceptions import DocumentNotFoundException, DocumentServiceError
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
        tenant_id: uuid.UUID,
        file: MetadataRequest,
        namespace: str = "documents",
    ) -> URLResponse:
        """Create presigned URL to upload file to S3 bucket."""

        # Create storage key
        now = datetime.now(UTC)
        document_id = uuid.uuid4()
        storage_key = StorageKey.document(
            tenant_id=tenant_id,
            document_id=document_id,
            namespace=namespace,
        )
        # Persist metadata
        entity = DocumentEntity(
            document_id=document_id,
            tenant_id=tenant_id,
            filename=file.filename,
            storage_key=storage_key,
            status=DocumentStatus.UPLOAD_PENDING,  # upload in progress
            created_at=now,
            updated_at=now,
        )
        try:
            db_document = await self.repository.create(document=entity)
            if db_document is None:
                raise DocumentNotFoundException(
                    name="Document Service Error",
                    message=f"The document with ID {document_id} was not found!",
                )
            # Create presigned URL
            expires_at = timedelta(minutes=30)  # 30 mins expiration
            presigned_url = await asyncio.to_thread(
                self.storage.create_upload_url,
                storage_key=storage_key,
                expires_at=expires_at,
            )
            return URLResponse(
                document_id=db_document.document_id,
                url=presigned_url,
                expires_at=expires_at,
            )
        except Exception as e:
            logger.exception(
                f"Failed to generate presigned upload URL for tenant {tenant_id!r} to blob storage!",
            )
            raise DocumentServiceError(
                "Document Service Error",
                f"Failed to generate presigned upload URL for tenant {tenant_id!r} to blob storage!",
            ) from e

    async def create_download_url(
        self,
        document_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> URLResponse:
        """Create presigned URL to download file from S3 bucket."""
        try:
            db_document = await self.repository.get(document_id=document_id)
            if db_document is None:
                raise DocumentNotFoundException(
                    name="Document Service Error",
                    message=f"The document with ID {document_id} was not found!",
                )
            expires_at = timedelta(minutes=30)  # 30 mins expiration
            presigned_url = await asyncio.to_thread(
                self.storage.create_download_url,
                storage_key=db_document.storage_key,
                expires_at=expires_at,
            )
            return URLResponse(
                document_id=document_id,
                url=presigned_url,
                expires_at=expires_at,
            )
        except Exception as e:
            logger.exception(
                f"Failed to generate presigned download URL for tenant {tenant_id!r} to blob storage!",
            )
            raise DocumentServiceError(
                "Document Service Error",
                f"Failed to generate presigned download URL for tenant {tenant_id!r} to blob storage!",
            ) from e

    async def update_metadata(
        self,
        document_id: uuid.UUID,
    ) -> MetadataResponse:
        try:
            db_document = await self.repository.get(document_id=document_id)
            if db_document is None:
                raise DocumentNotFoundException(
                    name="Document Service Error",
                    message=f"The document with ID {document_id} was not found!",
                )
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
            # If object is there we can mark it as uploaded
            db_document.mark_uploaded()

            # Update document metdata
            updated = await self.repository.update(db_document)
            return MetadataResponse(
                document_id=updated.document_id, status=updated.status
            )
        except Exception:
            logger.exception(
                f"Failed to process metadata for document {document_id}!",
            )
            raise DocumentServiceError(
                "Document Service Error",
                f"Failed to process metadata for document {document_id}!",
            )

    async def delete(
        self, document_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> DeleteResponse:
        try:
            # Retrieve actual document
            document = await self.repository.get(document_id)

            if document is None:
                raise DocumentNotFoundException(
                    name="Document Service Error",
                    message=f"Requested document with ID {document_id} not found!",
                )

            # Update status
            document.mark_deleted(tenant_id)

            # Update metadata
            db_document = await self.repository.update(document)
            if db_document is None:
                raise DocumentNotFoundException(
                    name="Document Service Error",
                    message=f"The document with ID {document_id} was not found!",
                )
            # # Trigger Temporal background processing
            # await self.workflow.start_removal(document.document_id)

            return DeleteResponse(
                document_id=db_document.document_id, status=db_document.status
            )
        except Exception as e:
            logger.exception(
                f"Failed to process delete workflow for document {document_id}!",
            )
            raise DocumentServiceError(
                "Document Service Error",
                f"Failed to process delete workflow for document {document_id}!",
            ) from e