# src/domain/documents/service.py
import asyncio
from datetime import datetime, timedelta, timezone
import uuid

from src.utils.exceptions import DocumentNotFoundException
from src.shared.enums import DocumentStatus
from src.domain.documents.entities import DocumentEntity
from src.domain.documents.repository import DocumentRepository
from src.domain.documents.dataclasses import DocumentStream, StorageKey
from src.domain.documents.schemas import CreateResponse, URLResponse, DeleteResponse
from src.infrastructure.storage.provider import StorageProvider
from src.workflows.ingestion.workflow import WorkflowClient
from src.utils.logger import get_logger

logger = get_logger("api-backend.domain.doc.service")


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

    async def create_upload_url(self, tenant_id: uuid.UUID) -> URLResponse:
        """Create presigned URL to upload file to S3 bucket."""
        document_id = uuid.uuid4()
        expires_at = timedelta(minutes=30)  # 30 mins expiration
        storage_key = StorageKey.document(tenant_id=tenant_id, document_id=document_id)
        try:
            presigned_url = self.storage.create_upload_url(
                storage_key, expires_at=expires_at
            )
            return URLResponse(
                url=presigned_url, storage_key=storage_key.value, expires_at=expires_at
            )
        except Exception as e:
            logger.error(
                f"Failed to generate presigned URL for tenant {tenant_id} to blob storage: {e}",
                exc_info=True,
            )
            raise

    async def create_download_url(
        self, document_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> URLResponse:
        """Create presigned URL to download file from S3 bucket."""
        storage_key = StorageKey.document(tenant_id=tenant_id, document_id=document_id)
        expires_at = timedelta(hours=2)
        try:
            presigned_url = self.storage.create_download_url(
                storage_key, expires_at=expires_at
            )
            return URLResponse(
                url=presigned_url, storage_key=storage_key.value, expires_at=expires_at
            )
        except Exception as e:
            logger.error(
                f"Failed to generate presigned URL for {storage_key.value} to blob storage: {e}",
                exc_info=True,
            )
            raise

    async def create(
        self, file: DocumentStream, tenant_id: uuid.UUID
    ) -> CreateResponse:
        document_id = uuid.uuid4()
        storage_key = StorageKey.document(tenant_id=tenant_id, document_id=document_id)

        try:
            # Non-blocking storage call
            # TODO: Deduplicate by matching checksum, then point to same file
            stored_file = await asyncio.to_thread(
                self.storage.store_file, file=file, storage_key=storage_key
            )
        except Exception as e:
            logger.error(
                f"Failed to upload document {file.filename} to blob storage: {e}",
                exc_info=True,
            )
            raise

        # Persist metadata
        now = datetime.now(timezone.utc)
        entity = DocumentEntity(
            document_id=document_id,
            tenant_id=tenant_id,
            filename=file.filename,
            mime_type=stored_file.mime_type,
            storage_key=storage_key,
            size_bytes=stored_file.size_bytes,
            checksum=stored_file.checksum,
            etag=stored_file.etag,
            version_id=stored_file.version_id,
            bucket_name=stored_file.bucket_name,
            status=DocumentStatus.PROCESSING,  # in progress
            created_at=now,
            updated_at=now,
        )
        try:
            # Save metadata
            db_document = await self.repository.create(entity)

            # Trigger Temporal background processing
            await self.workflow.start_ingestion(entity.document_id)
            return CreateResponse(
                document_id=db_document.document_id, status=db_document.status
            )
        except Exception as e:
            await asyncio.to_thread(self.storage.delete_file, storage_key=storage_key)
            logger.error(
                f"Failed to process upload workflow. Cleaning up storage {e}",
                exc_info=True,
            )
            raise

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

            # Trigger Temporal background processing
            await self.workflow.start_removal(document.document_id)

            return DeleteResponse(
                document_id=db_document.document_id, status=db_document.status
            )
        except Exception as e:
            logger.error(
                f"Failed to process upload workflow. Cleaning up storage {e}",
                exc_info=True,
            )
            raise
